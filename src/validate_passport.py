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
from urllib.parse import urlparse

from jsonschema import Draft7Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "dcp-batch.schema.json"

# Tolerance used for the two arithmetic consistency checks below (percentage points).
TOLERANCE_PP = 0.5

# EN 197-1:2011, Table 1 - main constituents other than clinker (K). Shares are in % of the
# sum of main and minor additional constituents (calcium sulfate and additives excluded).
_POZZOLANIC = {"D", "P", "Q", "V", "W"}
_ALL_MAIN = {"S", "D", "P", "Q", "V", "W", "T", "L", "LL"}
MINOR_MAX = 5.0  # minor additional constituents, 0-5 %


def main_constituent_rules(cement_type):
    """Return (allowed codes, [(codes, min %, max %)], minimum number of distinct codes)."""
    if cement_type == "CEM I":
        return set(), [], 0
    if cement_type.startswith("CEM II/"):
        cls, letter = cement_type[len("CEM II/"):].split("-", 1)
        if letter == "M":  # Portland-composite: two or more main constituents besides clinker
            return set(_ALL_MAIN), [(set(_ALL_MAIN), 12, 20) if cls == "A" else (set(_ALL_MAIN), 21, 35)], 2
        if letter == "D":
            return {"D"}, [({"D"}, 6, 10)], 1
        return {letter}, [({letter}, 6, 20) if cls == "A" else ({letter}, 21, 35)], 1
    if cement_type.startswith("CEM III/"):
        rng = {"A": (36, 65), "B": (66, 80), "C": (81, 95)}[cement_type[-1]]
        return {"S"}, [({"S"},) + rng], 1
    if cement_type.startswith("CEM IV/"):
        rng = (11, 35) if cement_type.endswith("A") else (36, 55)
        return set(_POZZOLANIC), [(set(_POZZOLANIC),) + rng, ({"D"}, 0, 10)], 1
    if cement_type.startswith("CEM V/"):
        rng = (18, 30) if cement_type.endswith("A") else (31, 49)
        return {"S", "P", "Q", "V"}, [({"S"},) + rng, ({"P", "Q", "V"},) + rng], 2
    return None, [], 0


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
        ctype = comp.get("cementType")
        allowed, ranges, min_distinct = (main_constituent_rules(ctype) if isinstance(ctype, str)
                                         else (None, [], 0))
        shares_ok = all(isinstance(c.get("massPercent"), (int, float)) for c in items)
        if allowed is not None:
            mains = [c for c in items if c.get("role") == "mainConstituent"]
            for i, c in enumerate(items):
                code = c.get("en197Constituent")
                if c.get("role") == "mainConstituent" and isinstance(code, str) and code not in allowed:
                    problems.append((f"composition.constituents.{i}.en197Constituent",
                                     f"main constituent '{code}' is not allowed in {ctype} (EN 197-1, Table 1)"))
            distinct = {c.get("en197Constituent") for c in mains} & allowed
            if len(distinct) < min_distinct:
                problems.append(("composition.constituents",
                                 f"{ctype} requires at least {min_distinct} different main constituents besides "
                                 f"clinker; found {len(distinct)} (EN 197-1, Table 1)"))
            nucleus = sum(c["massPercent"] for c in items
                          if c.get("role") not in ("calciumSulfate", "additive")) if shares_ok else 0
            if nucleus > 0:
                minor = 100.0 * sum(c["massPercent"] for c in items
                                    if c.get("role") == "minorAdditionalConstituent") / nucleus
                if round(minor, 1) > MINOR_MAX:
                    problems.append(("composition.constituents",
                                     f"minor additional constituents are {minor:.1f} % of the main and minor "
                                     f"constituents; maximum {MINOR_MAX:g} % (EN 197-1, Table 1)"))
                for codes, lo, hi in ranges:
                    share = 100.0 * sum(c["massPercent"] for c in mains
                                        if c.get("en197Constituent") in codes) / nucleus
                    if not lo <= round(share, 1) <= hi:
                        problems.append(("composition.constituents",
                                         f"{'/'.join(sorted(codes))} is {share:.1f} % of the main and minor "
                                         f"constituents; {ctype} requires {lo}-{hi} % (EN 197-1, Table 1)"))
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

    # Pilot convention: the passport URI must point to this batch (last path segment = batchID).
    if isinstance(record, dict):
        batch, uri = record.get("batchID"), record.get("passportURI")
        if isinstance(batch, str) and batch and isinstance(uri, str) and "://" in uri:
            last = urlparse(uri).path.rstrip("/").rsplit("/", 1)[-1]
            if last != batch:
                problems.append(("passportURI",
                                 f"passport URI ends with '{last}', not with the batchID '{batch}'"))

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
