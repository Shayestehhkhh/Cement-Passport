"""Re-create the synthetic invalid records in examples/invalid/ from examples/batch-valid.json.

Each record introduces exactly one defect; examples/expected_rejections.json lists the
expected rejection reason and the location where the error must be reported.

Usage:
    python src/make_invalid_examples.py
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _set(path, value):
    def mutate(d):
        *parents, last = path
        for p in parents:
            d = d[p]
        d[last] = value
    return mutate


def _module_b1(d):
    d["lcaIndicators"]["indicatorsPerModule"].append({"module": "B1", "gwpTotal": 1.0})


def _duplicate_a3(d):
    entries = d["lcaIndicators"]["indicatorsPerModule"]
    entries.append(copy.deepcopy(next(e for e in entries if e["module"] == "A3")))


CASES = [
    ("01-chromium-vi-above-limit", _set(["safety", "solubleChromiumVI"], 3.1),
     "water-soluble Cr(VI) of 3.1 mg/kg above the 2 mg/kg limit (REACH Annex XVII, entry 47)",
     "safety.solubleChromiumVI"),
    ("02-unknown-cement-type", _set(["composition", "cementType"], "CEM II/C-V"),
     "cement type not among the 27 products of EN 197-1", "composition.cementType"),
    ("03-clinker-ratio-outside-en197", _set(["composition", "clinkerRatio"], 85.0),
     "clinker ratio of 85 % outside the 65-79 % range of CEM II/B-V (EN 197-1, Table 1)", "composition.clinkerRatio"),
    ("04-invalid-strength-class", _set(["composition", "strengthClass"], "50"),
     "strength class not defined in EN 197-1", "composition.strengthClass"),
    ("05-28day-strength-below-class", _set(["strength", "standardStrength28Days"], 39.0),
     "28-day strength of 39 MPa below the 42.5 MPa lower limit of class 42.5 (EN 197-1, Table 3)",
     "strength.standardStrength28Days"),
    ("06-malformed-cas-number", _set(["composition", "constituents", 0, "casNumber"], "65997-16"),
     "CAS Registry Number not in the NNNNNNN-NN-N format", "composition.constituents.0.casNumber"),
    ("07-latitude-out-of-range", _set(["traceability", "quarryLocation", "latitude"], 95.0),
     "latitude outside -90..90", "traceability.quarryLocation.latitude"),
    ("08-undefined-lca-module", _module_b1,
     "module B1 is outside the passport scope (A1-A3, C1-C4)", "lcaIndicators.indicatorsPerModule.7.module"),
    ("09-missing-batch-id", lambda d: d.pop("batchID"), "mandatory batchID missing", "(record root)"),
    ("10-unknown-energy-source", _set(["energySourceType"], "Nuclear-Fusion"),
     "energy source outside the controlled vocabulary", "energySourceType"),
    ("11-passport-uri-not-a-uri", _set(["passportURI"], "passport DCP-EX-2026-000123"),
     "passportURI is not a valid URI and cannot serve as QR content", "passportURI"),
    ("12-L-class-with-non-CEM-III", _set(["composition", "strengthClass"], "42.5L"),
     "low early strength (L) classes apply only to CEM III cements (EN 197-1)", "composition.cementType"),
    ("13-cas-check-digit-wrong", _set(["composition", "constituents", 0, "casNumber"], "65997-16-3"),
     "CAS Registry Number fails its check digit", "composition.constituents.0.casNumber"),
    ("14-duplicate-a3-module", _duplicate_a3,
     "module A3 declared twice", "lcaIndicators.indicatorsPerModule"),
]


def main():
    base = json.loads((ROOT / "examples" / "batch-valid.json").read_text(encoding="utf-8"))
    out = ROOT / "examples" / "invalid"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        old.unlink()
    manifest = {}
    for name, mutate, reason, location in CASES:
        rec = copy.deepcopy(base)
        mutate(rec)
        (out / f"{name}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest[f"{name}.json"] = {"expectedRejectionReason": reason, "expectedErrorLocation": location}
    (ROOT / "examples" / "expected_rejections.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(CASES)} invalid records written to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
