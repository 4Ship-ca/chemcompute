# chemcompute: WetStack-0

A home-lab chemical neuron: electrons in, chemistry decides, light out.

Charge pulses at platinum electrodes write acid or base into micro-chambers. A borax buffer sets each
chamber's firing threshold, a pH indicator shows its state, a camera and optical fiber read it, and reverse
charge resets it with no fluid replaced. The MVP ends with a two-layer chemical network computing XOR,
an ionic hydrogel diode, fiber readout and solar power, each proven by a pass/fail gate.

**Lab workspace (progress, gates, parts, photos, ask the lab manager):**
https://claude.ai/artifact/Spr4Hz1cUCdgWMjxmdhvYG

## Quick start

```
python -m venv .venv
.venv\Scripts\activate          # Linux: source .venv/bin/activate
pip install -e .
python -m wetstack selftest     # every gate against the digital twin, about 30 s, must end PASSED
```

Every experiment command takes `--sim` so you can rehearse it before using liquids:

```
python -m wetstack g1-linearity --sim
python -m wetstack gate G1 --sim
```

## Layout

| Path | What it is |
|---|---|
| `docs/LAB_MANUAL.md` | The full plan: path, architecture, materials, methods, every phase, step and gate |
| `bom/` | Parts lists with CAD estimates and AliExpress / Amazon search terms |
| `host/wetstack/` | Python package: experiments, camera pipeline, statistics, serial link, digital twin |
| `firmware/wetstack_ctl/` | ESP32 controller firmware (Arduino IDE) |
| `hardware/scad/`, `hardware/stl/` | Parametric OpenSCAD parts and ready STLs (plate frame, lid, fiber couplers) |
| `proofs/` | Gate proof files written by the experiment commands |
| `data/raw/` | Raw session data, never edited |
| `config/lab.json` | Your bench settings (created on first run) |
| `tools/content.py` | Single source for the manual, BOM and workspace; rebuild with `python tools/build.py` |
| `web/` | Workspace page (offline copy works in any browser, saving to that browser only) |

## Status at handover

- Digital twin self-test: all ten gates pass.
- CAD: all parts render as manifold solids in OpenSCAD. Measure your plate and edit the parameters before printing the lid.
- Firmware: passes a syntax and type check against stub headers. It has not yet been compiled for a real ESP32; that is step P3.2.
- Real-bench results: none yet. That's your job.

## After each session

1. In the workspace, Sync tab: save `PROGRESS.md` and the progress JSON into the repo root.
2. `git add -A && git commit -m "session YYYYMMDD-x"`; tag passed gates (`git tag G1-pass`).
3. `git push --follow-tags`
