"""Config, sessions, proof files and gate evaluation."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

CONFIG_FILE = Path("config/lab.json")
PROOF_DIR = Path("proofs")
DATA_DIR = Path("data/raw")
GATES_FILE = Path(__file__).with_name("gates.json")

DEFAULT_CONFIG = {
    "port": "COM5",
    "camera_index": 0,
    "electrode_wells": ["A3", "A4", "A5", "A6", "B3"],
    "ref_acid_well": "A1",
    "ref_base_well": "A2",
    "well_volume_mL": 1.0,
    "shunt_ohm": 100.0,
    "mix_seconds": 10,
    "settle_seconds": 5,
    "pipette_factor_1000": 1.0,
    "pipette_factor_100": 1.0,
    "stack": {"g_or": None, "g_and": None, "unit_charge_mC": None, "buffers_mM": None},
    "q50_fits": {},
}


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_FILE.exists():
        user = json.loads(CONFIG_FILE.read_text())
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def session_dir(tag: str, sim: bool) -> Path:
    """Twin runs get a -sim suffix so .gitignore keeps them out of the bench record."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    d = DATA_DIR / f"{stamp}-{tag}{'-sim' if sim else ''}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_raw(directory: Path, name: str, obj) -> Path:
    path = directory / name
    path.write_text(json.dumps(obj, indent=1, default=float))
    return path


def load_gates() -> dict:
    return json.loads(GATES_FILE.read_text())


def proof_path(gate: str, sim: bool) -> Path:
    return PROOF_DIR / f"{gate}{'.sim' if sim else ''}.json"


def record_metrics(gate: str, metrics: dict, sim: bool, notes: str = "") -> dict:
    """Merge metrics into the gate's proof file and re-evaluate it."""
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    path = proof_path(gate, sim)
    proof = json.loads(path.read_text()) if path.exists() else {"gate": gate, "mode": "sim" if sim else "real",
                                                                 "metrics": {}, "history": []}
    clean = {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in metrics.items()}
    proof["metrics"].update(clean)
    proof["history"].append({"t": now_iso(), "metrics": clean, "notes": notes})
    proof["updated"] = now_iso()
    proof.update(evaluate(gate, proof["metrics"]))
    path.write_text(json.dumps(proof, indent=2))
    return proof


def _check(op: str, measured, target) -> bool | None:
    if measured is None:
        return None
    if op == ">=":
        return measured >= target
    if op == "<=":
        return measured <= target
    if op == "==":
        return abs(measured - target) < 1e-9
    if op == "record":
        return True
    raise ValueError(op)


def evaluate(gate: str, metrics: dict) -> dict:
    spec = load_gates()[gate]
    rows, all_ok = [], True
    for c in spec["criteria"]:
        got = metrics.get(c["key"])
        ok = _check(c["op"], got, c["value"])
        rows.append({"key": c["key"], "label": c["label"], "op": c["op"], "target": c["value"],
                     "measured": got, "pass": ok})
        if ok is not True:
            all_ok = False
    return {"criteria": rows, "pass": all_ok, "name": spec["name"]}


def print_gate(proof: dict) -> None:
    print(f"\n== Gate {proof['gate']} ({proof['name']}) [{proof['mode']}] ==")
    for r in proof["criteria"]:
        mark = {True: "PASS", False: "FAIL", None: "----"}[r["pass"]]
        measured = "not measured" if r["measured"] is None else f"{r['measured']:.4g}" if isinstance(r["measured"], float) else r["measured"]
        target = "" if r["op"] == "record" else f"{r['op']} {r['target']}"
        print(f"  [{mark}] {r['label']:<44} {measured:>14}  {target}")
    print(f"  => {'GATE PASSED' if proof['pass'] else 'gate not passed yet'}\n")
