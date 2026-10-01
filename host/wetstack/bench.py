"""One Bench object for both modes.

In --sim mode, pipetting maps are applied to the simulated plate.
In real mode, the same maps are printed for you to pipette, and the script
waits for Enter before reading.
"""
from __future__ import annotations

import time

import numpy as np

from . import sim
from .camera import rgb_to_absorbance

BTB_STOCK_uM = 640.6     # 0.4 mg/mL bromothymol blue, MW 624.4
PR_STOCK_uM = 564.4      # 0.2 mg/mL phenol red, MW 354.4


def medium_spec(name: str) -> tuple[dict, str]:
    """Returns (sim composition in mol/L, instruction text for a person)."""
    if name.startswith("cell_P"):
        p = float(name[len("cell_P"):])
        base = 0.0016 if p == 0 else 0.0
        text = (f"Cell medium, {p:g} mM phosphate pH 7.6 (50 mM sulfate, 40 uM BTB)"
                + (" - adjust to blue-green with a trace of carbonate" if p == 0 else ""))
        return sim.medium(phos_mM=p, base_mM=base), text
    if name.startswith("neur_B"):
        b = float(name[len("neur_B"):])
        base = 0.03 if b == 0 else 0.0
        text = (f"Neuron medium, {b:g} mM borate (50 mM sulfate, 40 uM BTB)"
                + (" - adjust to blue-green with a trace of carbonate" if b == 0 else ""))
        return sim.medium(phos_mM=0, borate_mM=b, base_mM=base), text
    if name == "xor_dual":
        return sim.medium(phos_mM=1.0, pr_uM=14.0), "XOR medium, dual indicator (BTB + phenol red)"
    if name == "xor_single":
        return sim.medium(phos_mM=1.0), "XOR medium, BTB only (control)"
    if name.startswith("carb_btb"):
        c = float(name[len("carb_btb"):])
        vol_uL = c * 1000.0 / BTB_STOCK_uM
        return (sim.medium(phos_mM=0, sulfate_mM=0, btb_uM=c, base_mM=10.0),
                f"10 mM carbonate + {vol_uL:.1f} uL BTB stock per mL ({c:g} uM)")
    if name == "sulfate":
        return sim.medium(phos_mM=0, btb_uM=0), "50 mM sodium sulfate, no indicator"
    if name == "water":
        return {}, "Distilled water"
    raise KeyError(name)


REAGENT_TEXT = {
    "acidA": "input A: 20 mM sodium bisulfate",
    "baseB": "input B: balanced carbonate",
    "water": "distilled water",
    "acid10": "10 mM sodium bisulfate standard",
    "acid_ref": "200 mM sodium bisulfate (acid reference)",
    "base_ref": "0.1 M sodium carbonate (base reference)",
}


class Bench:
    def __init__(self, cfg: dict, sim_mode: bool, seed: int = 7, port: str | None = None,
                 need_camera: bool = True, need_controller: bool = True):
        self.cfg, self.sim = cfg, sim_mode
        self.electrode_wells = cfg["electrode_wells"]
        self.vol_mL = cfg["well_volume_mL"]
        self.twin = None
        self.camera = None
        self.ctl = None
        if sim_mode:
            self.twin = sim.SimBench(self.electrode_wells, seed=seed)
            self.camera = self.twin.camera
            self.ctl = self.twin.ctl
        else:
            if need_camera:
                from .camera import RealCamera
                self.camera = RealCamera(cfg["camera_index"])
            if need_controller:
                from .link import SerialController
                self.ctl = SerialController(port or cfg["port"])

    # ---------------------------------------------------------------- liquids
    def apply_map(self, plate_map: dict, title: str, ask: bool = True) -> None:
        """plate_map: {pos: [("fill", medium, mL) | ("add", reagent, uL), ...]}"""
        if self.sim:
            self.twin.plate.reset()
            for pos, steps in plate_map.items():
                for kind, what, amount in steps:
                    if kind == "fill":
                        comp, _ = medium_spec(what)
                        self.twin.plate.fill(pos, comp, amount)
                    else:
                        self.twin.plate.add(pos, what, amount)
            return
        print(f"\n--- Pipetting map: {title} ---")
        for pos in sim.ALL_WELLS:
            if pos not in plate_map:
                continue
            parts = []
            for kind, what, amount in plate_map[pos]:
                if kind == "fill":
                    parts.append(f"{amount:g} mL {medium_spec(what)[1]}")
                else:
                    parts.append(f"+ {amount:g} uL {REAGENT_TEXT.get(what, what)}")
            print(f"  {pos}: " + "; ".join(parts))
        print("Empty wells stay empty. Tap the plate gently to mix.")
        if ask:
            input("Place the plate in the frame and press Enter to read... ")

    def reference_map(self) -> dict:
        a, b = self.cfg["ref_acid_well"], self.cfg["ref_base_well"]
        return {a: [("fill", "cell_P1", self.vol_mL), ("add", "acid_ref", 50)],
                b: [("fill", "cell_P1", self.vol_mL), ("add", "base_ref", 50)]}

    # ----------------------------------------------------------------- optics
    def read_abs(self, average: int = 1) -> dict:
        acc = None
        for _ in range(average):
            a = rgb_to_absorbance(self.camera.read_rgb())
            acc = a if acc is None else {k: acc[k] + a[k] for k in a}
        return {k: v / average for k, v in acc.items()}

    # ----------------------------------------------------------- electrodes
    def well_pos(self, index: int) -> str:
        return self.electrode_wells[index - 1]

    def dose_and_mix(self, index: int, mode: str, charge_mC: float) -> dict:
        r = self.ctl.dose(index, mode, charge_mC)
        self.ctl.mix(self.cfg["mix_seconds"])
        self.wait(self.cfg["settle_seconds"])
        return r

    def wait(self, seconds: float) -> None:
        if not self.sim:
            time.sleep(seconds)

    def fill_electrode_wells(self, media: list[str], with_refs: bool = True) -> None:
        plate_map = self.reference_map() if with_refs else {}
        for i, name in enumerate(media):
            plate_map[self.well_pos(i + 1)] = [("fill", name, self.vol_mL)]
        self.apply_map(plate_map, "electrode wells")

    def fired(self, absorb: dict, pos: str) -> float:
        """Fired fraction of a BTB well from reference wells, red channel."""
        a_base = absorb[self.cfg["ref_base_well"]][0]
        a_acid = absorb[self.cfg["ref_acid_well"]][0]
        return float((a_base - absorb[pos][0]) / (a_base - a_acid))

    def close(self) -> None:
        if not self.sim:
            if self.ctl is not None:
                self.ctl.close()
            if self.camera is not None:
                self.camera.close()


def randomized(items: list, rng: np.random.Generator) -> list:
    order = rng.permutation(len(items))
    return [items[i] for i in order]
