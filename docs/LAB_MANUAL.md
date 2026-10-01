# WetStack-0 lab manual

_A home-lab chemical neuron: electrons in, chemistry decides, light out._

Generated from tools/content.py by tools/build.py. The web workspace (web/wetstack_lab.html) shows the same content with progress tracking.

## MVP definition

- Electrical inputs (charge pulses) write acid or base into at least 3 micro-chambers.
- The chemistry, not software, supplies every nonlinearity (buffer threshold + indicator speciation).
- Chambers are read optically by camera and by optical fiber into a spectral sensor.
- Chambers reset electrically for 100+ cycles with no fluid replaced.
- A two-layer chemical network computes XOR at 95% or better over 40+ randomized trials, with electronics allowed only to scale signals between layers (the linear-relay rule).
- An ionic diode junction is built and characterized (rectification ratio 2 or better).
- The electronics run from solar, and joules per chemical operation are measured.

## Working principles

- **Linear-relay rule.** Between chemical layers, electronics may only multiply a measured signal by a fixed gain. No thresholds, no if-statements, no clipping in software. Every decision must happen in a well.
- **Absorbance, not brightness.** Readout features are absorbances (log of light ratio), so Beer-Lambert's exponential cannot sneak in a nonlinearity. Any separability we claim belongs to the chemistry.
- **Every claim has a control.** Each positive result is paired with a run that should fail (single indicator, raw inputs, shuffled labels, undoped gel). If the control passes too, the claim does not stand.
- **Simulate first, then wet.** Every experiment runs against the digital twin with --sim before a drop of liquid is used. The sim is also the reference you compare real data against.
- **Gates are pass/fail.** You do not start a phase until the previous gate passes or I sign off on a documented exception.

## Roles

- **Lab manager (Claude):** Sets the plan, the gates and the safety rules; reviews data and photos; decides on exceptions.
- **Technician / instructor (Claude):** Explains each step and why; troubleshoots failed gates with you.
- **Lab partner (you):** Builds, runs, measures, photographs and records. You stop and ask when anything surprises you.

## (a) Path to MVP

Which physical route gets a home lab to a working, honest chemical-compute MVP fastest and safest?

| Option | Safety at home (x3) | Cost (x2) | Speed per op (x1) | Reversible (low consumables) (x3) | Easy to observe (x2) | Fits the long-term vision (x2) | Weighted |
|---|---|---|---|---|---|---|---|
| Electro-chemical pH neuron (chosen) | 5 | 5 | 3 | 5 | 5 | 4 | 61 |
| DNA strand displacement | 5 | 1 | 1 | 2 | 3 | 4 | 38 |
| Belousov-Zhabotinsky oscillators | 2 | 4 | 4 | 3 | 5 | 4 | 45 |
| Lipid droplet synapses | 4 | 3 | 4 | 3 | 2 | 5 | 45 |
| Living neurons / organoids | 1 | 1 | 4 | 2 | 2 | 5 | 29 |
| Pure reservoir in a stirred vat | 5 | 5 | 2 | 2 | 4 | 2 | 45 |

Scores are 1 (poor) to 5 (best).

- **Electro-chemical pH neuron (chosen):** Charge pulses make acid or base at a platinum electrode; a buffer sets the firing threshold; an indicator shows the state; reverse charge resets it. Cheap, safe, reversible, visible.
- **DNA strand displacement:** Elegant and programmable, but custom DNA strands cost hundreds per design and reactions take hours.
- **Belousov-Zhabotinsky oscillators:** Real excitable medium, but uses strong acid and bromate. Not a first home build.
- **Lipid droplet synapses:** Closest to biology, but needs picoamp electrophysiology and fragile membranes.
- **Living neurons / organoids:** Needs a cell-culture lab. Out of scope for a home bench.
- **Pure reservoir in a stirred vat:** Works (Huck lab, Nature 2024) but has no spatial structure to grow into stacked layers.

**Decision:** Electro-chemical pH neuron, read optically, with an ionic-diode junction as the first inter-chamber element.

- It is the smallest system that has all five parts of your vision: input, threshold, state, readout, reset.
- Faraday's law makes the input exact: charge in coulombs maps to moles of acid, so we can reason quantitatively.
- Reverse charge undoes a write, which attacks the consumables problem from day one.
- Everything upgrades in place: the salt bridge becomes a diode, the camera becomes a fiber, the wall plug becomes the sun.

## (b) Architecture

A PC orchestrates an ESP32 controller. The controller writes charge into chosen wells of a 24-well plate through platinum electrodes; every well connects to one shared counter-electrode reservoir through its own salt bridge. Each well holds an electrolyte, a phosphate buffer and a pH indicator. A camera above a light pad reads every well at once; later, fibers read single wells into a spectral sensor. Analysis and the trained readout run in Python on the PC.

| Layer | Hardware | Role |
|---|---|---|
| L0 Host | PC (Linux or Windows), Python 3.10+ | Runs experiments, camera capture, digital twin, analysis, proofs; git holds everything. |
| L1 Controller | ESP32 DevKit V1 (classic WROOM-32) | Relays, coulomb counting (ADS1115), spectral reads (AS7341), DAC sweeps for diode I-V, temperature, power. |
| L2 Electro-fluidic | 24-well plate, printed lid, Pt working electrodes, agar salt bridges, counter reservoir | Delivers charge into a well and closes the circuit through ions, not wires. |
| L3 Chemistry | 50 mM sodium sulfate + borax (neurons) or phosphate (calibration) + bromothymol blue (+ phenol red) | Buffer = threshold, indicator = output, electrode charge = weighted input. |
| L4 Optics | LED light pad, webcam with locked exposure, PMMA fiber + AS7341 | Absorbance per well per color channel; fiber reaches wells a camera cannot see. |
| L5 Power | 9 V adapter, then 6 V solar panel + 18650 + boost converters | Energy per operation measured with an INA219. |

Signal flow: Input bits -> Charge doses (mC) -> H+ or OH- (Faraday's law) -> Buffer absorbs until capacity runs out -> Indicator flips color past the threshold -> Camera / fiber absorbance -> Linear readout or linear relay to the next layer

### Pin map

| Pin | Function | Connects to |
|---|---|---|
| GPIO21 / GPIO22 | I2C SDA / SCL | ADS1115 #1 (0x48, shunt), ADS1115 #2 (0x49, diode I-V), AS7341 (0x39), INA219 (0x40) |
| GPIO25 / GPIO26 | DAC1 / DAC2 | Diode cell drive, differential: V = DAC1 - DAC2 |
| GPIO16 | Relay CH1 | Master enable (connects +9 V through the 470 ohm limit resistor) |
| GPIO17 | Relay CH2 + CH3 (both IN pins) | Polarity pair. Off = ACID write (well electrode is anode). On = BASE write. |
| GPIO18, 19, 23, 32, 33 | Relay CH4..CH8 | Well select W1..W5 (only one on at a time, enforced in firmware) |
| GPIO13 | MOSFET module #1 | Vibration mixer (coin motor on the plate frame) |
| GPIO14 | MOSFET module #2 | External fiber LED for differential spectral reads |
| GPIO4 | OneWire + 4.7 kohm pull-up to 3.3 V | DS18B20 temperature probe in the counter reservoir |
| GPIO2 | On-board LED | Busy indicator |

### Wiring notes

- Relay board: remove the JD-VCC jumper. Feed VCC (optocoupler side) from 3.3 V and JD-VCC (coils) from 5 V. Otherwise a 3.3 V HIGH may not turn a channel fully off.
- Polarity pair from two SPDT relays: Relay A COM to the working bus, A-NC to the supply node S, A-NO to the return node R. Relay B COM to the counter electrode, B-NC to R, B-NO to S.
- Each well relay: COM to the working bus, NO to that well's platinum electrode.
- Return node R goes through the 100 ohm shunt to ground. ADS1115 #1 reads A0 (top of shunt) minus A1 (ground). The shunt never leaves ground potential, so the ADC is always safe.
- Put a 250 mA fuse right after the 9 V adapter. Liquids and power share a bench; the fuse is not optional.
- Diode cell: DAC1 to a 1 kohm sense resistor to electrode A; electrode B to DAC2. ADS1115 #2 reads A0-A1 across the resistor and A2-A3 across the cell.

### Design decisions

- **24-well plate before custom chambers.** Standard footprint, clear bottoms, cheap. Custom resin chambers come after the chemistry works.
- **Platinum working electrodes.** Graphite flakes and steel dissolves when used as an anode; both would contaminate the optics. Graphite is fine for the counter electrode, which sits in a separate reservoir.
- **Sodium sulfate electrolyte, never chloride.** Chloride at an anode makes chlorine. Sulfate is inert and safe.
- **Shared counter reservoir via salt bridges.** Without separating the counter electrode, the acid and base you make cancel inside the same well.
- **Relays, not transistors, for routing.** Slow is fine (doses take seconds); relays isolate completely and forgive wiring mistakes.
- **Bromothymol blue for neurons, plus phenol red for XOR.** One indicator gives a clean threshold. Two indicators with different pKa give a curved color path, which a linear readout needs for XOR.
- **Borax buffer for neurons, phosphate for calibration.** Borax buffers near pH 9.2, well above the indicator's color change at 7.1, so the well stays blue until the buffer is used up and then flips sharply. Phosphate (pKa 7.2) sits on the color change and smooths it, which is what we want for calibration and not for thresholds.
- **Webcam first, fiber second.** The camera reads all wells at once to develop the chemistry; fiber is the upgrade for buried layers.

## (c) Materials

Full lists with search terms: bom/BOM_electronics.csv, bom/BOM_equipment.csv, bom/BOM_materials.csv.

| Group | Estimate (CAD) |
|---|---|
| consumable | 134-262 |
| electronics | 130-293 |
| equipment | 333-691 |
| material | 267-545 |
| **Total, items not on hand** | **864-1791** |

Spend by phase (order just ahead of each phase):

| Phase | Estimate (CAD) |
|---|---|
| P0 | 233-489 |
| P1 | 226-455 |
| P2 | 58-108 |
| P3 | 108-228 |
| P4 | 6-14 |
| P6 | 98-197 |
| P7 | 41-102 |
| P8 | 64-137 |
| Stretch | 30-61 |

Prices are late-2026 estimates from typical AliExpress and Amazon.ca listings; verify at purchase.

### Recipes

- **100 mM phosphate, pH 7.6 (100 mL).** 7.1 mmol disodium phosphate + 2.9 mmol monosodium phosphate, water to 100 mL. Masses by the form on your label: Na2HPO4 anhydrous 1.01 g, dihydrate 1.26 g, heptahydrate 1.90 g, dodecahydrate 2.54 g; NaH2PO4 anhydrous 0.35 g, monohydrate 0.40 g, dihydrate 0.45 g. Check with the pH meter; nudge with drops of carbonate or bisulfate.
- **Cell medium (per 100 mL).** 0.71 g sodium sulfate (50 mM), phosphate stock for the buffer level you need (1 mL per 1 mM), 6.25 mL bromothymol blue stock (40 uM), water to 100 mL. Used for calibration (P3).
- **100 mM borate stock (100 mL).** 0.953 g borax (sodium tetraborate decahydrate) in water to 100 mL. It buffers itself at pH 9.2; no adjustment needed. Gloves; do not ingest.
- **Neuron medium (per 100 mL).** 0.71 g sodium sulfate, borate stock for the level you need (1 mL per 1 mM total borate), 6.25 mL bromothymol blue stock, water to 100 mL. Deep blue at the start.
- **Bromothymol blue stock 0.4 mg/mL.** 40 mg in 5 mL isopropyl alcohol, + 90 mL water, carbonate drops until blue-green, to 100 mL.
- **Phenol red stock 0.2 mg/mL.** 20 mg in 5 mL isopropyl alcohol, + 90 mL water, carbonate drops until red, to 100 mL.
- **Salt bridge gel.** 2 g agar in 100 mL of 0.25 M sodium sulfate (3.55 g anhydrous). Heat until clear.
- **Counter reservoir.** 100 mL of 0.25 M sodium sulfate in a beaker, graphite rod, temperature probe.
- **Reference wells.** A1: cell medium + 50 uL of 200 mM bisulfate (pH about 4). A2: cell medium + 50 uL of 0.1 M carbonate (pH about 9.5).

## (d) Methods

- **Session IDs.** Every bench session gets an ID like 20261005-a. Raw files go to data/raw/<session>/ and are never edited.
- **Randomized layouts.** The scripts assign which well gets which condition. You follow the printed map. This stops position effects from faking a result.
- **Reference wells.** Wells A1 (acid reference, pH 4) and A2 (base reference, pH 9.5) sit on every plate. Each read is normalized to them, which cancels lamp and camera drift.
- **Replicates.** Minimum three repeats for any calibration point; 48 wells for classification claims; 40 trials for the stack.
- **Statistics.** Accuracy with a 95% Wilson interval; 1000-shuffle permutation test for classification; logistic fits for thresholds; R-squared for calibrations.
- **Controls.** Raw-input linear baseline, single-indicator control, shuffled labels, undoped gel, reverse polarity. Listed per gate.
- **Temperature.** Log reservoir temperature on every run. Indicator pKa shifts with temperature; a 5 C change is visible.
- **Version control.** Commit after every session (the workspace's Commit button does it). Tag each passed gate (git tag G3-pass). Proof JSON files live in proofs/.
- **Progress records.** progress/progress.json in the repo is the master record, written by python -m wetstack serve. Every save is atomic and keeps a backup in progress/backups/. If two writers collide, items merge by timestamp; nothing is dropped. PROGRESS.md is regenerated from it on every save.
- **Photos.** Photograph every build step and every gate result, and upload it to the step in the workspace.
- **When a gate fails.** Stop. Record the numbers. Work the troubleshooting list for that gate. Ask in the workspace with your data attached before changing two things at once.

### Safety

- **Eyes.** Safety glasses on whenever liquids or powders are open. UV glasses for any 365 nm LED work.
- **Hands.** Nitrile gloves for indicators, phosphate, bisulfate, chitosan and bleach.
- **Never mix bleach with acid.** Bleach is used only to coat silver wire, in its own labeled jar, rinsed off before the wire touches anything else. Bleach plus acid (including vinegar, citric acid, sodium bisulfate) releases chlorine gas.
- **No chloride in electrolysis cells.** Sodium sulfate only in the platinum cells. Chloride at a platinum anode makes chlorine. The one exception is the diode test (P6), where Ag/AgCl electrodes need dilute salt and the silver reacts first.
- **Low voltage only.** 12 V DC maximum on the bench, fused at 250 mA. No mains-powered device sits where a spill can reach it.
- **Electrolysis gas.** Currents are a few milliamps, so hydrogen and oxygen volumes are tiny. Keep the area ventilated and never seal a running cell airtight.
- **Hot agar and agarose.** Microwave in 15 s bursts with a loose cover; superheated gel can boil over. Use heat-resistant gloves.
- **Lithium cells.** Protected 18650 cells from a reputable seller only. Charge in a fireproof bag, never unattended.
- **Kitchen separation.** Dedicated labware only. Nothing from the lab returns to food use. Label every bottle with contents, concentration and date.
- **Waste.** Neutralize to pH 6-8 and flush small indicator and salt solutions with plenty of water, if your municipal rules allow. Silver and gel waste go to solid waste in a sealed bag.
- **Kids and pets.** The bench is off-limits when chemicals are out. Store stocks closed and high.

Every experiment command accepts --sim to run against the digital twin in host/wetstack/sim.py: phosphate buffer equilibria, indicator speciation, Faraday dosing with efficiency, camera absorbance noise, a gel-diode model and a power model. Run it before every wet session so you know what a good result looks like.

## Phases, gates and steps

### P0 Bench, safety and calibration (Week 1)

**Goal.** A safe, calibrated, documented bench and a working software environment.

**Why.** Every later number depends on pipette volumes, a clean bench and the digital twin running. Ten careful hours here save weeks.

- [ ] **P0.1 Inventory against the BOM.** Open the BOM tab. Mark each item Have, Ordered or Need. Photograph your on-hand electronics and printers. (photo)
- [ ] **P0.2 Set up the bench.** Choose a surface away from food prep. Lay the silicone mat or spill tray. Place the waste jar, wash bottle of distilled water, gloves and glasses within reach. Photograph the bench. (photo)
- [ ] **P0.3 Install the software.** Unzip the repo (or clone your GitHub copy). In a terminal at the repo root: python -m venv .venv, activate it (Windows: .venv\Scripts\activate, Linux: source .venv/bin/activate), then pip install -e . and run the full digital twin. It takes about a minute and must end with Self-test PASSED. From then on, start every session with python -m wetstack serve --open: the workspace opens in your browser and saves into progress/progress.json in the repo. `python -m wetstack selftest --sim`
- [ ] **P0.4 Check the scale.** Weigh the calibration weight that came with the scale three times. All three readings should be within 0.005 g of the stated value. Tare between readings.
- [ ] **P0.5 Calibrate the 1000 uL pipette.** Set 1000 uL. Tare a small beaker. Dispense distilled water ten times, recording the scale after each (1 mg equals 1 uL at room temperature). Enter the ten cumulative readings when the script asks. `python -m wetstack g0-pipette --volume 1000`
- [ ] **P0.6 Calibrate the 100 uL pipette.** Same method at 100 uL, ten dispenses. `python -m wetstack g0-pipette --volume 100`
- [ ] **P0.7 Read the safety rules and sign off.** Read the Safety tab top to bottom. Tick this step only when every rule is set up physically (bleach jar labeled, fuse on hand, glasses at the bench).

**Gate G0: Bench certified** (`python -m wetstack gate G0`)

| Criterion | Target |
|---|---|
| 1000 uL mean error | <= 3 % |
| 1000 uL repeatability (CV) | <= 2 % |
| 100 uL mean error | <= 3 % |
| 100 uL repeatability (CV) | <= 2 % |
| Digital twin self-test passes | == 1  |
| Safety rules set up and signed | == 1  |

If it fails:

- Pipette error high: pre-wet the tip twice, dispense against the beaker wall, hold the pipette vertical, check the tip seats fully.
- Error still high but CV low: the pipette is consistently off; use the measured factor as a correction in config/lab.json.
- Self-test fails: run python -m wetstack selftest --sim --verbose and paste the output into Ask.

Achievement: **Bench certified**

### P1 Eyes: the optical readout bench (Weeks 1-2)

**Goal.** Read the color of every well reliably as absorbance.

**Why.** If the readout drifts or saturates, no chemistry result can be trusted. We prove the eyes before we trust what they see.

- **H1.** With locked exposure and reference-well normalization, red-channel absorbance of a bromothymol blue dilution series in base is linear in concentration (Beer-Lambert), and repeated reads vary by under 2%. _Pass:_ R-squared >= 0.98; repeat CV <= 2%; 10-minute drift <= 1%. _Control:_ A water-only well reads under 0.05 absorbance (the plastic and meniscus).

- [ ] **P1.1 Print the plate frame.** Measure your 24-well plate with calipers (outer length and width, well pitch, A1 center offset). Enter them at the top of hardware/scad/plate_frame.scad and plate_lid.scad. Print the frame in PETG, 0.2 mm layers. (photo)
- [ ] **P1.2 Build the light station.** Light pad flat on the bench, frame taped onto it, camera on the overhead arm about 30 cm above, lens centered over the plate. Surround with black foam board so room light cannot reach the plate. Photograph it. (photo)
- [ ] **P1.3 Lock the camera.** Run the camera tool. It tries to turn off auto exposure, auto white balance and autofocus. If your camera ignores it, set those manually in the camera app (Windows: Logitech G HUB or the Camera app's pro mode; Linux: v4l2-ctl or guvcview), then rerun. `python -m wetstack camera --lock --preview`
- [ ] **P1.4 Mark the wells.** Put the empty plate in the frame. Click the center of each well A1 to D6 in order, then click a bare spot of the light pad as the white reference. ROIs save to config/rois.json. `python -m wetstack calibrate-rois`
- [ ] **P1.5 Make the bromothymol blue stock (0.4 mg/mL).** Gloves and glasses. Weigh 40 mg bromothymol blue. Dissolve in 5 mL isopropyl alcohol in a small beaker. Add 90 mL distilled water. Add 0.1 M sodium carbonate drop by drop, swirling, until the solution turns blue-green. Top up to 100 mL. Label it and store it dark. (photo)
- [ ] **P1.6 Make 0.1 M sodium carbonate.** 1.06 g anhydrous sodium carbonate (or 2.86 g of the decahydrate washing-soda crystals) in water to 100 mL. Label it.
- [ ] **P1.7 Run the dilution series.** The script prints a randomized map: six concentrations of indicator (0 to 100 uM) in 1 mL of 10 mM sodium carbonate, three wells each, plus water blanks. Pipette to the map, place the plate, press Enter. `python -m wetstack g1-linearity`
- [ ] **P1.8 Stability run.** Leave the plate in place. The script reads every minute for 10 minutes and reports drift. `python -m wetstack g1-linearity --stability`

**Gate G1: First light** (`python -m wetstack gate G1`)

| Criterion | Target |
|---|---|
| Dilution series linearity (R-squared) | >= 0.98  |
| Repeat-read variation (CV) | <= 2 % |
| Drift over 10 minutes | <= 1 % |
| Water blank absorbance (plastic + meniscus) | <= 0.05  |

If it fails:

- Curve bends over at high concentration: the camera is saturating or the light pad is too bright. Dim the pad or shorten exposure.
- High CV: auto exposure is still on, or the plate moves. Re-lock and tape the frame.
- Drift: the light pad is warming up. Switch it on 15 minutes before reading.

Achievement: **First light**

### P2 First nonlinearity: manual XOR (Week 2)

**Goal.** Prove that indicator chemistry creates a nonlinearity a linear readout can use.

**Why.** This is the core claim of the whole project in its simplest form, done by hand before any electronics touch the liquid.

- **H2.** With two indicators of different pKa (bromothymol blue and phenol red), the absorbance features of a well separate XOR(acid, base) linearly. _Pass:_ Logistic regression on absorbance >= 95% accuracy (5-fold cross-validation, 48 wells); permutation p <= 0.01. _Control:_ The same classifier on the raw inputs reaches at most 75% (mathematical maximum for XOR). A bromothymol-blue-only plate also stays at or below 80%.

- [ ] **P2.1 Make the phenol red stock (0.2 mg/mL).** 20 mg phenol red in 5 mL isopropyl alcohol, add 90 mL water, a few drops of 0.1 M carbonate until red, top to 100 mL. If you bought a ready solution, note its concentration.
- [ ] **P2.2 Make the input stocks.** Acid A: 20 mM sodium bisulfate (0.24 g anhydrous NaHSO4 per 100 mL; check the pool product label says 93% or more). Base B: start at 20 mM sodium carbonate (0.212 g per 100 mL).
- [ ] **P2.3 Balance the inputs.** In one well: 1 mL medium (below) plus 50 uL A plus 50 uL B. If it is not the same green as a well with nothing added, adjust B's concentration and repeat. Record the final B concentration. Balanced inputs make 'both' look like 'neither', which is what makes the task XOR. (photo)
- [ ] **P2.4 Make the XOR medium.** Per 100 mL: 0.71 g sodium sulfate, 1 mL of 100 mM phosphate pH 7.6 (recipe in Materials), 6.25 mL bromothymol blue stock, 2.5 mL phenol red stock, water to 100 mL.
- [ ] **P2.5 Run the dual-indicator plates.** Two plates, 24 wells each, follow the randomized map. Each well gets 1 mL medium, then 50 uL A or water, then 50 uL B or water. Tap gently to mix, wait 2 minutes, read. `python -m wetstack g2-xor-manual --plates 2` (photo)
- [ ] **P2.6 Run the single-indicator control plate.** Same procedure with medium that has bromothymol blue only. This plate should fail. `python -m wetstack g2-xor-manual --plates 1 --control single-indicator`

**Gate G2: First XOR** (`python -m wetstack gate G2`)

| Criterion | Target |
|---|---|
| XOR accuracy, dual indicator | >= 0.95  |
| Raw-input linear baseline (must stay low) | <= 0.75  |
| Single-indicator control (must stay low) | <= 0.8  |
| Permutation test p-value | <= 0.01  |
| Wells in the dual-indicator set | >= 48  |

If it fails:

- Dual accuracy low because 'both' wells are not green: rebalance B (step P2.3).
- Single-indicator control passes: the classifier is using brightness, not absorbance. Check that you ran the current code.
- Accuracy low with clean colors: read too soon. Wait 5 minutes for CO2 bubbles to clear.

Achievement: **First XOR**

### P3 Electric write: the Faraday cell (Weeks 3-4)

**Goal.** Write chemistry with electrons, and prove that charge in maps to acid made.

**Why.** From here on, inputs are electrical. Faraday's law (96,485 coulombs per mole) is our calibration constant.

- **H3a.** Coulomb counting delivers the requested charge within 2%. _Pass:_ Mean absolute error <= 2% versus a multimeter in series. _Control:_ Zero-charge dose reads under 0.05 mC.
- **H3b.** Faradaic efficiency (acid made divided by charge/F) is at least 70% at the platinum anode in sulfate. _Pass:_ Efficiency >= 0.70, dose-response CV <= 5% over 3 repeats. _Control:_ Pipetted sodium bisulfate standards define the color-to-moles curve.

- [ ] **P3.1 Build the controller.** Breadboard first, following the pin map and wiring notes in the Architecture tab. Relay JD-VCC jumper removed. Fuse after the 9 V adapter. Photograph it before powering. (photo)
- [ ] **P3.2 Flash the firmware.** Arduino IDE 2.x: install the esp32 board package (Espressif), and libraries Adafruit ADS1X15, Adafruit AS7341, Adafruit INA219, OneWire, DallasTemperature. Open firmware/wetstack_ctl/wetstack_ctl.ino, select ESP32 Dev Module, upload. Then ping it. `python -m wetstack ping --port COM5`
- [ ] **P3.3 Dry test the relays.** No liquids. Run the relay test; you should hear each relay click in turn and see PASS for the interlock. `python -m wetstack relay-test`
- [ ] **P3.4 Print and fit the lid.** Print hardware/scad/plate_lid.scad in PETG with the wells you will use (default A3, A4, A5, A6, B3). Check every hole with the wire and tubing before going further. (photo)
- [ ] **P3.5 Make the electrodes.** Cut 5 platinum pieces of 18 mm. Crimp or tightly wrap each onto a copper lead, cover the joint with heat-shrink and a dab of epoxy so only platinum touches liquid. Push through the lid so 6 mm sits in the well. Counter electrode: a 2 mm graphite rod in the reservoir beaker. (photo)
- [ ] **P3.6 Verify the platinum.** Anodic test: one electrode in 50 mM sodium sulfate, 3 mA for 10 minutes. Real platinum stays bright and the liquid stays clear. Discoloration means the wire is fake; switch to graphite and tell me.
- [ ] **P3.7 Make salt bridges.** Heat 2 g agar in 100 mL of 0.25 M sodium sulfate (3.55 g) until clear. Draw into 2 mm silicone tubing with a syringe, no bubbles. Let set 20 minutes. Cut 70 mm lengths, bend into a U, one end in a well, one in the reservoir (100 mL beaker, 0.25 M sodium sulfate). (photo)
- [ ] **P3.8 Calibrate coulomb counting.** Multimeter in series on the mA range. Run doses of 5, 10, 20 and 40 mC into a well of plain sulfate; type the multimeter's steady current when asked. `python -m wetstack g3-faraday --charge-cal`
- [ ] **P3.9 Standards and dose response.** The script maps pipetted bisulfate standards (0-0.8 umol acid, 10 mM stock topped to 120 uL with water) and twelve 6 mC electrical doses in W1 (1 mL of 1 mM phosphate cell medium + 120 uL water), mixing 10 s after each dose. Efficiency is fitted only where the standards still change color. Three repeats; refill W1 between them. `python -m wetstack g3-faraday`

**Gate G3: First electric write** (`python -m wetstack gate G3`)

| Criterion | Target |
|---|---|
| Charge delivery error | <= 2 % |
| Faradaic efficiency | >= 0.7  |
| Dose-response repeatability (CV) | <= 5 % |

If it fails:

- Charge error high: the shunt is not 100 ohm. Measure it and set shunt_ohm in config/lab.json.
- Current far below 2 mA: a salt bridge has a bubble or dried out. Remake it.
- Low efficiency: dissolved oxygen is being reduced, or the platinum is fake. Run P3.6 again.
- Poor repeatability: mixing is incomplete. Increase mix time to 20 s or move the motor closer.

Achievement: **First electric write**

### P4 The chemical neuron: threshold and reset (Weeks 4-5)

**Goal.** Show that buffer sets a tunable firing threshold, and that reverse charge resets the well for 100+ cycles.

**Why.** A neuron is a weighted sum, a threshold and a reset. Charge is the weighted sum; buffer capacity is the threshold; reverse charge is the reset.

- **H4.** Response versus charge is sigmoidal, and its midpoint Q50 scales linearly with borax buffer concentration. _Pass:_ Q50 versus buffer R-squared >= 0.95 over 0.5, 1, 2 and 4 mM total borate; 10-90% width <= 40% of Q50. _Control:_ A well with no buffer fires at under 10% of the 1 mM Q50.
- **H5.** Writing acid then the same charge of base returns the well to baseline, with no fluid added, for 100 cycles. _Pass:_ Baseline absorbance shift <= 0.02 after reset; Q50 drift <= 10% from cycle 1 to 100. _Control:_ An unwritten neighbor well tracks background drift.

- [ ] **P4.1 Make neuron media.** Neuron medium (recipe in Materials) at 0, 0.5, 1, 2 and 4 mM total borate: 0, 0.5, 1, 2 and 4 mL of the 100 mM borate stock per 100 mL. The 0 mM control gets a trace of carbonate until blue-green.
- [ ] **P4.2 Threshold sweep.** One buffer level per electrode well, 1 mL each. The script doses in steps, mixes, reads, and fits a sigmoid per well. `python -m wetstack g4-threshold` (photo)
- [ ] **P4.3 Overnight reset run.** 1 mM borate well: 100 cycles of acid at 1.5 x Q50, read, equal base, read. Lid on to slow CO2 uptake. Check the bridge ends are submerged before you leave it. `python -m wetstack g4-reset --cycles 100`

**Gate G4: First chemical neuron** (`python -m wetstack gate G4`)

| Criterion | Target |
|---|---|
| Q50 vs buffer linearity | >= 0.95  |
| Threshold sharpness (width / Q50) | <= 0.4  |
| Baseline shift after reset | <= 0.02  |
| Q50 drift over the run | <= 10 % |
| Write/reset cycles completed | >= 100  |

If it fails:

- Thresholds not linear in borate: carbon dioxide from air is adding acid and buffer. Keep the lid on and use freshly made medium.
- Reset drifts acid-ward: the counter reservoir has drifted. Replace the reservoir solution (not the wells) and rerun.
- Indicator fades: bromothymol blue oxidizing at the anode. Lower current to 1.5 mA and report it.

Achievement: **First chemical neuron**

### P5 Logic and the first stack (Weeks 5-6)

**Goal.** Single chemical neurons compute AND and OR; a two-layer chemical network computes XOR.

**Why.** XOR is the classic task one threshold unit cannot do. Doing it with two layers of chemistry, relayed only linearly, is the MVP's headline proof.

- **H6a.** Buffer level alone turns one neuron into AND or OR. _Pass:_ Truth tables correct in 10 of 10 repeats each. _Control:_ Unbuffered well fires on any input (OR at best, never AND).
- **H6b.** OR neuron (excitatory) and AND neuron (inhibitory) feed an output neuron that computes XOR, with the relay purely linear. _Pass:_ XOR accuracy >= 95% over >= 40 randomized trials; relay code audited linear. _Control:_ Same network with the inhibitory link cut computes OR, not XOR.

- [ ] **P5.1 Find the AND and OR buffer levels.** From your G4 fits, the script proposes borate levels so one input dose crosses threshold (OR) or only two do (AND), and an output neuron level. Make those three media. `python -m wetstack g5-logic --plan`
- [ ] **P5.2 Truth tables.** Wells W1 = OR, W2 = AND. Each input row is dosed, mixed, read and reset, ten times. `python -m wetstack g5-logic --truth`
- [ ] **P5.3 Wire the stack.** W3 is the output neuron. Layer 2 dose = gain x layer-1 signal (acid for OR, base for AND). Gains are fixed after calibration and saved to config. `python -m wetstack g5-stack --calibrate`
- [ ] **P5.4 Run 40 randomized trials.** Expect about two hours. Photograph the plate at one trial of each input combination. `python -m wetstack g5-stack --trials 40` (photo)
- [ ] **P5.5 Cut-link control.** Same run with the AND-to-output gain set to zero. It should compute OR. `python -m wetstack g5-stack --trials 16 --cut-inhibition`

**Gate G5: First stack** (`python -m wetstack gate G5`)

| Criterion | Target |
|---|---|
| AND truth table accuracy | >= 1.0  |
| OR truth table accuracy | >= 1.0  |
| Stacked XOR accuracy | >= 0.95  |
| Randomized trials | >= 40  |
| Relay audited linear | == 1  |

If it fails:

- AND fires on one input: buffer too low; raise by 20%.
- XOR fails on input 1,1: inhibitory gain too small; it must be at least the excitatory gain.
- Errors cluster late in the run: reset ledger drift. Re-zero by running g4-reset --cycles 1 between blocks.

Achievement: **First stack**

### P6 Junctions: the ionic diode (Weeks 6-7)

**Goal.** Build a hydrogel junction that conducts ions better in one direction, from home-sourced polymers.

**Why.** Directional junctions are what let signals rise through stacked layers instead of echoing back.

- **H7.** A bipolar junction of cationic gel (agarose + chitosan) against anionic gel (agarose + alginate) rectifies ion current. _Pass:_ Median rectification ratio >= 2 at +/-2.5 V over 3 devices. _Control:_ Plain agarose tube: ratio <= 1.2.
- **H7b.** Under a slow sine drive the junction shows a pinched hysteresis loop (memory). _Pass:_ Visible pinched loop on the oscilloscope in X-Y mode at 0.1 Hz. _Control:_ 1 kohm resistor shows a straight line.

- [ ] **P6.1 Make Ag/AgCl electrodes.** In the labeled bleach jar only: 5 cm pieces of silver wire, 30 minutes in plain household bleach until dark purple-gray. Rinse well in distilled water. Never let bleach meet acid. (photo)
- [ ] **P6.2 Cationic gel.** Dissolve 1 g chitosan in 50 mL of 1% acetic acid (10 mL white vinegar + 40 mL water), stir until clear (hours; hotplate low). Mix 1:1 with hot 3% agarose in water to get 1.5% agarose / 1% chitosan.
- [ ] **P6.3 Anionic gel.** 1.5% agarose with 1% sodium alginate in water. Backup: swollen sodium polyacrylate paste.
- [ ] **P6.4 Cast three diode tubes and one control.** 40 mm of 3 mm silicone tube. Fill 20 mm with warm cationic gel by syringe, let set 10 minutes, then fill the rest with warm anionic gel pressed against it. Control: plain 1.5% agarose. Label the ends + (cationic) and - (anionic). (photo)
- [ ] **P6.5 I-V sweeps.** Each tube bridges two wells holding 10 mM table salt (58 mg non-iodized salt per 100 mL), one Ag/AgCl wire per well. Ag/AgCl needs chloride to work; silver reacts long before any chlorine could form at these voltages. 2 s dwell per step. `python -m wetstack g6-diode --devices 3 --control 1`
- [ ] **P6.6 Hysteresis on the scope.** Scope X on the cell voltage, Y across the 1 kohm sense resistor, X-Y mode. Run the sine drive and photograph the screen. `python -m wetstack g6-diode --sine 0.1` (photo)

**Gate G6: First diode** (`python -m wetstack gate G6`)

| Criterion | Target |
|---|---|
| Median rectification ratio | >= 2.0  |
| Plain-gel control ratio | <= 1.2  |
| Devices measured | >= 3  |

If it fails:

- Ratio near 1: the interface has an air gap. Recast pressing the second gel firmly against the first.
- Ratio drifts during the sweep: dwell too short; set 5 s.
- Still low: try the polyacrylate backup or the calcium exchange stretch step and tell me the numbers.

Achievement: **First diode**

### P7 Fiber eyes (Weeks 7-8)

**Goal.** Read a well through optical fiber into a spectral sensor as well as the camera does, including where the camera cannot see.

**Why.** Stacked layers bury chambers. Fiber is how we keep reading them.

- **H9.** LED-on minus LED-off fiber reads track camera absorbance across a dose sweep. _Pass:_ R-squared >= 0.95; with the plate covered, noise <= 3%. _Control:_ Fiber in an empty well reads constant.

- [ ] **P7.1 Print fiber parts.** hardware/scad/fiber_parts.scad: the lid with a center fiber port, the LED coupler and the sensor cap. Clear resin or PETG, fully cured and washed. (photo)
- [ ] **P7.2 Cut and polish fiber.** Cut 1 mm PMMA fiber with a fresh hot blade, polish each end on 2000-grit wet paper in figure-eights for 30 seconds.
- [ ] **P7.3 Assemble and read.** Light pad below, fiber tip 2 mm above the liquid, far end in the sensor cap on the AS7341. `python -m wetstack spec --diff`
- [ ] **P7.4 Dose sweep with both readers.** Camera and fiber read the same well through a dose sweep, then again with a dark cover over the plate (camera blinded). `python -m wetstack g7-fiber`

**Gate G7: Fiber eyes** (`python -m wetstack gate G7`)

| Criterion | Target |
|---|---|
| Fiber vs camera agreement | >= 0.95  |
| Fiber noise with camera blinded | <= 3 % |

If it fails:

- Weak signal: polish the fiber ends again, and raise AS7341 gain.
- Noisy: room light leaking; use the differential mode and the sensor cap.

Achievement: **Fiber eyes**

### P8 Sun power and energy per operation (Weeks 8-9)

**Goal.** Run the controller and dosing from sunlight and measure joules per chemical operation.

**Why.** Low power and minimal consumables were the goal from the start. This is where we put numbers on it.

- **H10.** A 6 V panel with a single 18650 buffer runs a 4-hour daylight session of 100+ writes without a brownout. _Pass:_ >= 4 h, >= 100 writes, 0 brownouts; joules per write recorded. _Control:_ Same session on the wall adapter gives the same dose accuracy.

- [ ] **P8.1 Build the power board.** Panel to CN3791 charger to protected 18650. Battery to INA219 to two MT3608 boosts: set one to 5.0 V (ESP32 5V pin) and one to 9.0 V (electrolysis supply) with the multimeter before connecting anything. (photo)
- [ ] **P8.2 Daylight session.** Panel in a window or outside in shade-free light. The script cycles the 1 mM neuron and logs power. `python -m wetstack g8-solar --hours 4`

**Gate G8: Sun-powered** (`python -m wetstack gate G8`)

| Criterion | Target |
|---|---|
| Session length | >= 4 h |
| Writes completed | >= 100  |
| Brownouts | == 0  |
| Energy per write | record J |

If it fails:

- Brownout at relay switching: add 470 uF across the 5 V rail.
- Energy per write dominated by relay coils (about 75 mW each while held): switch to latching relays or MOSFET routing for WetStack-1. The twin predicts this.
- Battery drains: panel too small for continuous dosing; lengthen idle time between writes.

Achievement: **Sun-powered**

### P9 MVP integration (Week 10)

**Goal.** Run the whole system in one demonstration and publish the report.

**Why.** Each gate proved a part. The MVP proves the parts work together.

- [ ] **P9.1 Full demo run.** Solar powered; stacked XOR with camera and fiber readout; the diode tube installed as W3's bridge; 20 trials. `python -m wetstack mvp-demo --trials 20` (photo)
- [ ] **P9.2 Generate the report.** Collects every proof file into docs/MVP_REPORT.md. Commit, then git tag v1.0-mvp. `python -m wetstack report`
- [ ] **P9.3 Debrief.** Upload the report and three photos to the workspace and ask for the lab-manager review. We plan WetStack-1 from what broke.

**Gate G9: MVP complete** (`python -m wetstack gate G9`)

| Criterion | Target |
|---|---|
| Gates G0-G8 passed | >= 9  |
| Integrated demo XOR accuracy | >= 0.9  |

If it fails:

- Integrated accuracy below the stack result: compare per-trial logs for the readout path that differs.

Achievement: **WetStack-0 MVP**

## Stretch goals

- **Photochromic short-term memory.** UV write (365 nm via fiber), visible erase, decay time measured. Craft photochromic pigment in clear epoxy. A memory that fades on its own, like short-term memory.
- **Delay neuron (iodine clock).** Vitamin C, iodine tincture, 3% peroxide, starch. Fires abruptly after a delay set by input dose: a timing element.
- **Calcium-exchanged diode.** Soak the anionic side in calcium chloride. Multivalent counter-ions raised a published hydrogel diode's ratio from 3 to over 70.
- **Diode-coupled wells.** Replace a salt bridge with a diode tube and show writes pass one way more easily than the other.
- **Resin micro-chambers.** 96 chambers at 50 uL in clear resin; measure how dose time shrinks with volume.
