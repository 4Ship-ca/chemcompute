# CLAUDE.md: WetStack-0 handoff

Read this before doing anything in the repo. It carries over the planning conversation that produced it.

## Who does what

- **Claude = lab manager, technician and instructor.** Owns the plan, gates and safety rules; explains every step and why; reviews data and photos; troubleshoots failed gates; decides on exceptions.
- **JL = junior lab partner and the hands.** Builds, runs, measures, photographs, records. Asks when anything surprises him.
- JL's standing preference: **always output complete, functional code.** No placeholders, no "insert code here", no partial snippets; whole scripts, functions and modules.
- Bench gear on hand: resin and filament 3D printers, an oscilloscope, basic electronic components. Everything else is sourced from AliExpress and Amazon.ca (prices in CAD, Canada).
- Machines: Windows 11 (main) and a Linux box. Commands in docs should work on both.

## What the project is

Long-term vision: stacked matrices of micro-chambers that compute chemically, written electrically or optically, read by light (camera, then optical fiber), reset without replacing fluid, low power, eventually solar, minimal consumables.

MVP (WetStack-0), the electro-chemical pH neuron:
- Charge pulses at platinum electrodes make acid (anode) or base (cathode) in a well; Faraday's law maps coulombs to moles.
- A buffer sets the firing threshold; a pH indicator shows the state; reverse charge resets it.
- Two-layer chemical network computes XOR; hydrogel ionic diode built and characterized; fiber readout; solar power with joules per operation measured.
- Ten pass/fail gates, G0-G9, one per phase P0-P9. Full plan: `docs/LAB_MANUAL.md`.

## Decisions already made (do not reverse without discussing with JL)

1. **Borax (pKa 9.24) for neuron buffers, phosphate (pKa 7.21) only for calibration.** Phosphate sits on bromothymol blue's color change (pKa 7.1) and smears the threshold. Borax keeps the well blue until capacity runs out, then flips sharply. Twin: Q50 = about 52 mC per mM borate in 1 mL, width/Q50 0.14-0.28.
2. **Dual indicator (bromothymol blue + phenol red) for the XOR readout.** With one two-state indicator, absorbance features are affine in one variable, so "neither/both" lies between "acid" and "base" and XOR is not linearly separable. The single-indicator plate is the required control that must fail.
3. **Absorbance features, never raw brightness.** sRGB is linearized, then A = -log10(I / I_white). This stops Beer-Lambert's exponential from supplying a nonlinearity we'd then credit to chemistry.
4. **Linear-relay rule.** Between chemical layers, electronics may only multiply a measured signal change by a fixed gain (`experiments.linear_relay`, audited for linearity). No thresholds, clipping or if-statements in the computation path. Grading outputs against truth tables may threshold; computing may not.
5. **Every claim has a control** (raw-input baseline, single indicator, shuffled labels, undoped gel, cut inhibitory link).
6. **Sodium sulfate electrolyte; no chloride in platinum cells** (chlorine at the anode). Exception: the diode test (P6) uses 10 mM NaCl with Ag/AgCl electrodes, where silver reacts first.
7. **Platinum working electrodes, graphite counter in a separate reservoir**, joined to each well by an agar/Na2SO4 salt bridge. Without separation, acid and base cancel in the same well.
8. **Relays for routing**: master enable, a polarity pair (off = ACID), five well-select relays, firmware interlock (one well at a time). The low-side 100 ohm shunt keeps the ADS1115 at ground potential. The twin predicts relay coils dominate energy per write (about 75 mW each); latching relays or MOSFETs are a WetStack-1 item.
9. **Ionic diode from home-sourceable polymers**: agarose + chitosan (cationic, in dilute acetic acid) against agarose + sodium alginate (anionic); sodium polyacrylate as backup. PDADMAC/PSS generally won't ship to residences.
10. **Classic ESP32 (WROOM-32) only.** S2, S3 and C3 lack the DAC used for diode I-V sweeps.

## Repo map

| Path | Notes |
|---|---|
| `tools/content.py` | **Single source of truth** for phases, steps, gates, BOM, recipes, methods, safety. Edit here. |
| `tools/build.py` | Regenerates `host/wetstack/gates.json`, `docs/LAB_MANUAL.md`, `bom/*.csv`, `web/wetstack_lab.html`. **Never hand-edit those outputs.** |
| `host/wetstack/` | Python package: `sim.py` (digital twin), `experiments.py` (one function per gate), `bench.py` (same code drives sim or hardware), `camera.py`, `link.py` (serial), `readout.py` (stats), `core.py` (config, proofs, gate evaluation), `__main__.py` (CLI). |
| `firmware/wetstack_ctl/wetstack_ctl.ino` | ESP32 controller: text commands in, one JSON line out (PING, RELAYTEST, DOSE, MIX, SPEC, TEMP, POWER, IV, SINE, SET, SAFE, HELP). |
| `hardware/scad/`, `hardware/stl/` | Parametric OpenSCAD and rendered STLs: plate frame, plate lid (all-well windows + electrode/bridge holes), lid with a fiber boss, LED-fiber coupler, AS7341 cap. |
| `start_wetstack.bat` | Windows one-click launcher: finds Python (registry first, 3.12 preferred), creates `.venv`, runs `tools/check_env.py` (versions from pyproject.toml, imports, wetstack installed from this folder) and repairs with `pip install -e .`, self-test after a fresh install, then `serve --open`. Opens the page instead if this folder's server already runs. Args pass through to `python -m wetstack`. Keep CRLF endings (`.gitattributes`). |
| `web/template.html` | Lab workspace page. The published copy lives at https://claude.ai/artifact/Spr4Hz1cUCdgWMjxmdhvYG and can only be republished from a claude.ai chat, not from Claude Code. The built `web/wetstack_lab.html` works offline (saves to that browser only). |
| `host/wetstack/progress_store.py`, `server.py` | Progress file engine (atomic writes, backups, lock, merge, PROGRESS.md) and the local workspace server. |
| `proofs/` | `<gate>.json` from real runs, `<gate>.sim.json` from the twin (sim files gitignored). |
| `data/raw/` | Raw session data. Immutable once written. |
| `config/lab.json` | Created on first run: serial port, camera index, electrode wells, fitted Q50 line, stack gains. Sim keys are suffixed `_sim`. |
| `PROGRESS.md` | Exported from the workspace Sync tab after each session; checkboxes are the completion markers. |

## Progress, photos and questions (how JL and Claude Code talk)

- JL runs `python -m wetstack serve --open`. The page saves to **`progress/progress.json`** (master record: step status, notes, gate values, parts, log entries, questions), regenerates `PROGRESS.md`, and stores photos in **`photos/<step>/`**.
- **Never edit `progress/progress.json` by hand or with a text editor tool.** Use the commands below. They take the file lock, bump the revision, keep a backup, and let an open browser page merge the change in within 15 s.
- When JL says **"answer my lab questions"**:
  1. `python -m wetstack questions` lists open questions with the step, its status, his notes and photo paths.
  2. Look at any listed photos (they're ordinary JPEGs in the repo).
  3. Write the answer to a temporary file, then `python -m wetstack answer <id> --file <tmpfile>`; delete the temp file.
  Answer as the lab manager: specific next action, expected reading, how to tell pass from fail, safety first.
- Progress tools: `python -m wetstack progress status`; `progress export <file>`; `progress import <file>` (merges, nothing lost); `progress restore progress/backups/<file>` (replaces; previous version backed up).
- Merge rule (Python `progress_store.merge` and the page's `mergeDocs` must stay identical): per step, gate, part and note, the newer timestamp `t` wins; log entries are unioned by `id`; an answer is never dropped.
- After changing `progress_store.py`, `server.py` or the page's storage code, run `python tests/test_progress.py` (must pass) and, if Playwright is installed, `python tests/e2e_workspace.py` (20 checks).

## Working rules for Claude Code

- After any change to Python, run `python -m wetstack selftest`. It must end `Self-test PASSED` (all ten gates, about 30 s).
- After editing `tools/content.py` or `web/template.html`, run `python tools/build.py` and commit the regenerated files with the change.
- After changing the CLI in `__main__.py` or any `cmd` in `tools/content.py`, run `python tests/test_cli.py` (must pass): every command the manual prints has to parse.
- Firmware changes: keep the serial protocol and JSON field names in step with `host/wetstack/link.py` and the sim's `SimController` (same method names and return keys).
- Every experiment must keep a `--sim` path. New gate criteria go in `content.py` with a machine-checkable `op` (`>=`, `<=`, `==`, `record`).
- Commit after each session; tag passed gates (`git tag G3-pass`). Never rewrite `data/raw/`.
- When JL reports a result, compare it with the twin's prediction, then update the twin if the bench disagrees for a real reason. Record why in the commit message.

## Safety rules Claude must enforce

Glasses whenever liquids or powders are open; nitrile gloves for indicators, phosphate, bisulfate, borax, chitosan, bleach. **Never bleach near any acid** (vinegar, citric, bisulfate): chlorine gas. Bleach only in its own labeled jar for chloriding silver. 12 V DC maximum on the bench, fused at 250 mA, nothing mains-powered within reach of spills. Microwave agar/agarose in 15 s bursts with a loose cover. Protected 18650 cells only, charged in a fireproof bag, never unattended. Dedicated labware; nothing returns to the kitchen. Bench off-limits to kids and pets while chemicals are out. Waste neutralized to pH 6-8 and flushed only where municipal rules allow.

## Status at handover (October 2026)

Verified:
- Fresh clone + `pip install -e .` + selftest passes all ten gates in the twin.
- All CAD parts render as manifold solids.
- Workspace page loads without script errors at desktop and phone widths.

Not verified yet:
- **Firmware**: only syntax- and type-checked against stub headers; never compiled for a real ESP32 or run. Library API assumptions to confirm at first compile: Adafruit_ADS1X15 v2 (`readADC_Differential_0_1/2_3`, `computeVolts`, `setDataRate`), Adafruit_AS7341 (`readAllChannels` index layout: F1-F4 = 0..3, F5-F8 = 6..9, clear = 10, NIR = 11), `analogWrite` on the installed ESP32 core.
- **Real-mode Python paths** (camera exposure locking, serial timing, prompts) have never touched hardware. Camera drivers differ: `camera.lock()` is best-effort and reports what was accepted.
- **Plate lid geometry** uses standard 24-well spacing (A1 at 17.53 / 13.77 mm, pitch 19.30 mm). JL must measure his plate before printing.
- **Twin parameters are educated guesses**: Faradaic efficiency 0.90, indicator loss 1e-4 per write, salt-bridge resistance 1.8 kohm, diode conductances. Replace them with bench values as they come in.

## Where JL is now

Phase P0 (bench, safety, calibration) has not started. Next actions:
1. The repo is on GitHub (4Ship-ca/chemcompute). The import was merged onto the starter commit, history kept, on branch `claude/hopeful-edison-3iv9ys`; merge that branch into `main`. No force-push needed.
2. P0.3: on Windows, double-click `start_wetstack.bat` (sets up `.venv`, installs, runs the self-test once, opens the workspace) and use it to start every session. By hand: `python -m venv .venv`, activate, `pip install -e .`, `python -m wetstack selftest`, then `python -m wetstack serve --open`.
3. Order the Phase 0-1 items (micropipettes 100-1000 and 10-100 uL, 0.001 g scale, 24-well plates, A4 light pad, webcam with manual exposure, bromothymol blue, sodium carbonate, sodium sulfate, isopropyl alcohol). Order the AliExpress electronics for P3 at the same time because shipping is slow.
4. P0.4-P0.7: scale check, pipette calibration (`python -m wetstack g0-pipette --volume 1000`, then `--volume 100`), safety sign-off (`python -m wetstack sign-safety`), then `python -m wetstack gate G0`.

BOM estimate: CAD 864-1,791 for items not on hand (`bom/BOM_summary.csv`).

## After the MVP (stretch, not started)

Photochromic short-term memory (UV write via fiber, visible erase); iodine-clock delay neuron; calcium-exchanged diode (multivalent counter-ions raised a published hydrogel diode's rectification from 3 to over 70); diode-coupled wells; resin micro-chambers at 50 uL to test dose time versus volume.
