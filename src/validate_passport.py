"""Validate Digital Cement Passport (DCP) batch records against the DCP JSON Schema.

Illustrative pilot code. A record that passes is *structurally consistent with the
specified schema*; this is NOT a conformity assessment under EN 197-1, NOT an
EPD verification under EN 15804 and NOT proof of compliance with REACH.

Usage:
    python src/validate_passport.py examples/batch-valid.json examples/invalid/*.json
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "dcp-batch.schema.json"

# Tolerance used for the two arithmetic consistency checks below (percentage points).
TOLERANCE_PP = 0.5


def load_schema(path=SCHEMA_PATH):
    with open(path, encoding="utf-8") as f:
        schema = json.load(f)
    Draft7Validator.check_schema(schema)  # the schema itself must be a valid JSON Schema
    return schema


def cas_check_digit_ok(cas):
    """CAS Registry Number check digit: weighted sum of the other digits, modulo 10."""
    digits = cas.replace("-", "")
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * w for w, d in enumerate(reversed(body), start=1))
    return total % 10 == check


def _path(error):
    return ".".join(str(p) for p in error.absolute_path) or "(record root)"


def validate_record(record, schema=None):
    """Return a list of (location, message) tuples; an empty list means the record is accepted."""
    schema = schema or load_schema()
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    problems = []
    for err in sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path)):
        # For if/then rules jsonschema reports the failing leaf; keep the most specific message.
        leaves = list(err.context) or [err]
        for leaf in leaves:
            problems.append((_path(leaf), leaf.message))

    # Checks that JSON Schema cannot express; run only on structurally sound parts.
    comp = record.get("composition") if isinstance(record, dict) else None
    if isinstance(comp, dict) and isinstance(comp.get("constituents"), list):
        items = [c for c in comp["constituents"] if isinstance(c, dict)]
        for i, c in enumerate(items):
            cas = c.get("casNumber", "")
            if isinstance(cas, str) and cas.count("-") == 2 and cas.replace("-", "").isdigit():
                if not cas_check_digit_ok(cas):
                    problems.append((f"composition.constituents.{i}.casNumber",
                                     f"'{cas}' fails the CAS Registry Number check digit"))
        shares = [c.get("massPercent") for c in items]
        if all(isinstance(s, (int, float)) for s in shares) and shares:
            total = sum(shares)
            if abs(total - 100.0) > TOLERANCE_PP:
                problems.append(("composition.constituents",
                                 f"constituent shares add up to {total:.1f} %, not 100 %"))
            nucleus = sum(c["massPercent"] for c in items if c.get("role") not in ("calciumSulfate", "additive"))
            clinker = sum(c["massPercent"] for c in items if c.get("role") == "clinker")
            ratio = comp.get("clinkerRatio")
            if nucleus > 0 and isinstance(ratio, (int, float)):
                derived = 100.0 * clinker / nucleus
                if abs(derived - ratio) > TOLERANCE_PP:
                    problems.append(("composition.clinkerRatio",
                                     f"declared clinkerRatio {ratio} differs from the value derived "
                                     f"from the constituents ({derived:.1f})"))

    lca = record.get("lcaIndicators") if isinstance(record, dict) else None
    entries = lca.get("indicatorsPerModule") if isinstance(lca, dict) else None
    if isinstance(entries, list):
        modules = [e.get("module") for e in entries if isinstance(e, dict)]
        for m in sorted({m for m in modules if modules.count(m) > 1 and isinstance(m, str)}):
            problems.append(("lcaIndicators.indicatorsPerModule", f"module {m} is declared more than once"))
        if "A1-A3" in modules and any(m in modules for m in ("A1", "A2", "A3")):
            problems.append(("lcaIndicators.indicatorsPerModule",
                             "aggregated module A1-A3 declared together with A1, A2 or A3 (double counting)"))
    return problems


def main(paths):
    schema = load_schema()
    rejected = 0
    for p in paths:
        with open(p, encoding="utf-8") as f:
            record = json.load(f)
        problems = validate_record(record, schema)
        if problems:
            rejected += 1
            print(f"REJECTED  {p}")
            for loc, msg in problems:
                print(f"          - {loc}: {msg}")
        else:
            print(f"ACCEPTED  {p}")
    return rejected


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(1 if main(sys.argv[1:]) else 0)
