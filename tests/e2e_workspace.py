"""End-to-end test of the workspace page against the real local server (needs playwright + chromium).
python tests/e2e_workspace.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
def _free_port():
    import socket
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]


PORT = _free_port()


def start_server(cwd):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "host"))
    p = subprocess.Popen([sys.executable, "-m", "wetstack", "serve", "--port", str(PORT)], cwd=cwd, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping", timeout=1)
            return p
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("server did not start")


def main():
    from playwright.sync_api import sync_playwright
    import cv2
    work = Path(tempfile.mkdtemp(prefix="wetstack-e2e-"))
    (work / "web").mkdir()
    shutil.copy(ROOT / "web" / "wetstack_lab.html", work / "web")
    img = np.zeros((3000, 4000, 3), np.uint8); img[:] = (40, 160, 90)
    cv2.imwrite(str(work / "bench.jpg"), img)
    prog = work / "progress" / "progress.json"
    load = lambda: json.loads(prog.read_text())
    srv = start_server(work)
    results = []

    def ok(name, cond):
        results.append((name, bool(cond)))
        print(("ok   " if cond else "FAIL ") + name)

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context()            # one browser profile, like a real browser
        pg = ctx.new_page()
        pg.goto(f"http://127.0.0.1:{PORT}/")
        pg.wait_for_function("store.mode === 'server'")
        pg.click("#s-P0\\.1 .seg button[data-v=done]")
        pg.wait_for_timeout(1500)
        ok("step tick saved to progress.json", load()["state"]["steps"]["P0.1"]["s"] == "done")
        ok("PROGRESS.md regenerated with marker", "- [x] P0.1" in (work / "PROGRESS.md").read_text())

        pg.click("#s-P0\\.2 summary")
        pg.fill("#s-P0\\.2 textarea", "Mat laid, waste jar labeled")
        pg.click("h1")
        pg.wait_for_timeout(1500)
        ok("note saved", load()["notes"]["P0.2"]["text"] == "Mat laid, waste jar labeled")

        pg.set_input_files("#s-P0\\.2 input[type=file]", str(work / "bench.jpg"))
        pg.wait_for_timeout(2500)
        photos = list((work / "photos" / "P0.2").glob("*.jpg"))
        ok("photo stored under photos/P0.2", len(photos) == 1)
        if photos:
            h, w = cv2.imread(str(photos[0])).shape[:2]
            ok("photo resized to 1600 px", max(h, w) == 1600)
        ok("photo entry recorded", any(e.get("kind") == "photo" and e.get("step") == "P0.2" for e in load()["entries"]))
        pg.wait_for_selector("#s-P0\\.2 .photos img")
        ok("thumbnail displays", pg.eval_on_selector("#s-P0\\.2 .photos img", "i => i.naturalWidth > 0"))

        pg.click("nav.tabs >> text=Ask")
        pg.select_option("select[aria-label=Context]", "P0.2")
        pg.fill("textarea[aria-label=Question]", "Is a silicone mat enough for spills?")
        pg.click("text=Save question for Claude Code")
        pg.wait_for_timeout(1500)
        qs = [e for e in load()["entries"] if e.get("kind") == "qa"]
        ok("question saved for Claude Code", len(qs) == 1 and not qs[0]["a"])
        env = dict(os.environ, PYTHONPATH=str(ROOT / "host"))
        out = subprocess.run([sys.executable, "-m", "wetstack", "questions"], cwd=work, env=env, capture_output=True, text=True).stdout
        ok("CLI lists the open question with context", qs and qs[0]["id"] in out and "P0.2" in out and "photos/P0.2" in out)
        subprocess.run([sys.executable, "-m", "wetstack", "answer", qs[0]["id"], "--text", "Yes, with a lipped tray under it."], cwd=work, env=env, check=True)
        pg.evaluate("serverPull()")
        pg.wait_for_selector("text=Yes, with a lipped tray under it.", timeout=5000)
        ok("answer appears in the page", True)

        # A second writer (CLI / Claude Code) changes the file while the page has an unsaved edit
        sys.path.insert(0, str(ROOT / "host"))
        os.chdir(work)
        from wetstack import progress_store as ps
        ps.update(lambda d: d["state"]["steps"].__setitem__("P0.5", {"s": "done", "t": int(time.time() * 1000)}))
        pg.click("nav.tabs >> text=Build")
        pg.click("#s-P0\\.3 .seg button[data-v=doing]")
        pg.wait_for_timeout(1500)
        st = load()["state"]["steps"]
        ok("conflicting writers merged, nothing lost", st.get("P0.5", {}).get("s") == "done" and st.get("P0.3", {}).get("s") == "doing")
        ok("page shows the other writer's change", pg.locator("#s-P0\\.5 .seg button[data-v=done][aria-pressed=true]").count() == 1)

        # Server dies mid-session
        srv.terminate(); srv.wait()
        pg.click("#s-P0\\.4 .seg button[data-v=done]")
        pg.wait_for_timeout(1200)
        ok("status warns when the server is down", "retrying" in pg.inner_text("#syncdot"))
        ok("edit kept in the browser while down", pg.evaluate("JSON.parse(localStorage.getItem('wetstack0.v2')).dirty") is True)
        srv = start_server(work)
        pg.evaluate("serverSave()")
        pg.wait_for_timeout(1500)
        ok("edit saved after the server returns", load()["state"]["steps"].get("P0.4", {}).get("s") == "done")

        # Tab closed with an unsaved edit, reopened later
        pg.evaluate("state.steps['P0.6'] = {s:'done', t:Date.now()}; doc.updated = Date.now(); local.dirty = true; local.seq++; persistLocal();")
        pg.close()
        pg2 = ctx.new_page()
        pg2.goto(f"http://127.0.0.1:{PORT}/")
        pg2.wait_for_function("store.mode === 'server'")
        pg2.wait_for_timeout(1500)
        ok("unsaved edit from a closed tab recovered", load()["state"]["steps"].get("P0.6", {}).get("s") == "done")
        ok("reload shows saved progress", pg2.locator("#s-P0\\.1 .seg button[data-v=done][aria-pressed=true]").count() == 1)
        ok("backups kept", len(list((work / "progress" / "backups").glob("*.json"))) >= 3)

        # Plain-file mode still works on its own
        pf = ctx.new_page()
        pf.goto((work / "web" / "wetstack_lab.html").as_uri())
        pf.wait_for_timeout(600)
        pf.click("#s-P0\\.7 .seg button[data-v=done]")
        pf.reload(); pf.wait_for_timeout(600)
        ok("file mode keeps ticks in the browser", pf.locator("#s-P0\\.7 .seg button[data-v=done][aria-pressed=true]").count() == 1)
        ok("file mode tells you it isn't saving to a file", "browser only" in pf.inner_text("#syncdot"))
        b.close()
    srv.terminate()
    failed = [n for n, c in results if not c]
    print(f"\n{len(results) - len(failed)}/{len(results)} end-to-end checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
