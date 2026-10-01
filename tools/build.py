"""Rebuild every generated artifact from tools/content.py.

    python tools/build.py

Writes host/wetstack/gates.json, docs/LAB_MANUAL.md, bom/*.csv and
web/wetstack_lab.html (from web/template.html).
"""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_content():
    spec = importlib.util.spec_from_file_location("content", ROOT / "tools" / "content.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def weighted(option, weights):
    return sum(s * w for s, w in zip(option["scores"], weights))


def bom_totals(bom):
    need = [b for b in bom if not b.get("onhand")]
    by_kind = {}
    for b in need:
        k = b["kind"]
        lo, hi = by_kind.get(k, (0, 0))
        by_kind[k] = (lo + b["qty"] * b["lo"], hi + b["qty"] * b["hi"])
    by_phase = {}
    for b in need:
        lo, hi = by_phase.get(b["phase"], (0, 0))
        by_phase[b["phase"]] = (lo + b["qty"] * b["lo"], hi + b["qty"] * b["hi"])
    total = (sum(v[0] for v in by_kind.values()), sum(v[1] for v in by_kind.values()))
    return by_kind, by_phase, total


def write_gates(c):
    gates = {}
    for ph in c.PHASES:
        g = ph["gate"]
        gates[g["id"]] = {"name": g["name"], "phase": ph["id"], "criteria": g["criteria"]}
    (ROOT / "host" / "wetstack" / "gates.json").write_text(json.dumps(gates, indent=1))


def write_bom(c):
    out = ROOT / "bom"
    out.mkdir(exist_ok=True)
    groups = {"electronics": ["electronics"], "equipment": ["equipment"], "materials": ["material", "consumable"]}
    fields = ["id", "name", "qty", "unit_cad_low", "unit_cad_high", "line_cad_low", "line_cad_high", "source",
              "search_terms", "first_needed", "on_hand", "notes"]
    for fname, kinds in groups.items():
        with open(out / f"BOM_{fname}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(fields)
            for b in c.BOM:
                if b["kind"] not in kinds:
                    continue
                w.writerow([b["id"], b["name"], b["qty"], b["lo"], b["hi"], b["qty"] * b["lo"], b["qty"] * b["hi"],
                            b["src"], b["search"], b["phase"], "yes" if b.get("onhand") else "no", b.get("note", "")])
    by_kind, by_phase, total = bom_totals(c.BOM)
    with open(out / "BOM_summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["group", "est_cad_low", "est_cad_high"])
        for k, (lo, hi) in sorted(by_kind.items()):
            w.writerow([f"kind:{k}", lo, hi])
        for k, (lo, hi) in sorted(by_phase.items()):
            w.writerow([f"phase:{k}", lo, hi])
        w.writerow(["TOTAL (items not on hand)", total[0], total[1]])


def write_manual(c):
    L = []
    P = c.PROJECT
    L += [f"# {P['name']} lab manual", "", f"_{P['tagline']}_", "",
          "Generated from tools/content.py by tools/build.py. The web workspace (web/wetstack_lab.html) shows the same content with progress tracking.", "",
          "## MVP definition", ""]
    L += [f"- {x}" for x in P["mvp_definition"]] + ["", "## Working principles", ""]
    L += [f"- **{a}.** {b}" for a, b in P["principles"]] + ["", "## Roles", ""]
    L += [f"- **{a}:** {b}" for a, b in P["roles"]] + [""]

    L += ["## (a) Path to MVP", "", c.PATH["question"], "",
          "| Option | " + " | ".join(f"{k} (x{w})" for k, w in zip(c.PATH["criteria"], c.PATH["weights"])) + " | Weighted |",
          "|---|" + "---|" * (len(c.PATH["criteria"]) + 1)]
    for o in c.PATH["options"]:
        L.append(f"| {o['name']} | " + " | ".join(str(s) for s in o["scores"]) + f" | {weighted(o, c.PATH['weights'])} |")
    L += ["", "Scores are 1 (poor) to 5 (best).", ""]
    L += [f"- **{o['name']}:** {o['note']}" for o in c.PATH["options"]]
    L += ["", f"**Decision:** {c.PATH['decision']}", ""] + [f"- {w}" for w in c.PATH["why"]] + [""]

    A = c.ARCHITECTURE
    L += ["## (b) Architecture", "", A["summary"], "", "| Layer | Hardware | Role |", "|---|---|---|"]
    L += [f"| {a} | {b} | {d} |" for a, b, d in A["layers"]]
    L += ["", "Signal flow: " + " -> ".join(A["signal_flow"]), "", "### Pin map", "", "| Pin | Function | Connects to |", "|---|---|---|"]
    L += [f"| {a} | {b} | {d} |" for a, b, d in A["pinmap"]]
    L += ["", "### Wiring notes", ""] + [f"- {w}" for w in A["wiring_notes"]] + ["", "### Design decisions", ""]
    L += [f"- **{a}.** {b}" for a, b in A["decisions"]] + [""]

    L += ["## (c) Materials", "", "Full lists with search terms: bom/BOM_electronics.csv, bom/BOM_equipment.csv, bom/BOM_materials.csv.", ""]
    by_kind, by_phase, total = bom_totals(c.BOM)
    L += ["| Group | Estimate (CAD) |", "|---|---|"]
    L += [f"| {k} | {lo}-{hi} |" for k, (lo, hi) in sorted(by_kind.items())]
    L += [f"| **Total, items not on hand** | **{total[0]}-{total[1]}** |", "",
          "Spend by phase (order just ahead of each phase):", "", "| Phase | Estimate (CAD) |", "|---|---|"]
    L += [f"| {k} | {lo}-{hi} |" for k, (lo, hi) in sorted(by_phase.items())]
    L += ["", "Prices are late-2026 estimates from typical AliExpress and Amazon.ca listings; verify at purchase.", "", "### Recipes", ""]
    L += [f"- **{a}.** {b}" for a, b in c.RECIPES] + [""]

    L += ["## (d) Methods", ""] + [f"- **{a}.** {b}" for a, b in c.METHODS] + ["", "### Safety", ""]
    L += [f"- **{a}.** {b}" for a, b in c.SAFETY] + ["", c.SIM_NOTE, ""]

    L += ["## Phases, gates and steps", ""]
    for ph in c.PHASES:
        L += [f"### {ph['id']} {ph['title']} ({ph['weeks']})", "", f"**Goal.** {ph['goal']}", "", f"**Why.** {ph['why']}", ""]
        for h in ph["hypotheses"]:
            L += [f"- **{h['id']}.** {h['text']} _Pass:_ {h['pass']} _Control:_ {h['control']}"]
        if ph["hypotheses"]:
            L.append("")
        for s in ph["steps"]:
            L.append(f"- [ ] **{s['id']} {s['title']}.** {s['detail']}" + (f" `{s['cmd']}`" if s.get("cmd") else "")
                     + (" (photo)" if s.get("photo") else ""))
        g = ph["gate"]
        L += ["", f"**Gate {g['id']}: {g['name']}** (`{g['cmd']}`)", "", "| Criterion | Target |", "|---|---|"]
        L += [f"| {cr['label']} | {'record' if cr['op'] == 'record' else cr['op'] + ' ' + str(cr['value'])} {cr['unit']} |" for cr in g["criteria"]]
        L += ["", "If it fails:", ""] + [f"- {x}" for x in g["if_fail"]] + ["", f"Achievement: **{ph['achievement']}**", ""]
    L += ["## Stretch goals", ""] + [f"- **{a}.** {b}" for a, b in c.STRETCH] + [""]
    (ROOT / "docs" / "LAB_MANUAL.md").write_text("\n".join(L), encoding="utf-8")


def write_web(c):
    by_kind, by_phase, total = bom_totals(c.BOM)
    data = {
        "project": c.PROJECT, "path": c.PATH, "architecture": c.ARCHITECTURE, "methods": c.METHODS,
        "safety": c.SAFETY, "recipes": c.RECIPES, "phases": c.PHASES, "stretch": c.STRETCH, "bom": c.BOM,
        "sim_note": c.SIM_NOTE,
    }
    tpl = (ROOT / "web" / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace("/*__DATA__*/null", payload)
    (ROOT / "web" / "wetstack_lab.html").write_text(html, encoding="utf-8")


def main():
    c = load_content()
    write_gates(c)
    write_bom(c)
    write_manual(c)
    if (ROOT / "web" / "template.html").exists():
        write_web(c)
    by_kind, by_phase, total = bom_totals(c.BOM)
    print(f"Built: gates.json, LAB_MANUAL.md, BOM CSVs, web. Estimated spend CAD {total[0]}-{total[1]}.")


if __name__ == "__main__":
    main()
