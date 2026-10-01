"""Gate experiments. Each function runs the procedure, analyses it, writes raw
data to data/raw/<session>/ and merges metrics into proofs/<gate>[.sim].json."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from . import readout as ro
from .bench import Bench, randomized
from .core import (load_config, print_gate, proof_path, record_metrics, save_config, save_raw,
                   session_dir)
from .sim import ALL_WELLS, F, solar_session


def _k(name: str, sim: bool) -> str:
    """Config keys used by sim runs are kept apart from real ones."""
    return f"{name}_sim" if sim else name


def _ask_float(prompt: str) -> float:
    while True:
        raw = input(prompt).strip().replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            print("  Please type a number.")


def _free_wells(cfg: dict) -> list[str]:
    taken = set(cfg["electrode_wells"]) | {cfg["ref_acid_well"], cfg["ref_base_well"]}
    return [w for w in ALL_WELLS if w not in taken]


# --------------------------------------------------------------------- G0
def g0_pipette(volume: int, sim: bool, seed: int = 1) -> dict:
    rng = np.random.default_rng(seed + volume)
    if sim:
        per = volume * (1 + 0.006) * (1 + rng.normal(0, 0.007, 10))
        cumulative_g = np.cumsum(per) / 1000.0
    else:
        print(f"Tare the beaker. Dispense {volume} uL ten times; after each, type the scale reading in grams.")
        cumulative_g = np.array([_ask_float(f"  reading {k + 1}/10 (g): ") for k in range(10)])
    dispensed_uL = np.diff(np.concatenate([[0.0], cumulative_g])) * 1000.0
    err = abs(float(np.mean(dispensed_uL)) - volume) / volume * 100
    cv = ro.cv_pct(dispensed_uL)
    d = session_dir(f"g0-pipette-{volume}")
    save_raw(d, "pipette.json", {"volume_uL": volume, "dispensed_uL": dispensed_uL.tolist()})
    if not sim:
        cfg = load_config()
        cfg[f"pipette_factor_{volume}"] = round(volume / float(np.mean(dispensed_uL)), 4)
        save_config(cfg)
    print(f"{volume} uL: mean {np.mean(dispensed_uL):.1f} uL, error {err:.2f}%, CV {cv:.2f}%")
    return record_metrics("G0", {f"pip{volume}_err_pct": err, f"pip{volume}_cv_pct": cv}, sim)


def sign_safety(sim: bool) -> dict:
    if not sim:
        ans = input("Are every safety rule's physical items in place and read (yes/no)? ").strip().lower()
        if ans not in ("y", "yes"):
            print("Not signed.")
            return record_metrics("G0", {}, sim)
    return record_metrics("G0", {"safety_signed": 1}, sim)


# --------------------------------------------------------------------- G1
def g1_linearity(sim: bool, stability: bool, seed: int = 7) -> dict:
    cfg = load_config()
    bench = Bench(cfg, sim, seed=seed, need_controller=False)
    rng = np.random.default_rng(seed)
    concs = [0.0, 6.25, 12.5, 25.0, 50.0, 100.0]
    slots = [("btb", c) for c in concs for _ in range(3)] + [("blank", 0.0)] * 3
    positions = randomized(ALL_WELLS, rng)[:len(slots)]
    plate_map, layout = {}, {}
    for pos, (kind, c) in zip(positions, slots):
        plate_map[pos] = [("fill", "water" if kind == "blank" else f"carb_btb{c:g}", 1.0)]
        layout[pos] = {"kind": kind, "conc_uM": c}
    bench.apply_map(plate_map, "G1 dilution series")
    reads = [bench.read_abs(average=1) for _ in range(10)]
    blanks = [p for p, v in layout.items() if v["kind"] == "blank"]
    btb = [p for p, v in layout.items() if v["kind"] == "btb"]
    blank_abs = float(np.mean([r[p][0] for r in reads for p in blanks]))
    mean_red = {p: float(np.mean([r[p][0] for r in reads])) - blank_abs for p in btb}
    x = np.array([layout[p]["conc_uM"] for p in btb])
    y = np.array([mean_red[p] for p in btb])
    r2, slope, _ = ro.r_squared(x, y)
    fifty = [p for p in btb if layout[p]["conc_uM"] == 50.0]
    read_cv = float(np.mean([ro.cv_pct([r[p][0] for r in reads]) for p in fifty]))
    metrics = {"r2_dilution": r2, "read_cv_pct": read_cv, "blank_abs": blank_abs}
    drift = None
    if stability or sim:
        top = [p for p in btb if layout[p]["conc_uM"] == 100.0]
        series = []
        for k in range(11):
            if k and not sim:
                time.sleep(60)
            r = bench.read_abs(average=3)
            series.append(float(np.mean([r[p][0] for p in top])))
        drift = abs(series[-1] - series[0]) / series[0] * 100
        metrics["drift_pct_10min"] = drift
    d = session_dir("g1-linearity")
    save_raw(d, "g1.json", {"layout": layout, "reads": [{k: v.tolist() for k, v in r.items()} for r in reads],
                            "slope_per_uM": slope, "drift_series": drift})
    print(f"R2 {r2:.4f}, slope {slope * 1000:.2f} mAbs/uM, read CV {read_cv:.2f}%, blank {blank_abs:.4f}"
          + (f", drift {drift:.2f}%" if drift is not None else ""))
    bench.close()
    return record_metrics("G1", metrics, sim)


# --------------------------------------------------------------------- G2
def g2_xor(sim: bool, plates: int, control: str | None, seed: int = 11) -> dict:
    cfg = load_config()
    bench = Bench(cfg, sim, seed=seed, need_controller=False)
    rng = np.random.default_rng(seed)
    medium = "xor_single" if control == "single-indicator" else "xor_dual"
    X, y, raw, rows = [], [], [], []
    for plate in range(plates):
        combos = randomized([(a, b) for a in (0, 1) for b in (0, 1) for _ in range(6)], rng)
        plate_map = {}
        for pos, (a, b) in zip(ALL_WELLS, combos):
            plate_map[pos] = [("fill", medium, 1.0), ("add", "acidA" if a else "water", 50),
                              ("add", ({"Na": 0.020 * 1.06} if sim else "baseB") if b else "water", 50)]
        bench.apply_map(plate_map, f"G2 XOR plate {plate + 1}/{plates} ({medium})")
        bench.wait(120)
        absorb = bench.read_abs(average=3)
        for pos, (a, b) in zip(ALL_WELLS, combos):
            X.append(absorb[pos].tolist())
            y.append(a ^ b)
            raw.append([a, b])
            rows.append({"plate": plate + 1, "pos": pos, "a": a, "b": b, "abs": absorb[pos].tolist()})
    X, y, raw = np.array(X), np.array(y), np.array(raw, dtype=float)
    acc = ro.cv_accuracy(X, y)
    d = session_dir(f"g2-xor-{medium}")
    save_raw(d, "g2.json", rows)
    lo, hi = ro.wilson(int(round(acc * len(y))), len(y))
    if control == "single-indicator":
        print(f"Single-indicator control: CV accuracy {acc:.3f} (95% CI {lo:.2f}-{hi:.2f}). It should be low.")
        bench.close()
        return record_metrics("G2", {"xor_acc_single": acc}, sim)
    raw_acc = ro.cv_accuracy(raw, y)
    p = ro.permutation_p(X, y, n_perm=1000)
    print(f"Dual indicator: CV accuracy {acc:.3f} (95% CI {lo:.2f}-{hi:.2f}); raw-input linear {raw_acc:.3f}; "
          f"permutation p = {p:.4f}; n = {len(y)}")
    bench.close()
    return record_metrics("G2", {"xor_acc_dual": acc, "xor_acc_raw_linear": raw_acc, "perm_p": p,
                                 "n_wells": len(y)}, sim)


# --------------------------------------------------------------------- G3
def g3_charge_cal(sim: bool, port: str | None, seed: int = 13) -> dict:
    cfg = load_config()
    bench = Bench(cfg, sim, seed=seed, port=port, need_camera=False)
    rng = np.random.default_rng(seed)
    bench.apply_map({bench.well_pos(1): [("fill", "sulfate", 1.0)]}, "G3 charge calibration (plain sulfate in W1)")
    cur_err, q_err, rows = [], [], []
    for target in (5.0, 10.0, 20.0, 40.0):
        r = bench.ctl.dose(1, "ACID", target)
        meter = r["mean_mA"] * (1 + rng.normal(0, 0.004)) if sim else _ask_float(
            f"  {target} mC dose: steady multimeter reading in mA: ")
        bench.ctl.dose(1, "BASE", r["delivered_mC"])
        cur_err.append(abs(r["mean_mA"] - meter) / meter * 100)
        q_err.append(abs(r["delivered_mC"] - target) / target * 100)
        rows.append({**r, "meter_mA": meter})
    d = session_dir("g3-charge-cal")
    save_raw(d, "charge_cal.json", rows)
    err = max(float(np.mean(cur_err)), float(np.mean(q_err)))
    print(f"Current error {np.mean(cur_err):.2f}%, charge error {np.mean(q_err):.2f}% -> {err:.2f}%")
    bench.close()
    return record_metrics("G3", {"charge_err_pct": err}, sim)


def g3_faraday(sim: bool, port: str | None, seed: int = 17) -> dict:
    cfg = load_config()
    bench = Bench(cfg, sim, seed=seed, port=port)
    free = _free_wells(cfg)
    std_umol = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8]
    plate_map = bench.reference_map()
    for pos, u in zip(free, std_umol):
        acid_uL = u / 0.010          # 10 mM = 0.010 umol per uL
        steps = [("fill", "cell_P1", 1.0)]
        if acid_uL > 0:
            steps.append(("add", "acid10", acid_uL))
        if 120 - acid_uL > 0:
            steps.append(("add", "water", 120 - acid_uL))
        plate_map[pos] = steps
    w1 = bench.well_pos(1)
    plate_map[w1] = [("fill", "cell_P1", 1.0), ("add", "water", 120)]
    bench.apply_map(plate_map, "G3 standards + W1")
    absorb = bench.read_abs(average=3)
    std_a = np.array([absorb[p][0] for p in free[:len(std_umol)]])
    order = np.argsort(std_a)
    floor = float(std_a.min())
    saturated = [u for u, a in zip(std_umol, std_a) if a < floor + 0.01]
    usable_max = 0.85 * min(saturated) if saturated else max(std_umol)
    effs, raw = [], {"standards": dict(zip(map(str, std_umol), std_a.tolist())), "repeats": []}
    for rep in range(3):
        if rep:
            if sim:
                keep = bench.twin.plate.wells[w1].path_factor
                bench.twin.plate.wells[w1] = type(bench.twin.plate.wells[w1])(path_factor=keep)
                from .bench import medium_spec
                bench.twin.plate.fill(w1, medium_spec("cell_P1")[0], 1.0)
                bench.twin.plate.add(w1, "water", 120)
            else:
                input(f"Refill {w1}: remove liquid, rinse with medium, add 1.0 mL cell_P1 + 120 uL water. Enter... ")
        q_cum, eq, theory = 0.0, [], []
        for _ in range(12):
            r = bench.dose_and_mix(1, "ACID", 6.0)
            q_cum += r["delivered_mC"]
            a = bench.read_abs(average=2)[w1][0]
            eq.append(float(np.interp(a, std_a[order], np.array(std_umol)[order])))
            theory.append(q_cum * 1e-3 / F * 1e6)
        eq, theory = np.array(eq), np.array(theory)
        use = (eq > 0.05) & (eq < usable_max)
        eff = float(np.sum(eq[use] * theory[use]) / np.sum(theory[use] ** 2))
        effs.append(eff)
        raw["repeats"].append({"eq_umol": eq.tolist(), "theory_umol": theory.tolist(), "eff": eff})
        print(f"  repeat {rep + 1}: Faradaic efficiency {eff:.3f} ({int(use.sum())} points in the usable range)")
    d = session_dir("g3-faraday")
    save_raw(d, "faraday.json", raw)
    bench.close()
    return record_metrics("G3", {"faradaic_eff": float(np.mean(effs)), "dose_cv_pct": ro.cv_pct(effs)}, sim)


# --------------------------------------------------------------------- G4
BORATE_LEVELS = [0.0, 0.5, 1.0, 2.0, 4.0]


def g4_threshold(sim: bool, port: str | None, seed: int = 19) -> dict:
    cfg = load_config()
    bench = Bench(cfg, sim, seed=seed, port=port)
    bench.fill_electrode_wells([f"neur_B{b:g}" for b in BORATE_LEVELS])
    fits, raw = {}, {}
    for i, b in enumerate(BORATE_LEVELS, start=1):
        pos = bench.well_pos(i)
        q_max = 12 + 100 * b
        q_cum, qs, ys = 0.0, [0.0], [bench.fired(bench.read_abs(), pos)]
        for _ in range(20):
            r = bench.dose_and_mix(i, "ACID", q_max / 20)
            q_cum += r["delivered_mC"]
            qs.append(q_cum)
            ys.append(bench.fired(bench.read_abs(), pos))
        raw[str(b)] = {"q_mC": qs, "fired": ys}
        try:
            fits[b] = ro.fit_threshold(np.array(qs), np.array(ys))
            print(f"  W{i} borate {b:g} mM: Q50 {fits[b]['q50']:.1f} mC, width {fits[b]['width']:.1f} mC")
        except RuntimeError:
            print(f"  W{i} borate {b:g} mM: sigmoid fit failed")
    buffered = [b for b in BORATE_LEVELS if b > 0 and b in fits]
    r2, slope, icpt = ro.r_squared(np.array(buffered), np.array([fits[b]["q50"] for b in buffered]))
    width_ratio = max(fits[b]["width"] / fits[b]["q50"] for b in buffered)
    control_ratio = fits[0.0]["q50"] / fits[1.0]["q50"] if 0.0 in fits and 1.0 in fits else None
    cfg[_k("q50_fits", sim)] = {f"{b:g}": fits[b]["q50"] for b in fits}
    cfg[_k("q50_line", sim)] = {"slope_mC_per_mM": slope, "intercept_mC": icpt}
    save_config(cfg)
    d = session_dir("g4-threshold")
    save_raw(d, "threshold.json", {"sweeps": raw, "fits": {f"{k:g}": v for k, v in fits.items()}})
    print(f"Q50 = {slope:.1f} mC/mM x borate + {icpt:.1f} mC (R2 {r2:.4f}); worst width ratio {width_ratio:.3f}"
          + (f"; unbuffered control fires at {control_ratio * 100:.1f}% of the 1 mM Q50" if control_ratio else ""))
    bench.close()
    return record_metrics("G4", {"q50_buffer_r2": r2, "width_ratio": width_ratio}, sim,
                          notes=f"control_ratio={control_ratio}")


def _q50(cfg: dict, sim: bool, borate: float) -> float:
    line = cfg.get(_k("q50_line", sim))
    if line:
        return line["slope_mC_per_mM"] * borate + line["intercept_mC"]
    return 52.0 * borate


def g4_reset(sim: bool, port: str | None, cycles: int, seed: int = 23) -> dict:
    cfg = load_config()
    bench = Bench(cfg, sim, seed=seed, port=port)
    bench.fill_electrode_wells(["neur_B1"])
    pos = bench.well_pos(1)
    q50 = _q50(cfg, sim, 1.0)
    q_w = 1.5 * q50
    a0 = bench.read_abs(average=3)[pos][0]
    checkpoints = {1, max(2, cycles // 4), max(3, cycles // 2), max(4, 3 * cycles // 4), cycles}
    q50_track, deltas, log = {}, [], []

    def sweep_q50() -> float:
        q_cum, qs, ys = 0.0, [0.0], [bench.fired(bench.read_abs(), pos)]
        for _ in range(10):
            r = bench.dose_and_mix(1, "ACID", 0.2 * q50)
            q_cum += r["delivered_mC"]
            qs.append(q_cum)
            ys.append(bench.fired(bench.read_abs(), pos))
        bench.dose_and_mix(1, "BASE", q_cum)
        return ro.fit_threshold(np.array(qs), np.array(ys))["q50"]

    for c in range(1, cycles + 1):
        if c in checkpoints:
            q50_track[c] = sweep_q50()
        ra = bench.dose_and_mix(1, "ACID", q_w)
        hi = bench.fired(bench.read_abs(), pos)
        bench.dose_and_mix(1, "BASE", ra["delivered_mC"])
        absb = bench.read_abs()
        lo = bench.fired(absb, pos)
        deltas.append(abs(absb[pos][0] - a0))
        log.append({"cycle": c, "fired_hi": hi, "fired_lo": lo, "delta_abs": deltas[-1],
                    "temp_C": bench.ctl.temp()["temp_C"]})
        if c % 10 == 0:
            print(f"  cycle {c}: high {hi:.2f}, low {lo:.2f}, baseline shift {deltas[-1]:.4f}")
    first, last = q50_track[min(q50_track)], q50_track[max(q50_track)]
    drift = abs(last - first) / first * 100
    d = session_dir("g4-reset")
    save_raw(d, "reset.json", {"log": log, "q50_track": q50_track})
    print(f"Q50 {first:.1f} -> {last:.1f} mC ({drift:.1f}% drift); final baseline shift {deltas[-1]:.4f}")
    bench.close()
    return record_metrics("G4", {"reset_delta_abs": deltas[-1], "cycle_drift_pct": drift, "cycles": cycles}, sim)


# --------------------------------------------------------------------- G5
def linear_relay(delta_signal: float, gain_mC: float) -> float:
    """The ONLY operation allowed between chemical layers: a fixed gain."""
    return gain_mC * delta_signal


def audit_linear_relay() -> int:
    rng = np.random.default_rng(0)
    for _ in range(100):
        g, a, b, c = rng.normal(0, 50), rng.normal(), rng.normal(), rng.normal(0, 3)
        if not math.isclose(linear_relay(a + b, g), linear_relay(a, g) + linear_relay(b, g), rel_tol=1e-9, abs_tol=1e-9):
            return 0
        if not math.isclose(linear_relay(c * a, g), c * linear_relay(a, g), rel_tol=1e-9, abs_tol=1e-9):
            return 0
    return 1


def _apply_signed(bench: Bench, well: int, charge_mC: float, ledger: dict) -> None:
    if abs(charge_mC) < 0.05:
        return
    mode = "ACID" if charge_mC > 0 else "BASE"
    r = bench.ctl.dose(well, mode, abs(charge_mC))
    ledger[well] = ledger.get(well, 0.0) + (r["delivered_mC"] if mode == "ACID" else -r["delivered_mC"])


def _reset_ledger(bench: Bench, ledger: dict) -> None:
    for well, net in list(ledger.items()):
        if abs(net) > 0.05:
            bench.ctl.dose(well, "BASE" if net > 0 else "ACID", abs(net))
        ledger[well] = 0.0
    bench.ctl.mix(bench.cfg["mix_seconds"])
    bench.wait(bench.cfg["settle_seconds"])


def g5_plan(sim: bool) -> dict:
    cfg = load_config()
    b_or, b_out = 0.5, 0.5
    q_unit = 1.6 * _q50(cfg, sim, b_or)
    line = cfg.get(_k("q50_line", sim)) or {"slope_mC_per_mM": 52.0, "intercept_mC": 0.0}
    b_and = round((1.45 * q_unit - line["intercept_mC"]) / line["slope_mC_per_mM"] / 0.05) * 0.05
    stack = {"unit_charge_mC": q_unit, "buffers_mM": {"OR": b_or, "AND": b_and, "OUT": b_out},
             "g_or": None, "g_and": None}
    cfg[_k("stack", sim)] = stack
    save_config(cfg)
    print(f"Input dose per active input: {q_unit:.1f} mC")
    print(f"Make neuron media: W1 OR = {b_or:g} mM borate, W2 AND = {b_and:g} mM, W3 OUT = {b_out:g} mM")
    return stack


def _stack_cfg(sim: bool) -> dict:
    cfg = load_config()
    st = cfg.get(_k("stack", sim))
    if not st or not st.get("unit_charge_mC"):
        st = g5_plan(sim)
    return st


def g5_truth(sim: bool, port: str | None, repeats: int = 10, seed: int = 29) -> dict:
    cfg = load_config()
    st = _stack_cfg(sim)
    bm = st["buffers_mM"]
    bench = Bench(cfg, sim, seed=seed, port=port)
    bench.fill_electrode_wells([f"neur_B{bm['OR']:g}", f"neur_B{bm['AND']:g}"])
    rng = np.random.default_rng(seed)
    q, ledger = st["unit_charge_mC"], {}
    ok_or = ok_and = n = 0
    rows = []
    for _ in range(repeats):
        for a, b in randomized([(0, 0), (0, 1), (1, 0), (1, 1)], rng):
            base = bench.read_abs()
            y0 = [bench.fired(base, bench.well_pos(i)) for i in (1, 2)]
            for _active in range(a + b):
                _apply_signed(bench, 1, q, ledger)
                _apply_signed(bench, 2, q, ledger)
            bench.ctl.mix(cfg["mix_seconds"])
            bench.wait(cfg["settle_seconds"])
            now = bench.read_abs()
            dy = [bench.fired(now, bench.well_pos(i)) - y0[k] for k, i in enumerate((1, 2))]
            out_or, out_and = int(dy[0] > 0.5), int(dy[1] > 0.5)
            ok_or += out_or == (a | b)
            ok_and += out_and == (a & b)
            n += 1
            rows.append({"a": a, "b": b, "dy_or": dy[0], "dy_and": dy[1]})
            _reset_ledger(bench, ledger)
    d = session_dir("g5-truth")
    save_raw(d, "truth.json", rows)
    print(f"OR {ok_or}/{n}, AND {ok_and}/{n}")
    bench.close()
    return record_metrics("G5", {"or_acc": ok_or / n, "and_acc": ok_and / n}, sim)


def g5_stack(sim: bool, port: str | None, trials: int, calibrate: bool, cut_inhibition: bool,
             seed: int = 31, fiber_out: bool = False) -> dict:
    cfg = load_config()
    st = _stack_cfg(sim)
    if calibrate or not st.get("g_or"):
        q50_out = _q50(cfg, sim, st["buffers_mM"]["OUT"])
        st["g_or"] = 1.8 * q50_out
        st["g_and"] = 1.25 * st["g_or"]
        cfg = load_config()
        cfg[_k("stack", sim)] = st
        save_config(cfg)
        print(f"Relay gains: excitatory {st['g_or']:.1f} mC, inhibitory {st['g_and']:.1f} mC per unit signal")
        if calibrate and trials == 0:
            return st
    bm = st["buffers_mM"]
    bench = Bench(cfg, sim, seed=seed, port=port)
    bench.fill_electrode_wells([f"neur_B{bm['OR']:g}", f"neur_B{bm['AND']:g}", f"neur_B{bm['OUT']:g}"])
    rng = np.random.default_rng(seed)
    q, ledger = st["unit_charge_mC"], {}
    combos = randomized([(a, b) for a in (0, 1) for b in (0, 1)] * math.ceil(trials / 4), rng)[:trials]
    correct, rows = 0, []
    g_and = 0.0 if cut_inhibition else st["g_and"]
    for t, (a, b) in enumerate(combos, start=1):
        base = bench.read_abs()
        y0 = [bench.fired(base, bench.well_pos(i)) for i in (1, 2, 3)]
        spec0 = bench.ctl.spec(3) if fiber_out else None
        for _active in range(a + b):
            _apply_signed(bench, 1, q, ledger)
            _apply_signed(bench, 2, q, ledger)
        bench.ctl.mix(cfg["mix_seconds"])
        bench.wait(cfg["settle_seconds"])
        mid = bench.read_abs()
        d_or = bench.fired(mid, bench.well_pos(1)) - y0[0]
        d_and = bench.fired(mid, bench.well_pos(2)) - y0[1]
        _apply_signed(bench, 3, linear_relay(d_or, st["g_or"]), ledger)       # excitatory synapse
        _apply_signed(bench, 3, -linear_relay(d_and, g_and), ledger)          # inhibitory synapse
        bench.ctl.mix(cfg["mix_seconds"])
        bench.wait(cfg["settle_seconds"])
        end = bench.read_abs()
        d_out = bench.fired(end, bench.well_pos(3)) - y0[2]
        if fiber_out:
            s1 = bench.ctl.spec(3)
            a630 = -math.log10(max(s1["diff"][6], 1e-3) / max(spec0["diff"][6], 1e-3))
            out = int(a630 < -0.15)
        else:
            out = int(d_out > 0.5)
        want = (a | b) if cut_inhibition else (a ^ b)
        correct += out == want
        rows.append({"trial": t, "a": a, "b": b, "d_or": d_or, "d_and": d_and, "d_out": d_out, "out": out, "want": want})
        if t % 8 == 0 or t == trials:
            print(f"  trial {t}/{trials}: running accuracy {correct / t:.3f}")
        _reset_ledger(bench, ledger)
    acc = correct / trials
    lo, hi = ro.wilson(correct, trials)
    d = session_dir("g5-stack" + ("-cut" if cut_inhibition else ""))
    save_raw(d, "stack.json", {"stack": st, "rows": rows})
    bench.close()
    if cut_inhibition:
        print(f"Cut-link control computes OR with accuracy {acc:.3f} (95% CI {lo:.2f}-{hi:.2f})")
        return record_metrics("G5", {}, sim, notes=f"cut_link_or_acc={acc:.3f}")
    print(f"Stacked XOR accuracy {acc:.3f} (95% CI {lo:.2f}-{hi:.2f}) over {trials} trials")
    if fiber_out:
        return {"acc": acc, "trials": trials}
    return record_metrics("G5", {"stack_xor_acc": acc, "stack_trials": trials, "linear_relay": audit_linear_relay()}, sim)


# --------------------------------------------------------------------- G6
def _rr(rows: list[dict], v: float = 2.5) -> float:
    fwd = [abs(r["i_uA"]) for r in rows if abs(r["v_set"] - v) < 1e-6]
    rev = [abs(r["i_uA"]) for r in rows if abs(r["v_set"] + v) < 1e-6]
    return float(np.mean(fwd) / max(np.mean(rev), 1e-9))


def g6_diode(sim: bool, port: str | None, devices: int, controls: int, sine: float | None, seed: int = 37) -> dict:
    cfg = load_config()
    bench = Bench(cfg, sim, seed=seed, port=port, need_camera=False)
    d = session_dir("g6-diode")
    if sine:
        if not sim:
            input("Connect a diode tube, scope X = cell voltage, Y = sense resistor, X-Y mode. Enter to start... ")
        rows = bench.ctl.sine(sine, 2.0, 2, device="diode")
        save_raw(d, "sine.json", rows)
        _plot_loop(rows, d / "hysteresis.png")
        print(f"Sine run saved with a plot at {d / 'hysteresis.png'}; photograph your scope too.")
        bench.close()
        return {"saved": str(d)}
    results = {"diode": [], "control": []}
    for kind, count in (("diode", devices), ("control", controls)):
        for k in range(count):
            if not sim:
                input(f"Connect {kind} #{k + 1} (+ end = cationic gel on electrode A). Enter to sweep... ")
            up = bench.ctl.iv(-2.5, 2.5, 0.1, 2000, device=kind)
            down = bench.ctl.iv(2.5, -2.5, -0.1, 2000, device=kind)
            rr = _rr(up + down)
            results[kind].append({"rr": rr, "up": up, "down": down})
            print(f"  {kind} #{k + 1}: rectification ratio {rr:.2f}")
    save_raw(d, "iv.json", results)
    bench.close()
    metrics = {"rr_median": float(np.median([r["rr"] for r in results["diode"]])), "devices": devices}
    if results["control"]:
        metrics["rr_control"] = float(np.median([r["rr"] for r in results["control"]]))
    return record_metrics("G6", metrics, sim)


def _plot_loop(rows: list[dict], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    v = [r["v_cell"] for r in rows]
    i = [r["i_uA"] for r in rows]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(v, i, lw=1.2)
    ax.axhline(0, color="0.7", lw=0.6)
    ax.axvline(0, color="0.7", lw=0.6)
    ax.set_xlabel("Cell voltage (V)")
    ax.set_ylabel("Current (uA)")
    ax.set_title("Hydrogel junction I-V under sine drive")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------- G7
def g7_fiber(sim: bool, port: str | None, seed: int = 41) -> dict:
    cfg = load_config()
    bench = Bench(cfg, sim, seed=seed, port=port)
    bench.fill_electrode_wells(["neur_B1"])
    pos = bench.well_pos(1)
    q50 = _q50(cfg, sim, 1.0)
    cam, fib = [], []
    a0 = bench.read_abs(average=2)[pos][0]
    s0 = bench.ctl.spec(1)["diff"][6]
    for k in range(13):
        if k:
            bench.dose_and_mix(1, "ACID", 2 * q50 / 12)
        cam.append(bench.read_abs(average=2)[pos][0] - a0)
        fib.append(-math.log10(max(bench.ctl.spec(1)["diff"][6], 1e-3) / s0))
    r2, _, _ = ro.r_squared(np.array(cam), np.array(fib))
    if sim:
        bench.ctl.spectral.covered = True
    else:
        input("Cover the plate with the dark box (the camera is now blind). Enter... ")
    blind = [bench.ctl.spec(1)["diff"][6] for _ in range(10)]
    noise = ro.cv_pct(blind)
    d = session_dir("g7-fiber")
    save_raw(d, "fiber.json", {"camera_dA": cam, "fiber_dA": fib, "blind_counts": blind})
    print(f"Fiber vs camera R2 {r2:.4f}; blind noise {noise:.2f}%")
    bench.close()
    return record_metrics("G7", {"fiber_camera_r2": r2, "fiber_blind_noise_pct": noise}, sim)


# --------------------------------------------------------------------- G8
def g8_solar(sim: bool, port: str | None, hours: float, seed: int = 43) -> dict:
    cfg = load_config()
    if sim:
        bench = Bench(cfg, True, seed=seed)
        bench.fill_electrode_wells(["neur_B1"], with_refs=False)
        e0 = bench.ctl.energy_J
        q = 1.5 * _q50(cfg, sim, 1.0)
        for _ in range(10):
            bench.ctl.dose(1, "ACID", q)
            bench.ctl.dose(1, "BASE", q)
        j_per_write = (bench.ctl.energy_J - e0) / 20
        res = solar_session(hours, writes_target=int(30 * hours), rng=np.random.default_rng(seed),
                            write_J=j_per_write)
        print(f"Sim: {res}")
        return record_metrics("G8", {k: res[k] for k in ("solar_hours", "writes", "brownouts", "j_per_write")}, sim)
    bench = Bench(cfg, False, seed=seed, port=port, need_camera=False)
    q = 1.5 * _q50(cfg, False, 1.0)
    t0, writes, brownouts, energies = time.time(), 0, 0, []
    last_boots = bench.ctl.ping().get("boots", 0)
    log = []
    while time.time() - t0 < hours * 3600:
        for mode in ("ACID", "BASE"):
            r = bench.ctl.dose(1, mode, q)
            writes += 1
            if r.get("energy_mJ") is not None:
                energies.append(r["energy_mJ"] / 1000)
        p = bench.ctl.ping()
        if p.get("boots", last_boots) != last_boots:
            brownouts += 1
            last_boots = p["boots"]
        log.append({"t_s": time.time() - t0, "writes": writes, "power": bench.ctl.power()})
        time.sleep(45)
    d = session_dir("g8-solar")
    save_raw(d, "solar.json", log)
    bench.close()
    jpw = float(np.mean(energies)) if energies else -1.0
    return record_metrics("G8", {"solar_hours": (time.time() - t0) / 3600, "writes": writes,
                                 "brownouts": brownouts, "j_per_write": jpw}, sim)


# --------------------------------------------------------------------- G9
def mvp_demo(sim: bool, port: str | None, trials: int) -> dict:
    res = g5_stack(sim, port, trials, calibrate=False, cut_inhibition=False, seed=53, fiber_out=True)
    passed = 0
    for g in [f"G{i}" for i in range(9)]:
        path = proof_path(g, sim)
        if path.exists() and json.loads(path.read_text()).get("pass"):
            passed += 1
    return record_metrics("G9", {"gates_passed": passed, "demo_acc": res["acc"]}, sim)


def report(sim: bool) -> Path:
    lines = ["# WetStack-0 MVP report", "", f"Mode: {'simulation' if sim else 'bench'}", ""]
    for g in [f"G{i}" for i in range(10)]:
        path = proof_path(g, sim)
        if not path.exists():
            lines += [f"## {g}: not run", ""]
            continue
        proof = json.loads(path.read_text())
        lines += [f"## {g} {proof['name']}: {'PASSED' if proof['pass'] else 'not passed'}",
                  f"Updated {proof.get('updated', '')}", "", "| Criterion | Measured | Target | Result |",
                  "|---|---|---|---|"]
        for r in proof["criteria"]:
            m = "-" if r["measured"] is None else (f"{r['measured']:.4g}" if isinstance(r["measured"], float) else str(r["measured"]))
            t = "record" if r["op"] == "record" else f"{r['op']} {r['target']}"
            res = {True: "pass", False: "FAIL", None: "not measured"}[r["pass"]]
            lines.append(f"| {r['label']} | {m} | {t} | {res} |")
        lines.append("")
    out = Path("docs") / ("MVP_REPORT.sim.md" if sim else "MVP_REPORT.md")
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines))
    print(f"Report written to {out}")
    return out


# ------------------------------------------------------------- self test
def selftest(verbose: bool = False) -> bool:
    t0 = time.time()
    steps = [
        ("G0 pipettes", lambda: (g0_pipette(1000, True), g0_pipette(100, True), sign_safety(True))),
        ("G1 optics", lambda: g1_linearity(True, True)),
        ("G2 XOR dual", lambda: g2_xor(True, 2, None)),
        ("G2 single-indicator control", lambda: g2_xor(True, 1, "single-indicator")),
        ("G3 charge", lambda: g3_charge_cal(True, None)),
        ("G3 Faraday", lambda: g3_faraday(True, None)),
        ("G4 threshold", lambda: g4_threshold(True, None)),
        ("G4 reset x100", lambda: g4_reset(True, None, 100)),
        ("G5 plan", lambda: g5_plan(True)),
        ("G5 truth tables", lambda: g5_truth(True, None)),
        ("G5 stack", lambda: g5_stack(True, None, 40, True, False)),
        ("G5 cut-link control", lambda: g5_stack(True, None, 16, False, True)),
        ("G6 diode", lambda: g6_diode(True, None, 3, 1, None)),
        ("G7 fiber", lambda: g7_fiber(True, None)),
        ("G8 solar", lambda: g8_solar(True, None, 4.0)),
        ("G0 self-test flag", lambda: record_metrics("G0", {"selftest_pass": 1}, True)),
        ("G9 demo", lambda: mvp_demo(True, None, 20)),
    ]
    for name, fn in steps:
        print(f"\n### {name}")
        fn()
    ok = True
    for g in [f"G{i}" for i in range(10)]:
        proof = json.loads(proof_path(g, True).read_text())
        print_gate(proof)
        ok &= bool(proof["pass"])
    record_metrics("G0", {"selftest_pass": 1 if ok else 0}, False)
    report(True)
    print(f"Self-test {'PASSED' if ok else 'FAILED'} in {time.time() - t0:.0f} s")
    return ok
