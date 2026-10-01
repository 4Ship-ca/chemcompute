"""python -m wetstack <command> [--sim] ...   (run from the repo root)"""
from __future__ import annotations

import argparse
import json
import sys

from . import experiments as ex
from .core import evaluate, load_config, print_gate, proof_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wetstack", description="WetStack-0 lab commands")
    ap.add_argument("--sim", action="store_true", help="run against the digital twin")
    ap.add_argument("--port", default=None, help="serial port (default from config/lab.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("selftest", help="run every gate against the digital twin")
    st.add_argument("--verbose", action="store_true")
    sub.add_parser("ping", help="talk to the controller")
    sub.add_parser("relay-test", help="click through relays and check the interlock")
    sp = sub.add_parser("spec", help="one AS7341 read")
    sp.add_argument("--diff", action="store_true")
    cam = sub.add_parser("camera", help="lock exposure and preview")
    cam.add_argument("--lock", action="store_true")
    cam.add_argument("--preview", action="store_true")
    sub.add_parser("calibrate-rois", help="click well centers")
    g = sub.add_parser("gate", help="show a gate's status")
    g.add_argument("gate")
    sub.add_parser("sign-safety", help="record the safety sign-off")

    p0 = sub.add_parser("g0-pipette")
    p0.add_argument("--volume", type=int, choices=[100, 1000], required=True)
    p1 = sub.add_parser("g1-linearity")
    p1.add_argument("--stability", action="store_true")
    p2 = sub.add_parser("g2-xor-manual")
    p2.add_argument("--plates", type=int, default=2)
    p2.add_argument("--control", choices=["single-indicator"], default=None)
    p3 = sub.add_parser("g3-faraday")
    p3.add_argument("--charge-cal", action="store_true")
    sub.add_parser("g4-threshold")
    p4 = sub.add_parser("g4-reset")
    p4.add_argument("--cycles", type=int, default=100)
    p5 = sub.add_parser("g5-logic")
    p5.add_argument("--plan", action="store_true")
    p5.add_argument("--truth", action="store_true")
    p6 = sub.add_parser("g5-stack")
    p6.add_argument("--calibrate", action="store_true")
    p6.add_argument("--trials", type=int, default=0)
    p6.add_argument("--cut-inhibition", action="store_true")
    p7 = sub.add_parser("g6-diode")
    p7.add_argument("--devices", type=int, default=3)
    p7.add_argument("--control", type=int, default=1)
    p7.add_argument("--sine", type=float, default=None)
    sub.add_parser("g7-fiber")
    p8 = sub.add_parser("g8-solar")
    p8.add_argument("--hours", type=float, default=4.0)
    p9 = sub.add_parser("mvp-demo")
    p9.add_argument("--trials", type=int, default=20)
    sub.add_parser("report")

    a = ap.parse_args(argv)
    sim, port = a.sim, a.port
    proof = None

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


if __name__ == "__main__":
    sys.exit(main())
