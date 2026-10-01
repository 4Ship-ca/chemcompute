"""Progress storage tests: python tests/test_progress.py (or pytest)."""
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
from wetstack import progress_store as ps  # noqa: E402


def _in_tmp():
    d = tempfile.mkdtemp(prefix="wetstack-test-")
    os.chdir(d)
    return Path(d)


def test_migrate_v1_browser_shape():
    _in_tmp()
    v1 = {"state": {"steps": {"P0.1": {"s": "done", "t": 5}}, "gates": {}, "bom": {}, "meta": {"phase": "P1"}, "updated": 9},
          "notes": {"updated": 7, "notes": {"P0.1": "hello"}}, "entries": [{"kind": "note", "text": "x", "t": 3}]}
    d = ps.migrate(v1)
    assert d["state"]["steps"]["P0.1"]["s"] == "done" and d["notes"]["P0.1"] == {"text": "hello", "t": 7}
    assert d["entries"][0]["id"].startswith("legacy-") and d["state"]["meta"]["phase"] == "P1"


def test_merge_newest_wins_nothing_lost():
    a = ps.empty_doc(); b = ps.empty_doc()
    a["state"]["steps"] = {"P0.1": {"s": "done", "t": 10}, "P0.2": {"s": "doing", "t": 10}}
    b["state"]["steps"] = {"P0.2": {"s": "done", "t": 20}, "P0.3": {"s": "blocked", "t": 5}}
    a["entries"] = [{"id": "q1", "kind": "qa", "q": "why", "a": "", "t": 1}]
    b["entries"] = [{"id": "q1", "kind": "qa", "q": "why", "a": "because", "a_t": 2, "t": 1, "edited": 2}, {"id": "n1", "kind": "note", "t": 3}]
    m = ps.merge(a, b)
    assert m["state"]["steps"]["P0.1"]["s"] == "done" and m["state"]["steps"]["P0.2"]["s"] == "done"
    assert m["state"]["steps"]["P0.3"]["s"] == "blocked" and len(m["entries"]) == 2
    assert [e for e in m["entries"] if e["id"] == "q1"][0]["a"] == "because"
    m2 = ps.merge(b, a)                                   # answer survives either order
    assert [e for e in m2["entries"] if e["id"] == "q1"][0]["a"] == "because"


def test_save_stale_rev_merges_and_backs_up():
    _in_tmp()
    d1 = ps.empty_doc(); d1["state"]["steps"]["P0.1"] = {"s": "done", "t": 1}
    s1, merged = ps.save(d1, 0); assert s1["rev"] == 1 and not merged
    d2 = ps.empty_doc(); d2["state"]["steps"]["P0.2"] = {"s": "done", "t": 2}
    s2, merged = ps.save(d2, 0)                           # stale: started from rev 0
    assert merged and s2["rev"] == 2 and set(s2["state"]["steps"]) == {"P0.1", "P0.2"}
    assert len(list(ps.BACKUP_DIR.glob("progress-*.json"))) == 1
    assert Path("PROGRESS.md").exists()


def test_corrupt_file_falls_back_to_backup():
    _in_tmp()
    d = ps.empty_doc(); d["state"]["steps"]["P0.1"] = {"s": "done", "t": 1}
    ps.save(d, 0); ps.save(d, 1)
    ps.PROGRESS_FILE.write_text("{ broken")
    assert ps.load()["state"]["steps"]["P0.1"]["s"] == "done"


def test_answer_and_validation():
    _in_tmp()
    d = ps.empty_doc(); d["entries"] = [{"id": "q9", "kind": "qa", "q": "?", "a": "", "t": 1}]
    ps.save(d, 0)
    assert len(ps.open_questions(ps.load())) == 1
    ps.answer("q9", "Do this.")
    assert ps.open_questions(ps.load()) == [] and "Open questions" not in Path("PROGRESS.md").read_text()
    bad = ps.empty_doc(); bad["entries"] = [{"id": "x", "kind": "photo", "file": "../secrets.txt", "t": 1}]
    try:
        ps.save(bad, None); raise AssertionError("unsafe path accepted")
    except ps.ProgressError:
        pass


def test_concurrent_writers():
    _in_tmp(); ps.save(ps.empty_doc(), 0)
    errors = []

    def worker(i):
        try:
            for k in range(10):
                d = ps.empty_doc(); d["state"]["steps"][f"P{i}.{k + 1}"] = {"s": "done", "t": time.time()}
                ps.save(d, 0)                             # always stale on purpose
        except Exception as e:                            # pragma: no cover
            errors.append(e)

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    doc = ps.load()
    assert not errors and len(doc["state"]["steps"]) == 40 and doc["rev"] == 41


def test_server_security():
    tmp = _in_tmp()
    (tmp / "web").mkdir(); (tmp / "web" / "wetstack_lab.html").write_text("<html>ok</html>")
    from http.server import ThreadingHTTPServer
    from wetstack import server
    server.Handler.port = 18766
    httpd = ThreadingHTTPServer(("127.0.0.1", 18766), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:18766"

    def req(path, method="GET", body=None, headers=None):
        r = urllib.request.Request(base + path, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    try:
        assert req("/api/ping")[0] == 200
        body = json.dumps({"base_rev": 0, "doc": ps.empty_doc()}).encode()
        assert req("/api/progress", "PUT", body, {"Content-Type": "application/json"})[0] == 403            # no header
        assert req("/api/progress", "PUT", body, {"X-WetStack": "1", "Origin": "https://evil.example"})[0] == 403
        assert req("/api/progress", "PUT", body, {"X-WetStack": "1", "Host": "evil.example:18766"})[0] == 403
        assert req("/api/progress", "PUT", body, {"X-WetStack": "1", "Content-Type": "application/json"})[0] == 200
        assert req("/photos/../progress/progress.json")[0] in (403, 404)
        assert req("/api/photo?step=../../x", "POST", b"notanimage", {"X-WetStack": "1"})[0] == 400
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    fns = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"ok  {fn.__name__}")
    print(f"{len(fns)} progress tests passed")
