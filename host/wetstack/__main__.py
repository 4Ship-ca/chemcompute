"""python -m wetstack <command> [--sim] ...   (run from the repo root)"""
from __future__ import annotations

import argparse
import json
import sys

from . import experiments as ex
from .core import evaluate, load_config, print_gate, proof_path


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="wetstack", description="WetStack-0 lab commands")
    ap.add_argument("--sim", action="store_true", help="run against the digital twin")
    ap.add_argument("--port", default=None, help="serial port (default from config/lab.json)")
    # Bench commands also accept --sim and --port after the command name, as the manual writes them
    # (python -m wetstack g1-linearity --sim). SUPPRESS keeps an omitted option from overwriting
    # one given before the command.
    bench = argparse.ArgumentParser(add_help=False)
    bench.add_argument("--sim", action="store_true", default=argparse.SUPPRESS, help="run against the digital twin")
    bench.add_argument("--port", default=argparse.SUPPRESS, help="serial port (default from config/lab.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cmd(name: str, **kw) -> argparse.ArgumentParser:
        return sub.add_parser(name, parents=[bench], **kw)

    st = cmd("selftest", help="run every gate against the digital twin")
    st.add_argument("--verbose", action="store_true")
    cmd("ping", help="talk to the controller")
    cmd("relay-test", help="click through relays and check the interlock")
    sp = cmd("spec", help="one AS7341 read")
    sp.add_argument("--diff", action="store_true")
    cam = cmd("camera", help="lock exposure and preview")
    cam.add_argument("--lock", action="store_true")
    cam.add_argument("--preview", action="store_true")
    cmd("calibrate-rois", help="click well centers")
    g = cmd("gate", help="show a gate's status")
    g.add_argument("gate")
    cmd("sign-safety", help="record the safety sign-off")

    p0 = cmd("g0-pipette")
    p0.add_argument("--volume", type=int, choices=[100, 1000], required=True)
    p1 = cmd("g1-linearity")
    p1.add_argument("--stability", action="store_true")
    p2 = cmd("g2-xor-manual")
    p2.add_argument("--plates", type=int, default=2)
    p2.add_argument("--control", choices=["single-indicator"], default=None)
    p3 = cmd("g3-faraday")
    p3.add_argument("--charge-cal", action="store_true")
    cmd("g4-threshold")
    p4 = cmd("g4-reset")
    p4.add_argument("--cycles", type=int, default=100)
    p5 = cmd("g5-logic")
    p5.add_argument("--plan", action="store_true")
    p5.add_argument("--truth", action="store_true")
    p6 = cmd("g5-stack")
    p6.add_argument("--calibrate", action="store_true")
    p6.add_argument("--trials", type=int, default=0)
    p6.add_argument("--cut-inhibition", action="store_true")
    p7 = cmd("g6-diode")
    p7.add_argument("--devices", type=int, default=3)
    p7.add_argument("--control", type=int, default=1)
    p7.add_argument("--sine", type=float, default=None)
    cmd("g7-fiber")
    p8 = cmd("g8-solar")
    p8.add_argument("--hours", type=float, default=4.0)
    p9 = cmd("mvp-demo")
    p9.add_argument("--trials", type=int, default=20)
    cmd("report")
    sv = sub.add_parser("serve", help="open the lab workspace, saving into the repo")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--open", action="store_true", help="open it in your browser")
    qs = sub.add_parser("questions", help="list open lab questions (for Claude Code)")
    qs.add_argument("--all", action="store_true", help="include answered ones")
    an = sub.add_parser("answer", help="answer a lab question by id")
    an.add_argument("id")
    an.add_argument("--text", default=None)
    an.add_argument("--file", default=None, help="read the answer from a text file")
    pg = sub.add_parser("progress", help="progress file tools")
    pg.add_argument("action", choices=["status", "import", "export", "restore"])
    pg.add_argument("path", nargs="?", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    sim, port = a.sim, a.port
    proof = None

    if a.cmd == "serve":
        from .server import serve
        serve(a.port, a.open)
        return 0
    if a.cmd in ("questions", "answer", "progress"):
        return _progress_cmd(a)
    if a.cmd == "selftest":
        return 0 if ex.selftest(a.verbose) else 1
    if a.cmd in ("ping", "relay-test", "spec"):
        from .bench import Bench
        bench = Bench(load_config(), sim, port=port, need_camera=False)
        fn = {"ping": bench.ctl.ping, "relay-test": bench.ctl.relay_test,
              "spec": lambda: bench.ctl.spec(1, diff=a.diff)}[a.cmd]
        print(json.dumps(fn(), indent=1))
        bench.close()
        return 0
    if a.cmd == "camera":
        from .camera import RealCamera
        camera = RealCamera(load_config()["camera_index"])
        if a.lock:
            print(json.dumps(camera.lock(), indent=1))
        if a.preview or not a.lock:
            camera.preview()
        camera.close()
        return 0
    if a.cmd == "calibrate-rois":
        from .camera import RealCamera
        camera = RealCamera(load_config()["camera_index"])
        print(camera.calibrate_rois())
        camera.close()
        return 0
    if a.cmd == "gate":
        path = proof_path(a.gate.upper(), sim)
        metrics = json.loads(path.read_text())["metrics"] if path.exists() else {}
        proof = {"gate": a.gate.upper(), "mode": "sim" if sim else "real", **evaluate(a.gate.upper(), metrics)}
        print_gate(proof)
        return 0 if proof["pass"] else 2
    if a.cmd == "sign-safety":
        proof = ex.sign_safety(sim)
    elif a.cmd == "g0-pipette":
        proof = ex.g0_pipette(a.volume, sim)
    elif a.cmd == "g1-linearity":
        proof = ex.g1_linearity(sim, a.stability)
    elif a.cmd == "g2-xor-manual":
        proof = ex.g2_xor(sim, a.plates, a.control)
    elif a.cmd == "g3-faraday":
        proof = ex.g3_charge_cal(sim, port) if a.charge_cal else ex.g3_faraday(sim, port)
    elif a.cmd == "g4-threshold":
        proof = ex.g4_threshold(sim, port)
    elif a.cmd == "g4-reset":
        proof = ex.g4_reset(sim, port, a.cycles)
    elif a.cmd == "g5-logic":
        if a.plan or not a.truth:
            ex.g5_plan(sim)
        if a.truth:
            proof = ex.g5_truth(sim, port)
    elif a.cmd == "g5-stack":
        res = ex.g5_stack(sim, port, a.trials, a.calibrate, a.cut_inhibition)
        proof = res if isinstance(res, dict) and "criteria" in res else None
    elif a.cmd == "g6-diode":
        res = ex.g6_diode(sim, port, a.devices, a.control, a.sine)
        proof = res if "criteria" in res else None
    elif a.cmd == "g7-fiber":
        proof = ex.g7_fiber(sim, port)
    elif a.cmd == "g8-solar":
        proof = ex.g8_solar(sim, port, a.hours)
    elif a.cmd == "mvp-demo":
        proof = ex.mvp_demo(sim, port, a.trials)
    elif a.cmd == "report":
        ex.report(sim)
        return 0
    if proof and "criteria" in proof:
        print_gate(proof)
    return 0


def _progress_cmd(a) -> int:
    from pathlib import Path
    from . import progress_store as ps
    if a.cmd == "questions":
        doc = ps.load()
        items = [e for e in doc["entries"] if e.get("kind") == "qa" and (a.all or not e.get("a"))]
        if not items:
            print("No open questions.")
            return 0
        steps = {s["id"]: (p, s) for p in json.loads(ps.STEPS_FILE.read_text()) for s in p["steps"]}
        for e in items:
            step = e.get("step") or "general"
            print(f"--- id {e['id']}  step {step}  asked {e.get('t')}")
            if step in steps:
                p, s = steps[step]
                state = doc["state"]["steps"].get(step, {}).get("s", "todo")
                print(f"    {p['id']} {p['title']} / {s['id']} {s['title']} (status {state})")
                note = doc["notes"].get(step, {}).get("text")
                if note:
                    print(f"    notes: {note[:600]}")
                photos = [x.get("file") for x in doc["entries"] if x.get("kind") == "photo" and x.get("step") == step and x.get("file")]
                if photos:
                    print("    photos: " + ", ".join(photos))
            if e.get("file"):
                print(f"    attached photo: {e['file']}")
            print(f"    Q: {e.get('q', '')}")
            if e.get("a"):
                print(f"    A: {e['a']}")
        print("\nAnswer with: python -m wetstack answer <id> --file answer.txt   (or --text \"...\")")
        return 0
    if a.cmd == "answer":
        text = Path(a.file).read_text(encoding="utf-8") if a.file else a.text
        if not text or not text.strip():
            print("Give the answer with --text or --file.")
            return 2
        doc = ps.answer(a.id, text.strip())
        print(f"Answered {a.id}; progress is now revision {doc['rev']}. The workspace shows it within 15 s.")
        return 0
    if a.action == "status":
        doc = ps.load()
        done = sum(1 for v in doc["state"]["steps"].values() if v.get("s") == "done")
        print(f"{ps.PROGRESS_FILE}: revision {doc['rev']}, {done} steps done, {len(doc['entries'])} log entries, "
              f"{len(ps.open_questions(doc))} open questions, {len(list(ps.BACKUP_DIR.glob('progress-*.json')))} backups")
        return 0
    if a.action == "export":
        out = Path(a.path or "progress-export.json")
        out.write_text(json.dumps(ps.load(), indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {out}")
        return 0
    if a.action in ("import", "restore"):
        if not a.path:
            print("Give the file to import, e.g. a workspace export or a file from progress/backups/.")
            return 2
        incoming = json.loads(Path(a.path).read_text(encoding="utf-8"))
        if a.action == "import":
            doc, _ = ps.save(incoming, None)          # merged, nothing lost
            print(f"Merged {a.path} into progress; revision {doc['rev']}.")
        else:
            cur = ps.load()
            restored = ps.migrate(incoming)
            restored["rev"] = cur["rev"]
            doc, _ = ps.save(restored, cur["rev"])    # replace with the backup's content
            print(f"Restored {a.path}; revision {doc['rev']}. The previous version is in progress/backups/.")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
