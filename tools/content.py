"""WetStack-0 curriculum: the single source of truth.

Everything the lab manual, the BOM CSVs and the web workspace show is
generated from this file by tools/build.py. Edit here, then rebuild.
"""

PROJECT = {
    "name": "WetStack-0",
    "tagline": "A home-lab chemical neuron: electrons in, chemistry decides, light out.",
    "version": "1.0",
    "mvp_definition": [
        "Electrical inputs (charge pulses) write acid or base into at least 3 micro-chambers.",
        "The chemistry, not software, supplies every nonlinearity (buffer threshold + indicator speciation).",
        "Chambers are read optically by camera and by optical fiber into a spectral sensor.",
        "Chambers reset electrically for 100+ cycles with no fluid replaced.",
        "A two-layer chemical network computes XOR at 95% or better over 40+ randomized trials, "
        "with electronics allowed only to scale signals between layers (the linear-relay rule).",
        "An ionic diode junction is built and characterized (rectification ratio 2 or better).",
        "The electronics run from solar, and joules per chemical operation are measured.",
    ],
    "principles": [
        ["Linear-relay rule",
         "Between chemical layers, electronics may only multiply a measured signal by a fixed gain. "
         "No thresholds, no if-statements, no clipping in software. Every decision must happen in a well."],
        ["Absorbance, not brightness",
         "Readout features are absorbances (log of light ratio), so Beer-Lambert's exponential cannot "
         "sneak in a nonlinearity. Any separability we claim belongs to the chemistry."],
        ["Every claim has a control",
         "Each positive result is paired with a run that should fail (single indicator, raw inputs, "
         "shuffled labels, undoped gel). If the control passes too, the claim does not stand."],
        ["Simulate first, then wet",
         "Every experiment runs against the digital twin with --sim before a drop of liquid is used. "
         "The sim is also the reference you compare real data against."],
        ["Gates are pass/fail",
         "You do not start a phase until the previous gate passes or I sign off on a documented exception."],
    ],
    "roles": [
        ["Lab manager (Claude)", "Sets the plan, the gates and the safety rules; reviews data and photos; decides on exceptions."],
        ["Technician / instructor (Claude)", "Explains each step and why; troubleshoots failed gates with you."],
        ["Lab partner (you)", "Builds, runs, measures, photographs and records. You stop and ask when anything surprises you."],
    ],
}

# ---------------------------------------------------------------------------
# (a) Path to MVP: decision matrix
# ---------------------------------------------------------------------------
PATH = {
    "question": "Which physical route gets a home lab to a working, honest chemical-compute MVP fastest and safest?",
    "criteria": ["Safety at home", "Cost", "Speed per op", "Reversible (low consumables)", "Easy to observe", "Fits the long-term vision"],
    "weights": [3, 2, 1, 3, 2, 2],
    "options": [
        {"name": "Electro-chemical pH neuron (chosen)", "scores": [5, 5, 3, 5, 5, 4],
         "note": "Charge pulses make acid or base at a platinum electrode; a buffer sets the firing threshold; "
                 "an indicator shows the state; reverse charge resets it. Cheap, safe, reversible, visible."},
        {"name": "DNA strand displacement", "scores": [5, 1, 1, 2, 3, 4],
         "note": "Elegant and programmable, but custom DNA strands cost hundreds per design and reactions take hours."},
        {"name": "Belousov-Zhabotinsky oscillators", "scores": [2, 4, 4, 3, 5, 4],
         "note": "Real excitable medium, but uses strong acid and bromate. Not a first home build."},
        {"name": "Lipid droplet synapses", "scores": [4, 3, 4, 3, 2, 5],
         "note": "Closest to biology, but needs picoamp electrophysiology and fragile membranes."},
        {"name": "Living neurons / organoids", "scores": [1, 1, 4, 2, 2, 5],
         "note": "Needs a cell-culture lab. Out of scope for a home bench."},
        {"name": "Pure reservoir in a stirred vat", "scores": [5, 5, 2, 2, 4, 2],
         "note": "Works (Huck lab, Nature 2024) but has no spatial structure to grow into stacked layers."},
    ],
    "decision": "Electro-chemical pH neuron, read optically, with an ionic-diode junction as the first inter-chamber element.",
    "why": [
        "It is the smallest system that has all five parts of your vision: input, threshold, state, readout, reset.",
        "Faraday's law makes the input exact: charge in coulombs maps to moles of acid, so we can reason quantitatively.",
        "Reverse charge undoes a write, which attacks the consumables problem from day one.",
        "Everything upgrades in place: the salt bridge becomes a diode, the camera becomes a fiber, the wall plug becomes the sun.",
    ],
}

# ---------------------------------------------------------------------------
# (b) Architecture
# ---------------------------------------------------------------------------
ARCHITECTURE = {
    "summary": (
        "A PC orchestrates an ESP32 controller. The controller writes charge into chosen wells of a 24-well plate "
        "through platinum electrodes; every well connects to one shared counter-electrode reservoir through its own "
        "salt bridge. Each well holds an electrolyte, a phosphate buffer and a pH indicator. A camera above a light "
        "pad reads every well at once; later, fibers read single wells into a spectral sensor. Analysis and the "
        "trained readout run in Python on the PC."
    ),
    "layers": [
        ["L0 Host", "PC (Linux or Windows), Python 3.10+", "Runs experiments, camera capture, digital twin, analysis, proofs; git holds everything."],
        ["L1 Controller", "ESP32 DevKit V1 (classic WROOM-32)", "Relays, coulomb counting (ADS1115), spectral reads (AS7341), DAC sweeps for diode I-V, temperature, power."],
        ["L2 Electro-fluidic", "24-well plate, printed lid, Pt working electrodes, agar salt bridges, counter reservoir", "Delivers charge into a well and closes the circuit through ions, not wires."],
        ["L3 Chemistry", "50 mM sodium sulfate + borax (neurons) or phosphate (calibration) + bromothymol blue (+ phenol red)", "Buffer = threshold, indicator = output, electrode charge = weighted input."],
        ["L4 Optics", "LED light pad, webcam with locked exposure, PMMA fiber + AS7341", "Absorbance per well per color channel; fiber reaches wells a camera cannot see."],
        ["L5 Power", "9 V adapter, then 6 V solar panel + 18650 + boost converters", "Energy per operation measured with an INA219."],
    ],
    "signal_flow": [
        "Input bits", "Charge doses (mC)", "H+ or OH- (Faraday's law)", "Buffer absorbs until capacity runs out",
        "Indicator flips color past the threshold", "Camera / fiber absorbance", "Linear readout or linear relay to the next layer",
    ],
    "pinmap": [
        ["GPIO21 / GPIO22", "I2C SDA / SCL", "ADS1115 #1 (0x48, shunt), ADS1115 #2 (0x49, diode I-V), AS7341 (0x39), INA219 (0x40)"],
        ["GPIO25 / GPIO26", "DAC1 / DAC2", "Diode cell drive, differential: V = DAC1 - DAC2"],
        ["GPIO16", "Relay CH1", "Master enable (connects +9 V through the 470 ohm limit resistor)"],
        ["GPIO17", "Relay CH2 + CH3 (both IN pins)", "Polarity pair. Off = ACID write (well electrode is anode). On = BASE write."],
        ["GPIO18, 19, 23, 32, 33", "Relay CH4..CH8", "Well select W1..W5 (only one on at a time, enforced in firmware)"],
        ["GPIO13", "MOSFET module #1", "Vibration mixer (coin motor on the plate frame)"],
        ["GPIO14", "MOSFET module #2", "External fiber LED for differential spectral reads"],
        ["GPIO4", "OneWire + 4.7 kohm pull-up to 3.3 V", "DS18B20 temperature probe in the counter reservoir"],
        ["GPIO2", "On-board LED", "Busy indicator"],
    ],
    "wiring_notes": [
        "Relay board: remove the JD-VCC jumper. Feed VCC (optocoupler side) from 3.3 V and JD-VCC (coils) from 5 V. "
        "Otherwise a 3.3 V HIGH may not turn a channel fully off.",
        "Polarity pair from two SPDT relays: Relay A COM to the working bus, A-NC to the supply node S, A-NO to the return node R. "
        "Relay B COM to the counter electrode, B-NC to R, B-NO to S.",
        "Each well relay: COM to the working bus, NO to that well's platinum electrode.",
        "Return node R goes through the 100 ohm shunt to ground. ADS1115 #1 reads A0 (top of shunt) minus A1 (ground). "
        "The shunt never leaves ground potential, so the ADC is always safe.",
        "Put a 250 mA fuse right after the 9 V adapter. Liquids and power share a bench; the fuse is not optional.",
        "Diode cell: DAC1 to a 1 kohm sense resistor to electrode A; electrode B to DAC2. ADS1115 #2 reads A0-A1 across the "
        "resistor and A2-A3 across the cell.",
    ],
    "decisions": [
        ["24-well plate before custom chambers", "Standard footprint, clear bottoms, cheap. Custom resin chambers come after the chemistry works."],
        ["Platinum working electrodes", "Graphite flakes and steel dissolves when used as an anode; both would contaminate the optics. "
                                        "Graphite is fine for the counter electrode, which sits in a separate reservoir."],
        ["Sodium sulfate electrolyte, never chloride", "Chloride at an anode makes chlorine. Sulfate is inert and safe."],
        ["Shared counter reservoir via salt bridges", "Without separating the counter electrode, the acid and base you make cancel inside the same well."],
        ["Relays, not transistors, for routing", "Slow is fine (doses take seconds); relays isolate completely and forgive wiring mistakes."],
        ["Bromothymol blue for neurons, plus phenol red for XOR", "One indicator gives a clean threshold. Two indicators with different pKa give a curved color path, which a linear readout needs for XOR."],
        ["Borax buffer for neurons, phosphate for calibration", "Borax buffers near pH 9.2, well above the indicator's color change at 7.1, so the well stays blue until the buffer is used up and then flips sharply. Phosphate (pKa 7.2) sits on the color change and smooths it, which is what we want for calibration and not for thresholds."],
        ["Webcam first, fiber second", "The camera reads all wells at once to develop the chemistry; fiber is the upgrade for buried layers."],
    ],
}

# ---------------------------------------------------------------------------
# (d) Methods and safety
# ---------------------------------------------------------------------------
METHODS = [
    ["Session IDs", "Every bench session gets an ID like 20261005-a. Raw files go to data/raw/<session>/ and are never edited."],
    ["Randomized layouts", "The scripts assign which well gets which condition. You follow the printed map. This stops position effects from faking a result."],
    ["Reference wells", "Wells A1 (acid reference, pH 4) and A2 (base reference, pH 9.5) sit on every plate. Each read is normalized to them, which cancels lamp and camera drift."],
    ["Replicates", "Minimum three repeats for any calibration point; 48 wells for classification claims; 40 trials for the stack."],
    ["Statistics", "Accuracy with a 95% Wilson interval; 1000-shuffle permutation test for classification; logistic fits for thresholds; R-squared for calibrations."],
    ["Controls", "Raw-input linear baseline, single-indicator control, shuffled labels, undoped gel, reverse polarity. Listed per gate."],
    ["Temperature", "Log reservoir temperature on every run. Indicator pKa shifts with temperature; a 5 C change is visible."],
    ["Version control", "Commit after every session (the workspace's Commit button does it). Tag each passed gate (git tag G3-pass). Proof JSON files live in proofs/."],
    ["Progress records", "progress/progress.json in the repo is the master record, written by python -m wetstack serve. Every save is atomic and keeps a backup in progress/backups/. If two writers collide, items merge by timestamp; nothing is dropped. PROGRESS.md is regenerated from it on every save."],
    ["Photos", "Photograph every build step and every gate result, and upload it to the step in the workspace."],
    ["When a gate fails", "Stop. Record the numbers. Work the troubleshooting list for that gate. Ask in the workspace with your data attached before changing two things at once."],
]

SAFETY = [
    ["Eyes", "Safety glasses on whenever liquids or powders are open. UV glasses for any 365 nm LED work."],
    ["Hands", "Nitrile gloves for indicators, phosphate, bisulfate, chitosan and bleach."],
    ["Never mix bleach with acid", "Bleach is used only to coat silver wire, in its own labeled jar, rinsed off before the wire touches anything else. Bleach plus acid (including vinegar, citric acid, sodium bisulfate) releases chlorine gas."],
    ["No chloride in electrolysis cells", "Sodium sulfate only in the platinum cells. Chloride at a platinum anode makes chlorine. The one exception is the diode test (P6), where Ag/AgCl electrodes need dilute salt and the silver reacts first."],
    ["Low voltage only", "12 V DC maximum on the bench, fused at 250 mA. No mains-powered device sits where a spill can reach it."],
    ["Electrolysis gas", "Currents are a few milliamps, so hydrogen and oxygen volumes are tiny. Keep the area ventilated and never seal a running cell airtight."],
    ["Hot agar and agarose", "Microwave in 15 s bursts with a loose cover; superheated gel can boil over. Use heat-resistant gloves."],
    ["Lithium cells", "Protected 18650 cells from a reputable seller only. Charge in a fireproof bag, never unattended."],
    ["Kitchen separation", "Dedicated labware only. Nothing from the lab returns to food use. Label every bottle with contents, concentration and date."],
    ["Waste", "Neutralize to pH 6-8 and flush small indicator and salt solutions with plenty of water, if your municipal rules allow. Silver and gel waste go to solid waste in a sealed bag."],
    ["Kids and pets", "The bench is off-limits when chemicals are out. Store stocks closed and high."],
]

# ---------------------------------------------------------------------------
# Phases. Gate criteria are machine-checkable: op is >=, <=, ==, or record.
# Proof JSON written by `python -m wetstack <gate>` uses the same keys.
# ---------------------------------------------------------------------------
PHASES = [
    {
        "id": "P0", "title": "Bench, safety and calibration", "weeks": "Week 1",
        "goal": "A safe, calibrated, documented bench and a working software environment.",
        "why": "Every later number depends on pipette volumes, a clean bench and the digital twin running. Ten careful hours here save weeks.",
        "hypotheses": [],
        "steps": [
            {"id": "P0.1", "title": "Inventory against the BOM",
             "detail": "Open the BOM tab. Mark each item Have, Ordered or Need. Photograph your on-hand electronics and printers.",
             "photo": True},
            {"id": "P0.2", "title": "Set up the bench",
             "detail": "Choose a surface away from food prep. Lay the silicone mat or spill tray. Place the waste jar, wash bottle of distilled water, gloves and glasses within reach. Photograph the bench.",
             "photo": True},
            {"id": "P0.3", "title": "Install the software",
             "detail": "Unzip the repo (or clone your GitHub copy). In a terminal at the repo root: python -m venv .venv, activate it (Windows: .venv\\Scripts\\activate, Linux: source .venv/bin/activate), then pip install -e . and run the full digital twin. It takes about a minute and must end with Self-test PASSED. From then on, start every session with python -m wetstack serve --open: the workspace opens in your browser and saves into progress/progress.json in the repo.",
             "cmd": "python -m wetstack selftest --sim"},
            {"id": "P0.4", "title": "Check the scale",
             "detail": "Weigh the calibration weight that came with the scale three times. All three readings should be within 0.005 g of the stated value. Tare between readings."},
            {"id": "P0.5", "title": "Calibrate the 1000 uL pipette",
             "detail": "Set 1000 uL. Tare a small beaker. Dispense distilled water ten times, recording the scale after each (1 mg equals 1 uL at room temperature). Enter the ten cumulative readings when the script asks.",
             "cmd": "python -m wetstack g0-pipette --volume 1000"},
            {"id": "P0.6", "title": "Calibrate the 100 uL pipette",
             "detail": "Same method at 100 uL, ten dispenses.",
             "cmd": "python -m wetstack g0-pipette --volume 100"},
            {"id": "P0.7", "title": "Read the safety rules and sign off",
             "detail": "Read the Safety tab top to bottom. Tick this step only when every rule is set up physically (bleach jar labeled, fuse on hand, glasses at the bench)."},
        ],
        "gate": {"id": "G0", "name": "Bench certified", "cmd": "python -m wetstack gate G0",
                 "criteria": [
                     {"key": "pip1000_err_pct", "label": "1000 uL mean error", "unit": "%", "op": "<=", "value": 3},
                     {"key": "pip1000_cv_pct", "label": "1000 uL repeatability (CV)", "unit": "%", "op": "<=", "value": 2},
                     {"key": "pip100_err_pct", "label": "100 uL mean error", "unit": "%", "op": "<=", "value": 3},
                     {"key": "pip100_cv_pct", "label": "100 uL repeatability (CV)", "unit": "%", "op": "<=", "value": 2},
                     {"key": "selftest_pass", "label": "Digital twin self-test passes", "unit": "", "op": "==", "value": 1},
                     {"key": "safety_signed", "label": "Safety rules set up and signed", "unit": "", "op": "==", "value": 1},
                 ],
                 "if_fail": [
                     "Pipette error high: pre-wet the tip twice, dispense against the beaker wall, hold the pipette vertical, check the tip seats fully.",
                     "Error still high but CV low: the pipette is consistently off; use the measured factor as a correction in config/lab.json.",
                     "Self-test fails: run python -m wetstack selftest --sim --verbose and paste the output into Ask.",
                 ]},
        "achievement": "Bench certified",
    },
    {
        "id": "P1", "title": "Eyes: the optical readout bench", "weeks": "Weeks 1-2",
        "goal": "Read the color of every well reliably as absorbance.",
        "why": "If the readout drifts or saturates, no chemistry result can be trusted. We prove the eyes before we trust what they see.",
        "hypotheses": [
            {"id": "H1", "text": "With locked exposure and reference-well normalization, red-channel absorbance of a bromothymol blue dilution series in base is linear in concentration (Beer-Lambert), and repeated reads vary by under 2%.",
             "pass": "R-squared >= 0.98; repeat CV <= 2%; 10-minute drift <= 1%.",
             "control": "A water-only well reads under 0.05 absorbance (the plastic and meniscus)."},
        ],
        "steps": [
            {"id": "P1.1", "title": "Print the plate frame",
             "detail": "Measure your 24-well plate with calipers (outer length and width, well pitch, A1 center offset). Enter them at the top of hardware/scad/plate_frame.scad and plate_lid.scad. Print the frame in PETG, 0.2 mm layers.",
             "photo": True},
            {"id": "P1.2", "title": "Build the light station",
             "detail": "Light pad flat on the bench, frame taped onto it, camera on the overhead arm about 30 cm above, lens centered over the plate. Surround with black foam board so room light cannot reach the plate. Photograph it.",
             "photo": True},
            {"id": "P1.3", "title": "Lock the camera",
             "detail": "Run the camera tool. It tries to turn off auto exposure, auto white balance and autofocus. If your camera ignores it, set those manually in the camera app (Windows: Logitech G HUB or the Camera app's pro mode; Linux: v4l2-ctl or guvcview), then rerun.",
             "cmd": "python -m wetstack camera --lock --preview"},
            {"id": "P1.4", "title": "Mark the wells",
             "detail": "Put the empty plate in the frame. Click the center of each well A1 to D6 in order, then click a bare spot of the light pad as the white reference. ROIs save to config/rois.json.",
             "cmd": "python -m wetstack calibrate-rois"},
            {"id": "P1.5", "title": "Make the bromothymol blue stock (0.4 mg/mL)",
             "detail": "Gloves and glasses. Weigh 40 mg bromothymol blue. Dissolve in 5 mL isopropyl alcohol in a small beaker. Add 90 mL distilled water. Add 0.1 M sodium carbonate drop by drop, swirling, until the solution turns blue-green. Top up to 100 mL. Label it and store it dark.",
             "photo": True},
            {"id": "P1.6", "title": "Make 0.1 M sodium carbonate",
             "detail": "1.06 g anhydrous sodium carbonate (or 2.86 g of the decahydrate washing-soda crystals) in water to 100 mL. Label it."},
            {"id": "P1.7", "title": "Run the dilution series",
             "detail": "The script prints a randomized map: six concentrations of indicator (0 to 100 uM) in 1 mL of 10 mM sodium carbonate, three wells each, plus water blanks. Pipette to the map, place the plate, press Enter.",
             "cmd": "python -m wetstack g1-linearity"},
            {"id": "P1.8", "title": "Stability run",
             "detail": "Leave the plate in place. The script reads every minute for 10 minutes and reports drift.",
             "cmd": "python -m wetstack g1-linearity --stability"},
        ],
        "gate": {"id": "G1", "name": "First light", "cmd": "python -m wetstack gate G1",
                 "criteria": [
                     {"key": "r2_dilution", "label": "Dilution series linearity (R-squared)", "unit": "", "op": ">=", "value": 0.98},
                     {"key": "read_cv_pct", "label": "Repeat-read variation (CV)", "unit": "%", "op": "<=", "value": 2},
                     {"key": "drift_pct_10min", "label": "Drift over 10 minutes", "unit": "%", "op": "<=", "value": 1},
                     {"key": "blank_abs", "label": "Water blank absorbance (plastic + meniscus)", "unit": "", "op": "<=", "value": 0.05},
                 ],
                 "if_fail": [
                     "Curve bends over at high concentration: the camera is saturating or the light pad is too bright. Dim the pad or shorten exposure.",
                     "High CV: auto exposure is still on, or the plate moves. Re-lock and tape the frame.",
                     "Drift: the light pad is warming up. Switch it on 15 minutes before reading.",
                 ]},
        "achievement": "First light",
    },
    {
        "id": "P2", "title": "First nonlinearity: manual XOR", "weeks": "Week 2",
        "goal": "Prove that indicator chemistry creates a nonlinearity a linear readout can use.",
        "why": "This is the core claim of the whole project in its simplest form, done by hand before any electronics touch the liquid.",
        "hypotheses": [
            {"id": "H2", "text": "With two indicators of different pKa (bromothymol blue and phenol red), the absorbance features of a well separate XOR(acid, base) linearly.",
             "pass": "Logistic regression on absorbance >= 95% accuracy (5-fold cross-validation, 48 wells); permutation p <= 0.01.",
             "control": "The same classifier on the raw inputs reaches at most 75% (mathematical maximum for XOR). A bromothymol-blue-only plate also stays at or below 80%."},
        ],
        "steps": [
            {"id": "P2.1", "title": "Make the phenol red stock (0.2 mg/mL)",
             "detail": "20 mg phenol red in 5 mL isopropyl alcohol, add 90 mL water, a few drops of 0.1 M carbonate until red, top to 100 mL. If you bought a ready solution, note its concentration."},
            {"id": "P2.2", "title": "Make the input stocks",
             "detail": "Acid A: 20 mM sodium bisulfate (0.24 g anhydrous NaHSO4 per 100 mL; check the pool product label says 93% or more). Base B: start at 20 mM sodium carbonate (0.212 g per 100 mL)."},
            {"id": "P2.3", "title": "Balance the inputs",
             "detail": "In one well: 1 mL medium (below) plus 50 uL A plus 50 uL B. If it is not the same green as a well with nothing added, adjust B's concentration and repeat. Record the final B concentration. Balanced inputs make 'both' look like 'neither', which is what makes the task XOR.",
             "photo": True},
            {"id": "P2.4", "title": "Make the XOR medium",
             "detail": "Per 100 mL: 0.71 g sodium sulfate, 1 mL of 100 mM phosphate pH 7.6 (recipe in Materials), 6.25 mL bromothymol blue stock, 2.5 mL phenol red stock, water to 100 mL."},
            {"id": "P2.5", "title": "Run the dual-indicator plates",
             "detail": "Two plates, 24 wells each, follow the randomized map. Each well gets 1 mL medium, then 50 uL A or water, then 50 uL B or water. Tap gently to mix, wait 2 minutes, read.",
             "cmd": "python -m wetstack g2-xor-manual --plates 2", "photo": True},
            {"id": "P2.6", "title": "Run the single-indicator control plate",
             "detail": "Same procedure with medium that has bromothymol blue only. This plate should fail.",
             "cmd": "python -m wetstack g2-xor-manual --plates 1 --control single-indicator"},
        ],
        "gate": {"id": "G2", "name": "First XOR", "cmd": "python -m wetstack gate G2",
                 "criteria": [
                     {"key": "xor_acc_dual", "label": "XOR accuracy, dual indicator", "unit": "", "op": ">=", "value": 0.95},
                     {"key": "xor_acc_raw_linear", "label": "Raw-input linear baseline (must stay low)", "unit": "", "op": "<=", "value": 0.75},
                     {"key": "xor_acc_single", "label": "Single-indicator control (must stay low)", "unit": "", "op": "<=", "value": 0.80},
                     {"key": "perm_p", "label": "Permutation test p-value", "unit": "", "op": "<=", "value": 0.01},
                     {"key": "n_wells", "label": "Wells in the dual-indicator set", "unit": "", "op": ">=", "value": 48},
                 ],
                 "if_fail": [
                     "Dual accuracy low because 'both' wells are not green: rebalance B (step P2.3).",
                     "Single-indicator control passes: the classifier is using brightness, not absorbance. Check that you ran the current code.",
                     "Accuracy low with clean colors: read too soon. Wait 5 minutes for CO2 bubbles to clear.",
                 ]},
        "achievement": "First XOR",
    },
    {
        "id": "P3", "title": "Electric write: the Faraday cell", "weeks": "Weeks 3-4",
        "goal": "Write chemistry with electrons, and prove that charge in maps to acid made.",
        "why": "From here on, inputs are electrical. Faraday's law (96,485 coulombs per mole) is our calibration constant.",
        "hypotheses": [
            {"id": "H3a", "text": "Coulomb counting delivers the requested charge within 2%.",
             "pass": "Mean absolute error <= 2% versus a multimeter in series.", "control": "Zero-charge dose reads under 0.05 mC."},
            {"id": "H3b", "text": "Faradaic efficiency (acid made divided by charge/F) is at least 70% at the platinum anode in sulfate.",
             "pass": "Efficiency >= 0.70, dose-response CV <= 5% over 3 repeats.", "control": "Pipetted sodium bisulfate standards define the color-to-moles curve."},
        ],
        "steps": [
            {"id": "P3.1", "title": "Build the controller",
             "detail": "Breadboard first, following the pin map and wiring notes in the Architecture tab. Relay JD-VCC jumper removed. Fuse after the 9 V adapter. Photograph it before powering.",
             "photo": True},
            {"id": "P3.2", "title": "Flash the firmware",
             "detail": "Arduino IDE 2.x: install the esp32 board package (Espressif), and libraries Adafruit ADS1X15, Adafruit AS7341, Adafruit INA219, OneWire, DallasTemperature. Open firmware/wetstack_ctl/wetstack_ctl.ino, select ESP32 Dev Module, upload. Then ping it.",
             "cmd": "python -m wetstack ping --port COM5"},
            {"id": "P3.3", "title": "Dry test the relays",
             "detail": "No liquids. Run the relay test; you should hear each relay click in turn and see PASS for the interlock.",
             "cmd": "python -m wetstack relay-test"},
            {"id": "P3.4", "title": "Print and fit the lid",
             "detail": "Print hardware/scad/plate_lid.scad in PETG with the wells you will use (default A3, A4, A5, A6, B3). Check every hole with the wire and tubing before going further.",
             "photo": True},
            {"id": "P3.5", "title": "Make the electrodes",
             "detail": "Cut 5 platinum pieces of 18 mm. Crimp or tightly wrap each onto a copper lead, cover the joint with heat-shrink and a dab of epoxy so only platinum touches liquid. Push through the lid so 6 mm sits in the well. Counter electrode: a 2 mm graphite rod in the reservoir beaker.",
             "photo": True},
            {"id": "P3.6", "title": "Verify the platinum",
             "detail": "Anodic test: one electrode in 50 mM sodium sulfate, 3 mA for 10 minutes. Real platinum stays bright and the liquid stays clear. Discoloration means the wire is fake; switch to graphite and tell me."},
            {"id": "P3.7", "title": "Make salt bridges",
             "detail": "Heat 2 g agar in 100 mL of 0.25 M sodium sulfate (3.55 g) until clear. Draw into 2 mm silicone tubing with a syringe, no bubbles. Let set 20 minutes. Cut 70 mm lengths, bend into a U, one end in a well, one in the reservoir (100 mL beaker, 0.25 M sodium sulfate).",
             "photo": True},
            {"id": "P3.8", "title": "Calibrate coulomb counting",
             "detail": "Multimeter in series on the mA range. Run doses of 5, 10, 20 and 40 mC into a well of plain sulfate; type the multimeter's steady current when asked.",
             "cmd": "python -m wetstack g3-faraday --charge-cal"},
            {"id": "P3.9", "title": "Standards and dose response",
             "detail": "The script maps pipetted bisulfate standards (0-0.8 umol acid, 10 mM stock topped to 120 uL with water) and twelve 6 mC electrical doses in W1 (1 mL of 1 mM phosphate cell medium + 120 uL water), mixing 10 s after each dose. Efficiency is fitted only where the standards still change color. Three repeats; refill W1 between them.",
             "cmd": "python -m wetstack g3-faraday"},
        ],
        "gate": {"id": "G3", "name": "First electric write", "cmd": "python -m wetstack gate G3",
                 "criteria": [
                     {"key": "charge_err_pct", "label": "Charge delivery error", "unit": "%", "op": "<=", "value": 2},
                     {"key": "faradaic_eff", "label": "Faradaic efficiency", "unit": "", "op": ">=", "value": 0.70},
                     {"key": "dose_cv_pct", "label": "Dose-response repeatability (CV)", "unit": "%", "op": "<=", "value": 5},
                 ],
                 "if_fail": [
                     "Charge error high: the shunt is not 100 ohm. Measure it and set shunt_ohm in config/lab.json.",
                     "Current far below 2 mA: a salt bridge has a bubble or dried out. Remake it.",
                     "Low efficiency: dissolved oxygen is being reduced, or the platinum is fake. Run P3.6 again.",
                     "Poor repeatability: mixing is incomplete. Increase mix time to 20 s or move the motor closer.",
                 ]},
        "achievement": "First electric write",
    },
    {
        "id": "P4", "title": "The chemical neuron: threshold and reset", "weeks": "Weeks 4-5",
        "goal": "Show that buffer sets a tunable firing threshold, and that reverse charge resets the well for 100+ cycles.",
        "why": "A neuron is a weighted sum, a threshold and a reset. Charge is the weighted sum; buffer capacity is the threshold; reverse charge is the reset.",
        "hypotheses": [
            {"id": "H4", "text": "Response versus charge is sigmoidal, and its midpoint Q50 scales linearly with borax buffer concentration.",
             "pass": "Q50 versus buffer R-squared >= 0.95 over 0.5, 1, 2 and 4 mM total borate; 10-90% width <= 40% of Q50.",
             "control": "A well with no buffer fires at under 10% of the 1 mM Q50."},
            {"id": "H5", "text": "Writing acid then the same charge of base returns the well to baseline, with no fluid added, for 100 cycles.",
             "pass": "Baseline absorbance shift <= 0.02 after reset; Q50 drift <= 10% from cycle 1 to 100.",
             "control": "An unwritten neighbor well tracks background drift."},
        ],
        "steps": [
            {"id": "P4.1", "title": "Make neuron media",
             "detail": "Neuron medium (recipe in Materials) at 0, 0.5, 1, 2 and 4 mM total borate: 0, 0.5, 1, 2 and 4 mL of the 100 mM borate stock per 100 mL. The 0 mM control gets a trace of carbonate until blue-green."},
            {"id": "P4.2", "title": "Threshold sweep",
             "detail": "One buffer level per electrode well, 1 mL each. The script doses in steps, mixes, reads, and fits a sigmoid per well.",
             "cmd": "python -m wetstack g4-threshold", "photo": True},
            {"id": "P4.3", "title": "Overnight reset run",
             "detail": "1 mM borate well: 100 cycles of acid at 1.5 x Q50, read, equal base, read. Lid on to slow CO2 uptake. Check the bridge ends are submerged before you leave it.",
             "cmd": "python -m wetstack g4-reset --cycles 100"},
        ],
        "gate": {"id": "G4", "name": "First chemical neuron", "cmd": "python -m wetstack gate G4",
                 "criteria": [
                     {"key": "q50_buffer_r2", "label": "Q50 vs buffer linearity", "unit": "", "op": ">=", "value": 0.95},
                     {"key": "width_ratio", "label": "Threshold sharpness (width / Q50)", "unit": "", "op": "<=", "value": 0.40},
                     {"key": "reset_delta_abs", "label": "Baseline shift after reset", "unit": "", "op": "<=", "value": 0.02},
                     {"key": "cycle_drift_pct", "label": "Q50 drift over the run", "unit": "%", "op": "<=", "value": 10},
                     {"key": "cycles", "label": "Write/reset cycles completed", "unit": "", "op": ">=", "value": 100},
                 ],
                 "if_fail": [
                     "Thresholds not linear in borate: carbon dioxide from air is adding acid and buffer. Keep the lid on and use freshly made medium.",
                     "Reset drifts acid-ward: the counter reservoir has drifted. Replace the reservoir solution (not the wells) and rerun.",
                     "Indicator fades: bromothymol blue oxidizing at the anode. Lower current to 1.5 mA and report it.",
                 ]},
        "achievement": "First chemical neuron",
    },
    {
        "id": "P5", "title": "Logic and the first stack", "weeks": "Weeks 5-6",
        "goal": "Single chemical neurons compute AND and OR; a two-layer chemical network computes XOR.",
        "why": "XOR is the classic task one threshold unit cannot do. Doing it with two layers of chemistry, relayed only linearly, is the MVP's headline proof.",
        "hypotheses": [
            {"id": "H6a", "text": "Buffer level alone turns one neuron into AND or OR.",
             "pass": "Truth tables correct in 10 of 10 repeats each.", "control": "Unbuffered well fires on any input (OR at best, never AND)."},
            {"id": "H6b", "text": "OR neuron (excitatory) and AND neuron (inhibitory) feed an output neuron that computes XOR, with the relay purely linear.",
             "pass": "XOR accuracy >= 95% over >= 40 randomized trials; relay code audited linear.",
             "control": "Same network with the inhibitory link cut computes OR, not XOR."},
        ],
        "steps": [
            {"id": "P5.1", "title": "Find the AND and OR buffer levels",
             "detail": "From your G4 fits, the script proposes borate levels so one input dose crosses threshold (OR) or only two do (AND), and an output neuron level. Make those three media.",
             "cmd": "python -m wetstack g5-logic --plan"},
            {"id": "P5.2", "title": "Truth tables",
             "detail": "Wells W1 = OR, W2 = AND. Each input row is dosed, mixed, read and reset, ten times.",
             "cmd": "python -m wetstack g5-logic --truth"},
            {"id": "P5.3", "title": "Wire the stack",
             "detail": "W3 is the output neuron. Layer 2 dose = gain x layer-1 signal (acid for OR, base for AND). Gains are fixed after calibration and saved to config.",
             "cmd": "python -m wetstack g5-stack --calibrate"},
            {"id": "P5.4", "title": "Run 40 randomized trials",
             "detail": "Expect about two hours. Photograph the plate at one trial of each input combination.",
             "cmd": "python -m wetstack g5-stack --trials 40", "photo": True},
            {"id": "P5.5", "title": "Cut-link control",
             "detail": "Same run with the AND-to-output gain set to zero. It should compute OR.",
             "cmd": "python -m wetstack g5-stack --trials 16 --cut-inhibition"},
        ],
        "gate": {"id": "G5", "name": "First stack", "cmd": "python -m wetstack gate G5",
                 "criteria": [
                     {"key": "and_acc", "label": "AND truth table accuracy", "unit": "", "op": ">=", "value": 1.0},
                     {"key": "or_acc", "label": "OR truth table accuracy", "unit": "", "op": ">=", "value": 1.0},
                     {"key": "stack_xor_acc", "label": "Stacked XOR accuracy", "unit": "", "op": ">=", "value": 0.95},
                     {"key": "stack_trials", "label": "Randomized trials", "unit": "", "op": ">=", "value": 40},
                     {"key": "linear_relay", "label": "Relay audited linear", "unit": "", "op": "==", "value": 1},
                 ],
                 "if_fail": [
                     "AND fires on one input: buffer too low; raise by 20%.",
                     "XOR fails on input 1,1: inhibitory gain too small; it must be at least the excitatory gain.",
                     "Errors cluster late in the run: reset ledger drift. Re-zero by running g4-reset --cycles 1 between blocks.",
                 ]},
        "achievement": "First stack",
    },
    {
        "id": "P6", "title": "Junctions: the ionic diode", "weeks": "Weeks 6-7",
        "goal": "Build a hydrogel junction that conducts ions better in one direction, from home-sourced polymers.",
        "why": "Directional junctions are what let signals rise through stacked layers instead of echoing back.",
        "hypotheses": [
            {"id": "H7", "text": "A bipolar junction of cationic gel (agarose + chitosan) against anionic gel (agarose + alginate) rectifies ion current.",
             "pass": "Median rectification ratio >= 2 at +/-2.5 V over 3 devices.",
             "control": "Plain agarose tube: ratio <= 1.2."},
            {"id": "H7b", "text": "Under a slow sine drive the junction shows a pinched hysteresis loop (memory).",
             "pass": "Visible pinched loop on the oscilloscope in X-Y mode at 0.1 Hz.", "control": "1 kohm resistor shows a straight line."},
        ],
        "steps": [
            {"id": "P6.1", "title": "Make Ag/AgCl electrodes",
             "detail": "In the labeled bleach jar only: 5 cm pieces of silver wire, 30 minutes in plain household bleach until dark purple-gray. Rinse well in distilled water. Never let bleach meet acid.",
             "photo": True},
            {"id": "P6.2", "title": "Cationic gel",
             "detail": "Dissolve 1 g chitosan in 50 mL of 1% acetic acid (10 mL white vinegar + 40 mL water), stir until clear (hours; hotplate low). Mix 1:1 with hot 3% agarose in water to get 1.5% agarose / 1% chitosan."},
            {"id": "P6.3", "title": "Anionic gel",
             "detail": "1.5% agarose with 1% sodium alginate in water. Backup: swollen sodium polyacrylate paste."},
            {"id": "P6.4", "title": "Cast three diode tubes and one control",
             "detail": "40 mm of 3 mm silicone tube. Fill 20 mm with warm cationic gel by syringe, let set 10 minutes, then fill the rest with warm anionic gel pressed against it. Control: plain 1.5% agarose. Label the ends + (cationic) and - (anionic).",
             "photo": True},
            {"id": "P6.5", "title": "I-V sweeps",
             "detail": "Each tube bridges two wells holding 10 mM table salt (58 mg non-iodized salt per 100 mL), one Ag/AgCl wire per well. Ag/AgCl needs chloride to work; silver reacts long before any chlorine could form at these voltages. 2 s dwell per step.",
             "cmd": "python -m wetstack g6-diode --devices 3 --control 1"},
            {"id": "P6.6", "title": "Hysteresis on the scope",
             "detail": "Scope X on the cell voltage, Y across the 1 kohm sense resistor, X-Y mode. Run the sine drive and photograph the screen.",
             "cmd": "python -m wetstack g6-diode --sine 0.1", "photo": True},
        ],
        "gate": {"id": "G6", "name": "First diode", "cmd": "python -m wetstack gate G6",
                 "criteria": [
                     {"key": "rr_median", "label": "Median rectification ratio", "unit": "", "op": ">=", "value": 2.0},
                     {"key": "rr_control", "label": "Plain-gel control ratio", "unit": "", "op": "<=", "value": 1.2},
                     {"key": "devices", "label": "Devices measured", "unit": "", "op": ">=", "value": 3},
                 ],
                 "if_fail": [
                     "Ratio near 1: the interface has an air gap. Recast pressing the second gel firmly against the first.",
                     "Ratio drifts during the sweep: dwell too short; set 5 s.",
                     "Still low: try the polyacrylate backup or the calcium exchange stretch step and tell me the numbers.",
                 ]},
        "achievement": "First diode",
    },
    {
        "id": "P7", "title": "Fiber eyes", "weeks": "Weeks 7-8",
        "goal": "Read a well through optical fiber into a spectral sensor as well as the camera does, including where the camera cannot see.",
        "why": "Stacked layers bury chambers. Fiber is how we keep reading them.",
        "hypotheses": [
            {"id": "H9", "text": "LED-on minus LED-off fiber reads track camera absorbance across a dose sweep.",
             "pass": "R-squared >= 0.95; with the plate covered, noise <= 3%.", "control": "Fiber in an empty well reads constant."},
        ],
        "steps": [
            {"id": "P7.1", "title": "Print fiber parts",
             "detail": "hardware/scad/fiber_parts.scad: the lid with a center fiber port, the LED coupler and the sensor cap. Clear resin or PETG, fully cured and washed.",
             "photo": True},
            {"id": "P7.2", "title": "Cut and polish fiber",
             "detail": "Cut 1 mm PMMA fiber with a fresh hot blade, polish each end on 2000-grit wet paper in figure-eights for 30 seconds."},
            {"id": "P7.3", "title": "Assemble and read",
             "detail": "Light pad below, fiber tip 2 mm above the liquid, far end in the sensor cap on the AS7341.",
             "cmd": "python -m wetstack spec --diff"},
            {"id": "P7.4", "title": "Dose sweep with both readers",
             "cmd": "python -m wetstack g7-fiber",
             "detail": "Camera and fiber read the same well through a dose sweep, then again with a dark cover over the plate (camera blinded)."},
        ],
        "gate": {"id": "G7", "name": "Fiber eyes", "cmd": "python -m wetstack gate G7",
                 "criteria": [
                     {"key": "fiber_camera_r2", "label": "Fiber vs camera agreement", "unit": "", "op": ">=", "value": 0.95},
                     {"key": "fiber_blind_noise_pct", "label": "Fiber noise with camera blinded", "unit": "%", "op": "<=", "value": 3},
                 ],
                 "if_fail": [
                     "Weak signal: polish the fiber ends again, and raise AS7341 gain.",
                     "Noisy: room light leaking; use the differential mode and the sensor cap.",
                 ]},
        "achievement": "Fiber eyes",
    },
    {
        "id": "P8", "title": "Sun power and energy per operation", "weeks": "Weeks 8-9",
        "goal": "Run the controller and dosing from sunlight and measure joules per chemical operation.",
        "why": "Low power and minimal consumables were the goal from the start. This is where we put numbers on it.",
        "hypotheses": [
            {"id": "H10", "text": "A 6 V panel with a single 18650 buffer runs a 4-hour daylight session of 100+ writes without a brownout.",
             "pass": ">= 4 h, >= 100 writes, 0 brownouts; joules per write recorded.", "control": "Same session on the wall adapter gives the same dose accuracy."},
        ],
        "steps": [
            {"id": "P8.1", "title": "Build the power board",
             "detail": "Panel to CN3791 charger to protected 18650. Battery to INA219 to two MT3608 boosts: set one to 5.0 V (ESP32 5V pin) and one to 9.0 V (electrolysis supply) with the multimeter before connecting anything.",
             "photo": True},
            {"id": "P8.2", "title": "Daylight session",
             "cmd": "python -m wetstack g8-solar --hours 4",
             "detail": "Panel in a window or outside in shade-free light. The script cycles the 1 mM neuron and logs power."},
        ],
        "gate": {"id": "G8", "name": "Sun-powered", "cmd": "python -m wetstack gate G8",
                 "criteria": [
                     {"key": "solar_hours", "label": "Session length", "unit": "h", "op": ">=", "value": 4},
                     {"key": "writes", "label": "Writes completed", "unit": "", "op": ">=", "value": 100},
                     {"key": "brownouts", "label": "Brownouts", "unit": "", "op": "==", "value": 0},
                     {"key": "j_per_write", "label": "Energy per write", "unit": "J", "op": "record", "value": 0},
                 ],
                 "if_fail": [
                     "Brownout at relay switching: add 470 uF across the 5 V rail.",
                     "Energy per write dominated by relay coils (about 75 mW each while held): switch to latching relays or MOSFET routing for WetStack-1. The twin predicts this.",
                     "Battery drains: panel too small for continuous dosing; lengthen idle time between writes.",
                 ]},
        "achievement": "Sun-powered",
    },
    {
        "id": "P9", "title": "MVP integration", "weeks": "Week 10",
        "goal": "Run the whole system in one demonstration and publish the report.",
        "why": "Each gate proved a part. The MVP proves the parts work together.",
        "hypotheses": [],
        "steps": [
            {"id": "P9.1", "title": "Full demo run",
             "detail": "Solar powered; stacked XOR with camera and fiber readout; the diode tube installed as W3's bridge; 20 trials.",
             "cmd": "python -m wetstack mvp-demo --trials 20", "photo": True},
            {"id": "P9.2", "title": "Generate the report",
             "cmd": "python -m wetstack report",
             "detail": "Collects every proof file into docs/MVP_REPORT.md. Commit, then git tag v1.0-mvp."},
            {"id": "P9.3", "title": "Debrief",
             "detail": "Upload the report and three photos to the workspace and ask for the lab-manager review. We plan WetStack-1 from what broke."},
        ],
        "gate": {"id": "G9", "name": "MVP complete", "cmd": "python -m wetstack gate G9",
                 "criteria": [
                     {"key": "gates_passed", "label": "Gates G0-G8 passed", "unit": "", "op": ">=", "value": 9},
                     {"key": "demo_acc", "label": "Integrated demo XOR accuracy", "unit": "", "op": ">=", "value": 0.90},
                 ],
                 "if_fail": ["Integrated accuracy below the stack result: compare per-trial logs for the readout path that differs."]},
        "achievement": "WetStack-0 MVP",
    },
]

STRETCH = [
    ["Photochromic short-term memory", "UV write (365 nm via fiber), visible erase, decay time measured. Craft photochromic pigment in clear epoxy. A memory that fades on its own, like short-term memory."],
    ["Delay neuron (iodine clock)", "Vitamin C, iodine tincture, 3% peroxide, starch. Fires abruptly after a delay set by input dose: a timing element."],
    ["Calcium-exchanged diode", "Soak the anionic side in calcium chloride. Multivalent counter-ions raised a published hydrogel diode's ratio from 3 to over 70."],
    ["Diode-coupled wells", "Replace a salt bridge with a diode tube and show writes pass one way more easily than the other."],
    ["Resin micro-chambers", "96 chambers at 50 uL in clear resin; measure how dose time shrinks with volume."],
]

# ---------------------------------------------------------------------------
# Recipes (c) chemistry details used by the steps
# ---------------------------------------------------------------------------
RECIPES = [
    ["100 mM phosphate, pH 7.6 (100 mL)",
     "7.1 mmol disodium phosphate + 2.9 mmol monosodium phosphate, water to 100 mL. Masses by the form on your label: "
     "Na2HPO4 anhydrous 1.01 g, dihydrate 1.26 g, heptahydrate 1.90 g, dodecahydrate 2.54 g; "
     "NaH2PO4 anhydrous 0.35 g, monohydrate 0.40 g, dihydrate 0.45 g. Check with the pH meter; nudge with drops of carbonate or bisulfate."],
    ["Cell medium (per 100 mL)", "0.71 g sodium sulfate (50 mM), phosphate stock for the buffer level you need (1 mL per 1 mM), 6.25 mL bromothymol blue stock (40 uM), water to 100 mL. Used for calibration (P3)."],
    ["100 mM borate stock (100 mL)", "0.953 g borax (sodium tetraborate decahydrate) in water to 100 mL. It buffers itself at pH 9.2; no adjustment needed. Gloves; do not ingest."],
    ["Neuron medium (per 100 mL)", "0.71 g sodium sulfate, borate stock for the level you need (1 mL per 1 mM total borate), 6.25 mL bromothymol blue stock, water to 100 mL. Deep blue at the start."],
    ["Bromothymol blue stock 0.4 mg/mL", "40 mg in 5 mL isopropyl alcohol, + 90 mL water, carbonate drops until blue-green, to 100 mL."],
    ["Phenol red stock 0.2 mg/mL", "20 mg in 5 mL isopropyl alcohol, + 90 mL water, carbonate drops until red, to 100 mL."],
    ["Salt bridge gel", "2 g agar in 100 mL of 0.25 M sodium sulfate (3.55 g anhydrous). Heat until clear."],
    ["Counter reservoir", "100 mL of 0.25 M sodium sulfate in a beaker, graphite rod, temperature probe."],
    ["Reference wells", "A1: cell medium + 50 uL of 200 mM bisulfate (pH about 4). A2: cell medium + 50 uL of 0.1 M carbonate (pH about 9.5)."],
]

# ---------------------------------------------------------------------------
# BOM. CAD estimates, low-high per unit, as of late 2026. Verify at purchase.
# kind: electronics | equipment | material | consumable
# ---------------------------------------------------------------------------
BOM = [
    # Electronics
    {"id": "E01", "kind": "electronics", "name": "ESP32 DevKit V1 (classic ESP32-WROOM-32, 38-pin)", "qty": 2, "lo": 6, "hi": 12, "src": "AliExpress", "search": "ESP32 DevKit V1 WROOM-32 38pin", "phase": "P3", "note": "Must be classic ESP32: S2, S3 and C3 have no DAC. Second board is a spare."},
    {"id": "E02", "kind": "electronics", "name": "ADS1115 16-bit ADC module", "qty": 3, "lo": 3, "hi": 6, "src": "AliExpress", "search": "ADS1115 module 16 bit", "phase": "P3", "note": "One shunt, one diode I-V, one spare. Set the second to address 0x49 (ADDR to VDD)."},
    {"id": "E03", "kind": "electronics", "name": "AS7341 11-channel spectral sensor module", "qty": 2, "lo": 14, "hi": 38, "src": "AliExpress / Amazon (Adafruit)", "search": "AS7341 spectral sensor module", "phase": "P7", "note": "Adafruit version is easiest; Ali clones work with the same library."},
    {"id": "E04", "kind": "electronics", "name": "8-channel 5 V relay module, optocoupled, with JD-VCC jumper", "qty": 1, "lo": 7, "hi": 14, "src": "AliExpress", "search": "8 channel relay module 5V optocoupler", "phase": "P3", "note": "Low-level trigger type."},
    {"id": "E05", "kind": "electronics", "name": "INA219 current/power module", "qty": 2, "lo": 2, "hi": 6, "src": "AliExpress", "search": "INA219 module", "phase": "P8", "note": ""},
    {"id": "E06", "kind": "electronics", "name": "DS18B20 waterproof temperature probe", "qty": 2, "lo": 2, "hi": 5, "src": "AliExpress", "search": "DS18B20 waterproof probe", "phase": "P3", "note": ""},
    {"id": "E07", "kind": "electronics", "name": "Logic-level MOSFET switch module (AO3400 or D4184)", "qty": 3, "lo": 1, "hi": 3, "src": "AliExpress", "search": "D4184 MOSFET module", "phase": "P3", "note": "Not IRF520 modules: they do not switch fully at 3.3 V."},
    {"id": "E08", "kind": "electronics", "name": "Coin vibration motors 10 mm, 3 V (10-pack)", "qty": 1, "lo": 3, "hi": 7, "src": "AliExpress", "search": "coin vibration motor 1027 3V", "phase": "P3", "note": "Mixer."},
    {"id": "E09", "kind": "electronics", "name": "MT3608 boost converter", "qty": 3, "lo": 1, "hi": 3, "src": "AliExpress", "search": "MT3608 boost module", "phase": "P8", "note": ""},
    {"id": "E10", "kind": "electronics", "name": "9 V 1 A DC adapter + barrel jack breakout", "qty": 1, "lo": 10, "hi": 18, "src": "Amazon", "search": "9V 1A power adapter 5.5x2.1", "phase": "P3", "note": ""},
    {"id": "E11", "kind": "electronics", "name": "Inline fuse holder + 250 mA fast fuses", "qty": 1, "lo": 5, "hi": 10, "src": "Amazon", "search": "inline fuse holder 5x20 250mA", "phase": "P3", "note": "Required."},
    {"id": "E12", "kind": "electronics", "name": "1% resistor kit (incl. 100, 470, 1k, 4.7k ohm)", "qty": 1, "lo": 8, "hi": 14, "src": "AliExpress", "search": "1% metal film resistor kit", "phase": "P3", "note": "Verify on hand.", "onhand": True},
    {"id": "E13", "kind": "electronics", "name": "Perfboard, screw terminals, headers", "qty": 1, "lo": 8, "hi": 15, "src": "AliExpress", "search": "perfboard screw terminal kit", "phase": "P3", "note": ""},
    {"id": "E14", "kind": "electronics", "name": "Breadboard and jumper wires", "qty": 1, "lo": 8, "hi": 12, "src": "AliExpress", "search": "830 breadboard jumper kit", "phase": "P3", "note": "Verify on hand.", "onhand": True},
    {"id": "E15", "kind": "equipment", "name": "Multimeter with uA/mA ranges", "qty": 1, "lo": 25, "hi": 50, "src": "Amazon", "search": "auto ranging multimeter microamp", "phase": "P3", "note": "Verify on hand.", "onhand": True},
    {"id": "E16", "kind": "equipment", "name": "Oscilloscope", "qty": 1, "lo": 0, "hi": 0, "src": "On hand", "search": "", "phase": "P6", "note": "On hand.", "onhand": True},
    {"id": "E17", "kind": "electronics", "name": "TCA9548A I2C multiplexer", "qty": 1, "lo": 2, "hi": 4, "src": "AliExpress", "search": "TCA9548A module", "phase": "Stretch", "note": "For several AS7341 later."},
    # Optics
    {"id": "O01", "kind": "equipment", "name": "LED tracing light pad, A4, dimmable", "qty": 1, "lo": 22, "hi": 38, "src": "Amazon", "search": "A4 LED light pad tracing dimmable", "phase": "P1", "note": "Even backlight for the plate."},
    {"id": "O02", "kind": "equipment", "name": "USB webcam with manual exposure (Logitech C920/C922 class)", "qty": 1, "lo": 50, "hi": 110, "src": "Amazon", "search": "Logitech C920", "phase": "P1", "note": "Manual exposure and white balance are the requirement."},
    {"id": "O03", "kind": "equipment", "name": "Overhead camera arm / desk mount", "qty": 1, "lo": 20, "hi": 38, "src": "Amazon", "search": "overhead camera desk mount arm 1/4", "phase": "P1", "note": ""},
    {"id": "O04", "kind": "material", "name": "PMMA end-glow optical fiber, 1.0 mm, 10 m", "qty": 1, "lo": 8, "hi": 16, "src": "AliExpress", "search": "PMMA optical fiber 1mm end glow", "phase": "P7", "note": ""},
    {"id": "O05", "kind": "electronics", "name": "5 mm LED assortment (white, 450, 590, 630 nm)", "qty": 1, "lo": 5, "hi": 10, "src": "AliExpress", "search": "5mm LED assortment kit", "phase": "P7", "note": ""},
    {"id": "O06", "kind": "electronics", "name": "365 nm UV LEDs, 5 mm (20-pack)", "qty": 1, "lo": 4, "hi": 9, "src": "AliExpress", "search": "365nm UV LED 5mm", "phase": "Stretch", "note": ""},
    {"id": "O07", "kind": "equipment", "name": "UV-blocking safety glasses", "qty": 1, "lo": 10, "hi": 22, "src": "Amazon", "search": "UV protection safety glasses 365nm", "phase": "Stretch", "note": ""},
    {"id": "O08", "kind": "equipment", "name": "18% gray / white reference card", "qty": 1, "lo": 8, "hi": 15, "src": "Amazon", "search": "18% gray card", "phase": "P1", "note": "Verify on hand.", "onhand": True},
    {"id": "O09", "kind": "material", "name": "Black foam board (2 sheets) for the light shroud", "qty": 1, "lo": 6, "hi": 14, "src": "Local / Amazon", "search": "black foam board", "phase": "P1", "note": ""},
    # Lab equipment
    {"id": "L01", "kind": "equipment", "name": "Adjustable micropipette 100-1000 uL", "qty": 1, "lo": 25, "hi": 60, "src": "AliExpress / Amazon", "search": "adjustable micropipette 100-1000ul", "phase": "P0", "note": ""},
    {"id": "L02", "kind": "equipment", "name": "Adjustable micropipette 10-100 uL", "qty": 1, "lo": 25, "hi": 60, "src": "AliExpress / Amazon", "search": "adjustable micropipette 10-100ul", "phase": "P0", "note": ""},
    {"id": "L05", "kind": "equipment", "name": "Digital scale 0.001 g / 50 g with calibration weight", "qty": 1, "lo": 25, "hi": 48, "src": "Amazon", "search": "0.001g digital scale 50g", "phase": "P0", "note": ""},
    {"id": "L06", "kind": "equipment", "name": "Borosilicate beaker set 50-500 mL", "qty": 1, "lo": 18, "hi": 32, "src": "Amazon", "search": "borosilicate beaker set", "phase": "P0", "note": ""},
    {"id": "L07", "kind": "equipment", "name": "Graduated cylinders 10/50/100 mL", "qty": 1, "lo": 14, "hi": 26, "src": "Amazon", "search": "graduated cylinder set", "phase": "P0", "note": ""},
    {"id": "L13", "kind": "equipment", "name": "pH meter pen (0.01, ATC) + calibration powders", "qty": 1, "lo": 20, "hi": 42, "src": "Amazon", "search": "pH meter 0.01 ATC calibration", "phase": "P0", "note": ""},
    {"id": "L14", "kind": "equipment", "name": "Digital caliper 150 mm", "qty": 1, "lo": 12, "hi": 25, "src": "AliExpress", "search": "digital caliper 150mm", "phase": "P0", "note": ""},
    {"id": "L15", "kind": "equipment", "name": "Small magnetic hotplate stirrer + stir bars", "qty": 1, "lo": 60, "hi": 120, "src": "Amazon", "search": "magnetic stirrer hot plate", "phase": "P1", "note": "Recommended. Microwave in short bursts is the fallback."},
    {"id": "L16", "kind": "equipment", "name": "Silicone bench mat / spill tray", "qty": 1, "lo": 10, "hi": 22, "src": "Amazon", "search": "silicone work mat large", "phase": "P0", "note": ""},
    {"id": "L18", "kind": "equipment", "name": "Safety glasses (Z87.1)", "qty": 2, "lo": 6, "hi": 15, "src": "Amazon", "search": "safety glasses Z87", "phase": "P0", "note": ""},
    {"id": "L23", "kind": "equipment", "name": "Fireproof LiPo charging bag", "qty": 1, "lo": 10, "hi": 18, "src": "Amazon", "search": "lipo safe bag", "phase": "P8", "note": ""},
    {"id": "L26", "kind": "equipment", "name": "3D printers (resin + filament)", "qty": 1, "lo": 0, "hi": 0, "src": "On hand", "search": "", "phase": "P1", "note": "On hand.", "onhand": True},
    # Labware and consumables
    {"id": "L03", "kind": "consumable", "name": "Pipette tips 1000 uL (500) + 200 uL (1000)", "qty": 1, "lo": 10, "hi": 22, "src": "AliExpress", "search": "pipette tips 1000ul 200ul", "phase": "P0", "note": ""},
    {"id": "L04", "kind": "consumable", "name": "24-well flat-bottom clear plates with lids (10-pack)", "qty": 1, "lo": 18, "hi": 38, "src": "Amazon / AliExpress", "search": "24 well plate flat bottom", "phase": "P1", "note": "Polystyrene, clear, flat bottom."},
    {"id": "L08", "kind": "consumable", "name": "Amber glass dropper bottles 30 mL (12)", "qty": 1, "lo": 12, "hi": 20, "src": "Amazon", "search": "amber glass dropper bottles 30ml", "phase": "P1", "note": ""},
    {"id": "L09", "kind": "consumable", "name": "Storage bottles 250/500 mL (6)", "qty": 1, "lo": 15, "hi": 30, "src": "Amazon", "search": "glass media bottle 500ml", "phase": "P0", "note": ""},
    {"id": "L10", "kind": "consumable", "name": "Wash bottles 250/500 mL", "qty": 2, "lo": 3, "hi": 6, "src": "AliExpress", "search": "lab wash bottle 500ml", "phase": "P0", "note": ""},
    {"id": "L11", "kind": "consumable", "name": "Silicone tubing 2 mm ID x 3 mm OD, 5 m", "qty": 1, "lo": 6, "hi": 12, "src": "AliExpress", "search": "silicone tube 2mm ID 3mm OD", "phase": "P3", "note": "Salt bridges and diode tubes."},
    {"id": "L12", "kind": "consumable", "name": "10 mL luer syringes (10) + blunt needles 14-18 G", "qty": 1, "lo": 10, "hi": 18, "src": "Amazon", "search": "10ml syringe blunt tip needle", "phase": "P3", "note": ""},
    {"id": "L17", "kind": "consumable", "name": "Nitrile gloves (100)", "qty": 1, "lo": 10, "hi": 18, "src": "Amazon / local", "search": "nitrile gloves", "phase": "P0", "note": ""},
    {"id": "L19", "kind": "consumable", "name": "Lab notebook, labels, waterproof markers", "qty": 1, "lo": 10, "hi": 20, "src": "Local", "search": "", "phase": "P0", "note": ""},
    {"id": "L20", "kind": "consumable", "name": "Transfer pipettes 3 mL (100)", "qty": 1, "lo": 5, "hi": 10, "src": "AliExpress", "search": "plastic transfer pipette 3ml", "phase": "P0", "note": ""},
    {"id": "L22", "kind": "consumable", "name": "Weighing boats, spatulas, small funnels", "qty": 1, "lo": 8, "hi": 16, "src": "AliExpress", "search": "lab spatula weighing boat set", "phase": "P0", "note": ""},
    {"id": "L27", "kind": "consumable", "name": "PETG filament / clear resin", "qty": 1, "lo": 0, "hi": 0, "src": "On hand", "search": "", "phase": "P1", "note": "On hand. PETG for wet parts.", "onhand": True},
    # Electrodes
    {"id": "X01", "kind": "material", "name": "Platinum wire 0.3 mm x 10 cm, 99.95%", "qty": 1, "lo": 15, "hi": 45, "src": "AliExpress", "search": "platinum wire 0.3mm 99.95", "phase": "P3", "note": "Verify with step P3.6."},
    {"id": "X02", "kind": "material", "name": "Graphite rods 2 mm (pure, art leads)", "qty": 1, "lo": 6, "hi": 12, "src": "Amazon / AliExpress", "search": "2mm graphite lead refill pure", "phase": "P3", "note": "Counter electrode; Pt fallback."},
    {"id": "X03", "kind": "material", "name": "Silver wire 999, 0.5 mm x 1 m", "qty": 1, "lo": 15, "hi": 40, "src": "AliExpress", "search": "999 silver wire 0.5mm", "phase": "P6", "note": "For Ag/AgCl."},
    # Chemicals
    {"id": "C01", "kind": "consumable", "name": "Distilled water, 4 L", "qty": 4, "lo": 2, "hi": 4, "src": "Grocery", "search": "", "phase": "P0", "note": ""},
    {"id": "C02", "kind": "material", "name": "Bromothymol blue powder (5-10 g)", "qty": 1, "lo": 12, "hi": 28, "src": "Amazon", "search": "bromothymol blue powder", "phase": "P1", "note": "Backup: aquarium pH test solution (bromothymol blue)."},
    {"id": "C03", "kind": "material", "name": "Phenol red powder (5 g) or 0.02% solution", "qty": 1, "lo": 12, "hi": 28, "src": "Amazon", "search": "phenol red indicator", "phase": "P2", "note": "Pool test phenol red works if concentration is listed."},
    {"id": "C04", "kind": "material", "name": "Universal indicator solution 100 mL", "qty": 1, "lo": 12, "hi": 20, "src": "Amazon", "search": "universal indicator solution", "phase": "P2", "note": "Backup for XOR."},
    {"id": "C05", "kind": "material", "name": "Sodium sulfate anhydrous 500 g", "qty": 1, "lo": 12, "hi": 22, "src": "Amazon", "search": "sodium sulfate anhydrous", "phase": "P1", "note": ""},
    {"id": "C06", "kind": "material", "name": "Sodium bisulfate (pool pH Down, 93%+) 1 kg", "qty": 1, "lo": 10, "hi": 16, "src": "Amazon / pool store", "search": "sodium bisulfate pH down", "phase": "P2", "note": ""},
    {"id": "C07", "kind": "material", "name": "Sodium carbonate (washing soda / pH Up) 1 kg", "qty": 1, "lo": 6, "hi": 12, "src": "Grocery / Amazon", "search": "washing soda sodium carbonate", "phase": "P1", "note": ""},
    {"id": "C09", "kind": "material", "name": "Disodium phosphate, food grade, 250-500 g", "qty": 1, "lo": 12, "hi": 22, "src": "Amazon", "search": "disodium phosphate food grade", "phase": "P2", "note": "Note the hydrate form on the label."},
    {"id": "C22", "kind": "material", "name": "Borax (sodium tetraborate decahydrate), laundry grade OK", "qty": 1, "lo": 6, "hi": 14, "src": "Grocery / Amazon", "search": "20 Mule Team Borax", "phase": "P4", "note": "Neuron buffer. Gloves; keep from kids and pets."},
    {"id": "C10", "kind": "material", "name": "Monosodium phosphate, food grade, 250-500 g", "qty": 1, "lo": 12, "hi": 22, "src": "Amazon", "search": "monosodium phosphate food grade", "phase": "P2", "note": ""},
    {"id": "C11", "kind": "material", "name": "Agar-agar powder 100 g", "qty": 1, "lo": 10, "hi": 16, "src": "Grocery / Amazon", "search": "agar agar powder", "phase": "P3", "note": "Salt bridges."},
    {"id": "C12", "kind": "material", "name": "Agarose LE, molecular biology grade, 25 g", "qty": 1, "lo": 35, "hi": 70, "src": "Amazon", "search": "agarose powder molecular biology", "phase": "P6", "note": "Low charge; agar is not a substitute for the diode."},
    {"id": "C13", "kind": "material", "name": "Chitosan powder, medium MW, 100 g", "qty": 1, "lo": 20, "hi": 38, "src": "Amazon", "search": "chitosan powder", "phase": "P6", "note": "Cationic side of the diode."},
    {"id": "C14", "kind": "material", "name": "Sodium alginate, food grade, 100 g", "qty": 1, "lo": 10, "hi": 18, "src": "Amazon", "search": "sodium alginate", "phase": "P6", "note": "Anionic side."},
    {"id": "C15", "kind": "material", "name": "Sodium polyacrylate (SAP) 250 g", "qty": 1, "lo": 10, "hi": 16, "src": "Amazon", "search": "sodium polyacrylate powder", "phase": "P6", "note": "Backup anionic side."},
    {"id": "C21", "kind": "consumable", "name": "Non-iodized table salt", "qty": 1, "lo": 2, "hi": 4, "src": "Grocery", "search": "", "phase": "P6", "note": "Diode test wells only."},
    {"id": "C16", "kind": "consumable", "name": "White vinegar 5%", "qty": 1, "lo": 3, "hi": 5, "src": "Grocery", "search": "", "phase": "P6", "note": ""},
    {"id": "C17", "kind": "consumable", "name": "Isopropyl alcohol 99%, 500 mL", "qty": 1, "lo": 8, "hi": 15, "src": "Pharmacy / Amazon", "search": "isopropyl alcohol 99%", "phase": "P1", "note": ""},
    {"id": "C18", "kind": "consumable", "name": "Household bleach, unscented", "qty": 1, "lo": 3, "hi": 6, "src": "Grocery", "search": "", "phase": "P6", "note": "Own labeled jar. Never near acids."},
    {"id": "C19", "kind": "material", "name": "Calcium chloride food grade 250 g", "qty": 1, "lo": 8, "hi": 14, "src": "Amazon", "search": "calcium chloride food grade", "phase": "Stretch", "note": ""},
    {"id": "C20", "kind": "material", "name": "Photochromic pigment powder 10 g", "qty": 1, "lo": 6, "hi": 12, "src": "AliExpress", "search": "photochromic pigment powder UV", "phase": "Stretch", "note": ""},
    # Solar
    {"id": "S01", "kind": "electronics", "name": "Solar panel 6 V, 6 W", "qty": 1, "lo": 18, "hi": 35, "src": "Amazon / AliExpress", "search": "6V 6W solar panel", "phase": "P8", "note": ""},
    {"id": "S02", "kind": "electronics", "name": "CN3791 MPPT single-cell solar charger module", "qty": 1, "lo": 3, "hi": 7, "src": "AliExpress", "search": "CN3791 solar charger 6V", "phase": "P8", "note": "Get the 6 V input version."},
    {"id": "S03", "kind": "material", "name": "Protected 18650 Li-ion cell, reputable brand", "qty": 2, "lo": 12, "hi": 25, "src": "Local battery shop / Amazon", "search": "protected 18650 battery", "phase": "P8", "note": "Do not buy cells on AliExpress."},
    {"id": "S04", "kind": "electronics", "name": "18650 holder with leads", "qty": 2, "lo": 1, "hi": 3, "src": "AliExpress", "search": "18650 battery holder", "phase": "P8", "note": ""},
]

SIM_NOTE = (
    "Every experiment command accepts --sim to run against the digital twin in host/wetstack/sim.py: "
    "phosphate buffer equilibria, indicator speciation, Faraday dosing with efficiency, camera absorbance noise, "
    "a gel-diode model and a power model. Run it before every wet session so you know what a good result looks like."
)
