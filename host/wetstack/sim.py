"""WetStack digital twin.

Physical models used by every --sim run:
  * charge-balance pH solver: phosphate (3 pKa), sulfate, two indicators, strong acid/base
  * indicator speciation -> per-channel absorbance (camera RGB and AS7341 bands)
  * Faraday dosing with efficiency, slow indicator oxidation and efficiency drift
  * 8-bit camera with sRGB gamma, saturation and noise (so the real pipeline is exercised)
  * bipolar hydrogel diode with first-order memory
  * solar + battery + load energy model
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

F = 96485.33212        # C/mol
KW = 1.0e-14
PKA_PHOS = (2.15, 7.21, 12.32)
PKA_HSO4 = 1.99
PKA_BORATE = 9.24
WELL_AREA_CM2 = 1.90   # 24-well plate well bottom area
PLATE_ROWS = "ABCD"
PLATE_COLS = range(1, 7)
ALL_WELLS = [f"{r}{c}" for r in PLATE_ROWS for c in PLATE_COLS]

# Indicator data: pKa, molar absorptivity (L mol-1 cm-1) of acid and base forms.
# Camera channels are band-averaged effective values; spectra are Gaussian.
INDICATORS = {
    "BTB": {"pKa": 7.10,
            "acid_rgb": (200.0, 2500.0, 14000.0), "base_rgb": (30000.0, 9000.0, 2500.0),
            "acid_peak": (433.0, 48.0, 16000.0), "base_peak": (617.0, 58.0, 38000.0)},
    "PR": {"pKa": 7.90,
           "acid_rgb": (200.0, 2000.0, 15000.0), "base_rgb": (4000.0, 30000.0, 6000.0),
           "acid_peak": (430.0, 46.0, 18000.0), "base_peak": (558.0, 48.0, 43000.0)},
}
AS7341_BANDS_NM = (415, 445, 480, 515, 555, 590, 630, 680)


# ---------------------------------------------------------------------------
# Chemistry
# ---------------------------------------------------------------------------
@dataclass
class Well:
    """Contents tracked in moles so additions and dilutions are exact."""
    vol_L: float = 0.0
    n_P: float = 0.0          # total phosphate
    n_S: float = 0.0          # total sulfate
    n_B: float = 0.0          # total borate (boric acid + borate)
    n_Na: float = 0.0         # sodium (includes strong base added)
    n_X: float = 0.0          # strong-acid anion equivalents added
    n_ind: dict = field(default_factory=dict)
    path_factor: float = 1.0  # well-to-well optical path variation

    def add(self, comp: dict, vol_L: float) -> None:
        """Add vol_L of a solution whose composition is given in mol/L."""
        self.vol_L += vol_L
        self.n_P += comp.get("P", 0.0) * vol_L
        self.n_S += comp.get("S", 0.0) * vol_L
        self.n_B += comp.get("B", 0.0) * vol_L
        self.n_Na += comp.get("Na", 0.0) * vol_L
        self.n_X += comp.get("X", 0.0) * vol_L
        for name in INDICATORS:
            if comp.get(name, 0.0):
                self.n_ind[name] = self.n_ind.get(name, 0.0) + comp[name] * vol_L

    def add_moles(self, acid_mol: float = 0.0, base_mol: float = 0.0) -> None:
        self.n_X += acid_mol
        self.n_Na += base_mol

    def conc(self, n: float) -> float:
        return n / self.vol_L if self.vol_L > 0 else 0.0

    def ph(self) -> float:
        if self.vol_L <= 0:
            return 7.0
        P, S, B = self.conc(self.n_P), self.conc(self.n_S), self.conc(self.n_B)
        ka_b = 10 ** -PKA_BORATE
        Na, X = self.conc(self.n_Na), self.conc(self.n_X)
        inds = {k: self.conc(v) for k, v in self.n_ind.items()}
        ka = [10 ** -p for p in PKA_PHOS]
        ka_s = 10 ** -PKA_HSO4

        def imbalance(h: float) -> float:
            d0 = h ** 3
            d1 = h ** 2 * ka[0]
            d2 = h * ka[0] * ka[1]
            d3 = ka[0] * ka[1] * ka[2]
            den = d0 + d1 + d2 + d3
            nbar_p = (d1 + 2 * d2 + 3 * d3) / den
            nbar_s = (h + 2 * ka_s) / (h + ka_s)
            ind_charge = 0.0
            for name, c in inds.items():
                ka_i = 10 ** -INDICATORS[name]["pKa"]
                ind_charge += c * (1.0 + ka_i / (h + ka_i))
            borate = B * ka_b / (h + ka_b)
            return Na + h - KW / h - P * nbar_p - S * nbar_s - borate - ind_charge - X

        lo, hi = -14.0, 0.0     # log10(h); imbalance increases with h
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if imbalance(10 ** mid) > 0:
                hi = mid
            else:
                lo = mid
        return -0.5 * (lo + hi)

    def base_fraction(self, name: str) -> float:
        return 1.0 / (1.0 + 10 ** (INDICATORS[name]["pKa"] - self.ph()))

    def absorbance_rgb(self) -> np.ndarray:
        depth_cm = (self.vol_L * 1000.0) / WELL_AREA_CM2 * self.path_factor
        a = np.full(3, 0.015)  # plastic and meniscus background
        if self.vol_L <= 0:
            return a
        ph = self.ph()
        for name, n in self.n_ind.items():
            c = n / self.vol_L
            fb = 1.0 / (1.0 + 10 ** (INDICATORS[name]["pKa"] - ph))
            eps = fb * np.array(INDICATORS[name]["base_rgb"]) + (1 - fb) * np.array(INDICATORS[name]["acid_rgb"])
            a = a + eps * c * depth_cm
        return a

    def absorbance_spectrum(self, wl_nm: np.ndarray) -> np.ndarray:
        depth_cm = (self.vol_L * 1000.0) / WELL_AREA_CM2 * self.path_factor
        a = np.full_like(wl_nm, 0.015, dtype=float)
        if self.vol_L <= 0:
            return a
        ph = self.ph()
        for name, n in self.n_ind.items():
            c = n / self.vol_L
            d = INDICATORS[name]
            fb = 1.0 / (1.0 + 10 ** (d["pKa"] - ph))
            for frac, (mu, sig, emax) in ((fb, d["base_peak"]), (1 - fb, d["acid_peak"])):
                a = a + frac * emax * np.exp(-0.5 * ((wl_nm - mu) / sig) ** 2) * c * depth_cm
        return a


# Media and reagents, concentrations in mol/L. Phosphate buffer at pH 7.6 is
# 71% Na2HPO4 + 29% NaH2PO4, so sodium = 1.71 x phosphate.
def medium(phos_mM: float = 1.0, sulfate_mM: float = 50.0, btb_uM: float = 40.0, pr_uM: float = 0.0,
           base_mM: float = 0.0, borate_mM: float = 0.0) -> dict:
    """borate_mM is total boron from dissolved borax, which self-buffers at pH 9.2 (Na = B/2)."""
    P = phos_mM * 1e-3
    B = borate_mM * 1e-3
    S = sulfate_mM * 1e-3
    btb, pr = btb_uM * 1e-6, pr_uM * 1e-6
    return {"P": P, "S": S, "B": B, "BTB": btb, "PR": pr,
            "Na": 2 * S + 1.71 * P + 0.5 * B + btb + pr + base_mM * 1e-3}


REAGENTS = {
    "acidA": {"X": 0.020},                 # 20 mM sodium bisulfate, as strong-acid equivalents
    "acid10": {"X": 0.010},                # 10 mM sodium bisulfate standard
    "baseB": {"Na": 0.020},                # balanced carbonate input, as strong-base equivalents
    "water": {},
    "acid_ref": {"X": 0.200},              # reference well acid
    "base_ref": {"Na": 0.100},             # reference well base
}


# ---------------------------------------------------------------------------
# Plate, camera and spectral sensor
# ---------------------------------------------------------------------------
class SimPlate:
    def __init__(self, rng: np.random.Generator):
        self.rng = rng
        self.wells = {w: Well(path_factor=float(1 + rng.normal(0, 0.015))) for w in ALL_WELLS}
        self.lamp = 1.0

    def reset(self) -> None:
        for w in ALL_WELLS:
            self.wells[w] = Well(path_factor=float(1 + self.rng.normal(0, 0.015)))

    def fill(self, pos: str, comp: dict, vol_mL: float) -> None:
        self.wells[pos].add(comp, vol_mL * 1e-3)

    def add(self, pos: str, reagent: str | dict, vol_uL: float, pipette_cv: float = 0.01) -> None:
        comp = REAGENTS[reagent] if isinstance(reagent, str) else reagent
        actual = vol_uL * (1 + self.rng.normal(0, pipette_cv))
        self.wells[pos].add(comp, actual * 1e-6)


def _srgb_encode(lin: np.ndarray) -> np.ndarray:
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


class SimCamera:
    """Produces the same 8-bit sRGB ROI means a real webcam would, so the real
    absorbance pipeline (camera.rgb_to_absorbance) is what gets tested."""

    def __init__(self, plate: SimPlate, rng: np.random.Generator, exposure: float = 0.85, noise: float = 0.6):
        self.plate, self.rng = plate, rng
        self.exposure, self.noise = exposure, noise
        self.white_balance = np.array([1.0, 1.0, 1.0])

    def read_rgb(self) -> dict:
        out = {}
        lamp = self.plate.lamp * self.exposure
        white_lin = np.full(3, lamp) * self.white_balance
        for pos, well in self.plate.wells.items():
            t = 10 ** (-well.absorbance_rgb())
            lin = white_lin * t
            code = _srgb_encode(lin) * 255 + self.rng.normal(0, self.noise, 3)
            out[pos] = np.clip(np.round(code), 0, 255)
        ref = _srgb_encode(white_lin) * 255 + self.rng.normal(0, self.noise, 3)
        out["WHITE"] = np.clip(np.round(ref), 0, 255)
        return out


class SimSpectral:
    """AS7341 through a fiber looking down one well, LED on/off differential."""

    def __init__(self, plate: SimPlate, rng: np.random.Generator):
        self.plate, self.rng = plate, rng
        self.covered = False

    def read(self, pos: str, led: bool = True) -> np.ndarray:
        wl = np.array(AS7341_BANDS_NM, dtype=float)
        t = 10 ** (-self.plate.wells[pos].absorbance_spectrum(wl))
        led_spec = 1800.0 * np.exp(-0.5 * ((wl - 560) / 120) ** 2) if led else np.zeros_like(wl)
        ambient = 0.0 if self.covered else 250.0 * (1 + 0.2 * self.rng.normal())
        counts = led_spec * t * 0.9 + ambient * t + 40.0 + self.rng.normal(0, 4.0, wl.size)
        return np.clip(counts, 0, 65535)


# ---------------------------------------------------------------------------
# Controller twin (same API as the serial link)
# ---------------------------------------------------------------------------
class SimController:
    def __init__(self, plate: SimPlate, electrode_wells: list[str], rng: np.random.Generator,
                 efficiency: float = 0.90):
        self.plate, self.rng = plate, rng
        self.electrode_wells = electrode_wells
        self.eff = efficiency
        self.eff_drift_per_write = 2.0e-4
        self.btb_loss_per_write = 1.0e-4
        self.writes = 0
        self.energy_J = 0.0
        self.supply_V = 9.0
        self.diode_state = 0.0
        self.spectral = SimSpectral(plate, rng)
        self.temp_C = 21.5

    def ping(self) -> dict:
        return {"ok": True, "fw": "wetstack-sim", "ads1": True, "ads2": True, "as7341": True, "ina219": True}

    def relay_test(self) -> dict:
        return {"ok": True, "interlock": "PASS", "channels": 8}

    def _current_A(self) -> float:
        r_total = 470 + 100 + 1800 * (1 + self.rng.normal(0, 0.03))
        return max(0.0, (self.supply_V - 2.6) / r_total)

    def dose(self, well_index: int, mode: str, charge_mC: float, max_s: float = 300) -> dict:
        pos = self.electrode_wells[well_index - 1]
        well = self.plate.wells[pos]
        i_a = self._current_A()
        delivered_C = abs(charge_mC) * 1e-3 * (1 + self.rng.normal(0, 0.003))
        duration = delivered_C / i_a if i_a > 0 else 0.0
        if duration > max_s:
            delivered_C, duration = i_a * max_s, max_s
        eff = max(0.5, self.eff * (1 - self.eff_drift_per_write * self.writes)) * (1 + self.rng.normal(0, 0.01))
        mol = eff * delivered_C / F
        if mode.upper() == "ACID":
            well.add_moles(acid_mol=mol)
        else:
            well.add_moles(base_mol=mol)
        for name in list(well.n_ind):
            well.n_ind[name] *= (1 - self.btb_loss_per_write)
        self.writes += 1
        self.energy_J += self.supply_V * i_a * duration / 0.85 + 0.075 * 3 * duration
        return {"ok": True, "well": well_index, "mode": mode.upper(), "target_mC": charge_mC,
                "delivered_mC": round(delivered_C * 1e3, 4), "duration_s": round(duration, 3),
                "mean_mA": round(i_a * 1e3, 4), "peak_mA": round(i_a * 1.05e3, 4), "overrange": False}

    def mix(self, seconds: float, duty: int = 100) -> dict:
        self.energy_J += 0.25 * seconds * duty / 100
        return {"ok": True, "mixed_s": seconds}

    def spec(self, well_index: int = 1, diff: bool = True) -> dict:
        pos = self.electrode_wells[well_index - 1]
        on = self.spectral.read(pos, led=True)
        off = self.spectral.read(pos, led=False)
        return {"ok": True, "bands_nm": list(AS7341_BANDS_NM), "on": on.tolist(), "off": off.tolist(),
                "diff": (on - off).tolist() if diff else on.tolist()}

    def temp(self) -> dict:
        self.temp_C += self.rng.normal(0, 0.02)
        return {"ok": True, "temp_C": round(self.temp_C, 3)}

    def power(self) -> dict:
        return {"ok": True, "bus_V": 3.9, "current_mA": 110.0, "power_mW": 429.0}

    def safe(self) -> dict:
        return {"ok": True}

    # Bipolar hydrogel diode with a first-order memory state
    def iv(self, vmin: float, vmax: float, step: float, dwell_ms: int, device: str = "diode") -> list[dict]:
        rows = []
        n = int(round((vmax - vmin) / step)) + 1
        for k in range(n):
            v = vmin + k * step
            rows.append(self._diode_point(v, dwell_ms / 1000.0, device))
        return rows

    def _diode_point(self, v: float, dt: float, device: str) -> dict:
        if device == "control":
            g_f = g_r = 32e-6
        else:
            g_f, g_r = 42e-6 * (1 + self.rng.normal(0, 0.05)), 15e-6 * (1 + self.rng.normal(0, 0.05))
        target = 1.0 / (1.0 + math.exp(-v / 0.35))
        tau = 3.0
        self.diode_state += (target - self.diode_state) * (1 - math.exp(-dt / tau))
        g = g_r + (g_f - g_r) * self.diode_state
        r_sense = 1000.0
        i = v / (1.0 / g + r_sense)
        i *= (1 + self.rng.normal(0, 0.01))
        v_cell = v - i * r_sense
        return {"v_set": round(v, 4), "v_cell": round(v_cell, 5), "i_uA": round(i * 1e6, 4)}

    def sine(self, freq_hz: float, amp_v: float, cycles: int, device: str = "diode") -> list[dict]:
        rows, dt = [], 0.05
        steps = int(cycles / freq_hz / dt)
        self.diode_state = 0.5
        for k in range(steps):
            v = amp_v * math.sin(2 * math.pi * freq_hz * k * dt)
            rows.append(self._diode_point(v, dt, device))
        return rows


class SimBench:
    """Everything a --sim experiment needs, sharing one random stream."""

    def __init__(self, electrode_wells: list[str], seed: int = 7):
        self.rng = np.random.default_rng(seed)
        self.plate = SimPlate(self.rng)
        self.camera = SimCamera(self.plate, self.rng)
        self.ctl = SimController(self.plate, electrode_wells, self.rng)


# ---------------------------------------------------------------------------
# Solar session model
# ---------------------------------------------------------------------------
def solar_session(hours: float, writes_target: int, rng: np.random.Generator, panel_W: float = 6.0,
                  battery_Wh: float = 9.0, idle_W: float = 0.45, write_J: float = 2.0) -> dict:
    dt_h = 1 / 60
    soc = 0.8 * battery_Wh
    writes, brownouts, energy_load = 0, 0, 0.0
    per_min_writes = writes_target / (hours * 60)
    acc = 0.0
    for k in range(int(hours * 60)):
        sun = max(0.0, math.sin(math.pi * (k / (hours * 60)) * 0.8 + 0.4)) * (0.55 + 0.1 * rng.normal())
        harvest = panel_W * max(0.0, sun) * 0.75 * dt_h
        acc += per_min_writes
        n_now = int(acc)
        acc -= n_now
        load = idle_W * dt_h + n_now * write_J / 3600
        soc = min(battery_Wh, soc + harvest - load)
        energy_load += load
        if soc <= 0.05 * battery_Wh:
            brownouts += 1
            soc = 0.05 * battery_Wh
        else:
            writes += n_now
    return {"solar_hours": hours, "writes": writes, "brownouts": brownouts,
            "j_per_write": round(write_J, 3), "load_Wh": round(energy_load, 3), "end_soc_Wh": round(soc, 3)}
