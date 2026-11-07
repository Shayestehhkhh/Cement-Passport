"""Print a role-dependent view of a DCP batch record.

Illustrates the 'permissions and access control' element of the framework: each role
sees only the fields assigned to it. The role-to-field assignment is an illustrative
design choice of this pilot, not a requirement taken from a standard. No ratings or
grades are computed.

Usage:
    python src/passport_report.py examples/batch-valid.json [public|engineer|auditor]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_passport import validate_record  # noqa: E402

ROLES = ("public", "engineer", "auditor")


def a1_a3_total(entries, key="gwpTotal"):
    """A1-A3 value: the aggregated module if declared, otherwise the sum of A1, A2 and A3."""
    by_module = {e["module"]: e for e in entries}
    if "A1-A3" in by_module and key in by_module["A1-A3"]:
        return by_module["A1-A3"][key]
    if all(m in by_module and key in by_module[m] for m in ("A1", "A2", "A3")):
        return round(sum(by_module[m][key] for m in ("A1", "A2", "A3")), 6)
    return None


def view(record, role):
    if role not in ROLES:
        raise ValueError(f"unknown role '{role}'; use one of {ROLES}")
    lca = record["lcaIndicators"]
    unit = lca["declaredUnit"]
    out = {
        "batchID": record["batchID"],
        "passportURI": record["passportURI"],
        "plantLocation": record["traceability"]["plantLocation"],
        "cementType": record["composition"]["cementType"],
        f"GWP-total A1-A3 (kg CO2 eq / {unit})": a1_a3_total(lca["indicatorsPerModule"]),
    }
    if role in ("engineer", "auditor"):
        out.update({
            "strengthClass": record["composition"]["strengthClass"],
            "standardStrength28Days (MPa)": record["strength"]["standardStrength28Days"],
            "manufacturingDate": record["traceability"]["manufacturingDate"],
            "safetyDataSheet": record["safety"].get("safetyDataSheet"),
            "recyclabilityStatus": record.get("endOfLife", {}).get("recyclabilityStatus"),
        })
    if role == "auditor":
        out.update({
            "manufacturerID": record["traceability"]["manufacturerID"],
            "clinkerRatio": record["composition"]["clinkerRatio"],
            "constituents": record["composition"]["constituents"],
            "solubleChromiumVI (mg/kg)": record["safety"]["solubleChromiumVI"],
            "energySourceType": record.get("energySourceType"),
            "indicatorsPerModule": lca["indicatorsPerModule"],
        })
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as f:
        rec = json.load(f)
    problems = validate_record(rec)
    if problems:
        print("Record rejected by the schema; no view produced:", problems)
        sys.exit(1)
    role = sys.argv[2] if len(sys.argv) > 2 else "public"
    print(json.dumps(view(rec, role), indent=2, ensure_ascii=False))
