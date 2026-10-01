"""Canonical progress storage: progress/progress.json in the repo.

Guarantees
  * Atomic writes: temp file + fsync + os.replace, so a crash never leaves a half-written file.
  * Rolling backups in progress/backups/ (last 40 kept, gitignored) before every overwrite.
  * A revision counter. Writers send the revision they started from; if someone else saved in
    between, the two documents are merged item by item (newest timestamp wins) instead of one
    overwriting the other.
  * A cross-process lock file so the web server and CLI commands never write at the same time.
  * Validation and migration of older shapes on every load.
  * PROGRESS.md regenerated on every save (the completion markers GitHub shows).
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import time
from pathlib import Path

SCHEMA = "wetstack-progress"
VERSION = 2
MAX_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 5000
KEEP_BACKUPS = 40
ID_RE = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")
STEP_RE = re.compile(r"^P\d\.\d{1,2}$")

PROGRESS_DIR = Path("progress")
PROGRESS_FILE = PROGRESS_DIR / "progress.json"
BACKUP_DIR = PROGRESS_DIR / "backups"
LOCK_FILE = PROGRESS_DIR / ".lock"
STEPS_FILE = Path(__file__).with_name("steps.json")
GATES_FILE = Path(__file__).with_name("gates.json")


class ProgressError(ValueError):
    pass


def now_ms() -> int:
    return int(time.time() * 1000)


def empty_doc() -> dict:
    return {"schema": SCHEMA, "version": VERSION, "rev": 0, "updated": 0,
            "state": {"steps": {}, "gates": {}, "bom": {}, "meta": {"phase": "P0", "t": 0}},
            "notes": {}, "entries": []}


def _num(v, default=0):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else default


def migrate(raw) -> dict:
    """Accept any earlier shape (v1 browser export, bare state, partial doc) and return a clean v2 doc."""
    if not isinstance(raw, dict):
        raise ProgressError("Progress must be a JSON object")
    doc = empty_doc()
    src_state = raw.get("state") if isinstance(raw.get("state"), dict) else (raw if "steps" in raw else {})
    notes_src = raw.get("notes", {})
    if isinstance(notes_src, dict) and isinstance(notes_src.get("notes"), dict):      # v1 {updated, notes}
        notes_t = _num(notes_src.get("updated"))
        notes_src = {k: {"text": v, "t": notes_t} for k, v in notes_src["notes"].items() if isinstance(v, str)}
    doc["rev"] = int(_num(raw.get("rev")))
    doc["updated"] = int(_num(raw.get("updated"), _num(src_state.get("updated"))))
    st = doc["state"]
    for key in ("steps", "gates", "bom"):
        part = src_state.get(key, {})
        if isinstance(part, dict):
            for item_id, item in part.items():
                if isinstance(item_id, str) and ID_RE.match(item_id) and isinstance(item, dict):
                    clean = copy.deepcopy(item)
                    clean["t"] = int(_num(item.get("t"), doc["updated"]))
                    st[key][item_id] = clean
    meta = src_state.get("meta", {})
    if isinstance(meta, dict):
        st["meta"]["phase"] = meta.get("phase") if isinstance(meta.get("phase"), str) else "P0"
        st["meta"]["t"] = int(_num(meta.get("t"), doc["updated"]))
    if isinstance(notes_src, dict):
        for k, v in notes_src.items():
            if not (isinstance(k, str) and ID_RE.match(k)):
                continue
            if isinstance(v, str):
                doc["notes"][k] = {"text": v, "t": doc["updated"]}
            elif isinstance(v, dict) and isinstance(v.get("text"), str):
                doc["notes"][k] = {"text": v["text"], "t": int(_num(v.get("t"), doc["updated"]))}
    ents = raw.get("entries", [])
    if isinstance(ents, list):
        for i, e in enumerate(ents[-MAX_ENTRIES:]):
            if not isinstance(e, dict):
                continue
            e = copy.deepcopy(e)
            eid = e.get("id") if isinstance(e.get("id"), str) and ID_RE.match(e.get("id", "")) else f"legacy-{_num(e.get('t'))}-{i}"
            e["id"] = eid
            e["t"] = int(_num(e.get("t")))
            if e.get("kind") not in ("note", "photo", "qa"):
                e["kind"] = "note"
            doc["entries"].append(e)
    return doc


def validate(doc: dict) -> dict:
    doc = migrate(doc)
    size = len(json.dumps(doc))
    if size > MAX_BYTES:
        raise ProgressError(f"Progress is {size // 1024} KB, over the {MAX_BYTES // 1048576} MB limit; prune the log")
    for e in doc["entries"]:
        f = e.get("file")
        if f is not None and (not isinstance(f, str) or not f.startswith("photos/") or ".." in f or "\\" in f):
            raise ProgressError(f"Entry {e['id']} has an unsafe file path")
    return doc


def _newer(a: dict | None, b: dict | None) -> dict | None:
    if a is None:
        return b
    if b is None:
        return a
    return b if _num(b.get("t")) > _num(a.get("t")) else a


def merge(base: dict, incoming: dict) -> dict:
    """Item-level merge: for every step, gate, part, note and log entry, the newer timestamp wins.
    Nothing present in either document is ever dropped."""
    a, b = migrate(base), migrate(incoming)
    out = empty_doc()
    for key in ("steps", "gates", "bom"):
        for k in set(a["state"][key]) | set(b["state"][key]):
            out["state"][key][k] = copy.deepcopy(_newer(a["state"][key].get(k), b["state"][key].get(k)))
    out["state"]["meta"] = copy.deepcopy(_newer(a["state"]["meta"], b["state"]["meta"]))
    for k in set(a["notes"]) | set(b["notes"]):
        out["notes"][k] = copy.deepcopy(_newer(a["notes"].get(k), b["notes"].get(k)))
    by_id: dict[str, dict] = {}
    for e in a["entries"] + b["entries"]:
        cur = by_id.get(e["id"])
        if cur is None:
            by_id[e["id"]] = copy.deepcopy(e)
            continue
        winner = e if _num(e.get("edited", e.get("t"))) >= _num(cur.get("edited", cur.get("t"))) else cur
        merged = copy.deepcopy(winner)
        if not merged.get("a") and (cur.get("a") or e.get("a")):      # never lose an answer
            src = cur if cur.get("a") else e
            merged["a"], merged["a_t"] = src.get("a"), src.get("a_t")
        by_id[e["id"]] = merged
    out["entries"] = sorted(by_id.values(), key=lambda e: e.get("t", 0))[-MAX_ENTRIES:]
    out["rev"] = max(a["rev"], b["rev"])
    out["updated"] = max(a["updated"], b["updated"])
    return out


class FileLock:
    """Cross-process lock using an exclusively created file; stale locks expire after 15 s."""

    def __init__(self, path: Path = LOCK_FILE, timeout: float = 10.0):
        self.path, self.timeout = path, timeout

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        end = time.time() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 15:
                        self.path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.time() > end:
                    raise ProgressError("Progress file is locked by another writer; try again")
                time.sleep(0.05)

    def __exit__(self, *exc):
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def load() -> dict:
    if not PROGRESS_FILE.exists():
        return empty_doc()
    try:
        return migrate(json.loads(PROGRESS_FILE.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ProgressError):
        # Corrupt file (should never happen with atomic writes): fall back to the newest good backup.
        for b in sorted(BACKUP_DIR.glob("progress-*.json"), reverse=True):
            try:
                return migrate(json.loads(b.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ProgressError):
                continue
        raise ProgressError("progress.json is unreadable and no good backup exists")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    for attempt in range(20):            # Windows: a reader may briefly hold the target open
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05 * (attempt + 1))
    os.replace(tmp, path)


def _backup(current_text: str, rev: int) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    (BACKUP_DIR / f"progress-{stamp}-r{rev:06d}.json").write_text(current_text, encoding="utf-8")
    olds = sorted(BACKUP_DIR.glob("progress-*.json"))
    for old in olds[:-KEEP_BACKUPS]:
        old.unlink(missing_ok=True)


def save(incoming: dict, base_rev: int | None) -> tuple[dict, bool]:
    """Save a document. Returns (stored_doc, merged). Merges when base_rev is stale."""
    incoming = validate(incoming)
    with FileLock():
        current = load()
        merged = base_rev is None or base_rev != current["rev"]
        doc = merge(current, incoming) if merged else incoming
        doc["rev"] = current["rev"] + 1
        doc["updated"] = max(doc["updated"], now_ms())
        if PROGRESS_FILE.exists():
            _backup(PROGRESS_FILE.read_text(encoding="utf-8"), current["rev"])
        _atomic_write(PROGRESS_FILE, json.dumps(doc, indent=1, ensure_ascii=False))
        try:
            _atomic_write(Path("PROGRESS.md"), render_markdown(doc))
        except OSError:
            pass
    return doc, merged


def update(fn) -> dict:
    """Read-modify-write under the lock (used by CLI commands)."""
    with FileLock():
        current = load()
        doc = copy.deepcopy(current)
        fn(doc)
        doc = validate(doc)
        doc["rev"] = current["rev"] + 1
        doc["updated"] = now_ms()
        if PROGRESS_FILE.exists():
            _backup(PROGRESS_FILE.read_text(encoding="utf-8"), current["rev"])
        _atomic_write(PROGRESS_FILE, json.dumps(doc, indent=1, ensure_ascii=False))
        _atomic_write(Path("PROGRESS.md"), render_markdown(doc))
    return doc


def _check(op, got, target):
    if got is None:
        return None
    if op == ">=":
        return got >= target
    if op == "<=":
        return got <= target
    if op == "==":
        return abs(got - target) < 1e-9
    return True


def render_markdown(doc: dict) -> str:
    phases = json.loads(STEPS_FILE.read_text()) if STEPS_FILE.exists() else []
    gates = json.loads(GATES_FILE.read_text()) if GATES_FILE.exists() else {}
    st = doc["state"]
    done = sum(1 for p in phases for s in p["steps"] if st["steps"].get(s["id"], {}).get("s") == "done")
    total = sum(len(p["steps"]) for p in phases)
    L = ["# WetStack-0 progress", "",
         f"Revision {doc['rev']}, saved {dt.datetime.fromtimestamp(doc['updated'] / 1000).isoformat(timespec='seconds') if doc['updated'] else 'never'}. "
         f"{done} of {total} steps done.", "",
         "Generated from progress/progress.json. Do not edit by hand.", ""]
    for p in phases:
        L += [f"## {p['id']} {p['title']}", ""]
        for s in p["steps"]:
            state = st["steps"].get(s["id"], {}).get("s", "todo")
            tag = f" ({state})" if state in ("doing", "blocked") else ""
            L.append(f"- [{'x' if state == 'done' else ' '}] {s['id']} {s['title']}{tag}")
        g = gates.get(p["gate"])
        if g:
            vals = st["gates"].get(p["gate"], {}).get("values", {})
            rows = [(c, vals.get(c["key"]), _check(c["op"], vals.get(c["key"]), c["value"])) for c in g["criteria"]]
            passed = all(ok is True for _, _, ok in rows)
            L += ["", f"Gate {p['gate']} {g['name']}: {'PASSED' if passed else 'open'}"]
            for c, v, ok in rows:
                target = "record" if c["op"] == "record" else f"{c['op']} {c['value']}"
                L.append(f"  - {c['label']}: {'-' if v is None else v} (target {target}){' pass' if ok is True else ' FAIL' if ok is False else ''}")
        L.append("")
    open_q = [e for e in doc["entries"] if e.get("kind") == "qa" and not e.get("a")]
    if open_q:
        L += ["## Open questions", ""] + [f"- {e['id']} ({e.get('step') or 'general'}): {e.get('q', '')}" for e in open_q] + [""]
    return "\n".join(L)


def open_questions(doc: dict) -> list[dict]:
    return [e for e in doc["entries"] if e.get("kind") == "qa" and not e.get("a")]


def answer(entry_id: str, text: str, by: str = "Claude Code") -> dict:
    found = {"ok": False}

    def fn(doc):
        for e in doc["entries"]:
            if e["id"] == entry_id:
                e["a"], e["a_t"], e["a_by"] = text, now_ms(), by
                e["edited"] = now_ms()
                found["ok"] = True
        if not found["ok"]:
            raise ProgressError(f"No entry with id {entry_id}")

    return update(fn)


def safe_step(step: str | None) -> str:
    return step if step and STEP_RE.match(step) else "log"
