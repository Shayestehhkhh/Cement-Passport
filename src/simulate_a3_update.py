"""Offline simulation of the proposed MQTT-based A3 update (no broker, no network).

A synthetic message shaped like the payload in api/dcp-asyncapi.yaml is (1) checked
against the message schema, (2) checked for a matching batchID, and (3) merged into a
copy of the passport, which is then re-validated against the full schema. Only messages
that pass all checks are recorded, as described for the proposed design.

Usage:
    python src/simulate_a3_update.py examples/batch-valid.json
"""
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_passport import load_schema, validate_record  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def message_schema(schema):
    """Payload schema of the 'a3Update' message (same structure as in api/dcp-asyncapi.yaml).

    The indicator block reuses the moduleIndicators definition of the passport schema,
    without the 'module' field, which is carried at message level and fixed to A3.
    """
    indicators = copy.deepcopy(schema["definitions"]["moduleIndicators"])
    indicators["properties"].pop("module")
    # A message must say where the values come from and when they were measured.
    indicators["required"] = [r for r in indicators["required"] if r != "module"] + ["dataSource", "lastUpdated"]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["batchID", "module", "indicators"],
        "properties": {
            "batchID": {"type": "string", "minLength": 1},
            "module": {"const": "A3"},
            "indicators": indicators,
        },
    }


def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def apply_a3_update(record, message, schema=None):
    """Return (updated_record, problems). The input record is never modified."""
    schema = schema or load_schema()
    base_problems = validate_record(record, schema)
    if base_problems:
        return record, [("(passport)", "the stored passport record is itself invalid; no update applied")] + base_problems
    v = Draft7Validator(message_schema(schema), format_checker=FormatChecker())
    problems = [(".".join(map(str, e.absolute_path)) or "(message root)", e.message)
                for e in v.iter_errors(message)]
    if not problems and message["batchID"] != record["batchID"]:
        problems.append(("batchID", f"message for '{message['batchID']}' does not match passport '{record['batchID']}'"))
    if not problems:
        stored = next((e for e in record["lcaIndicators"]["indicatorsPerModule"] if e.get("module") == "A3"), None)
        if stored is not None and "lastUpdated" in stored:
            if _time(message["indicators"]["lastUpdated"]) <= _time(stored["lastUpdated"]):
                problems.append(("indicators.lastUpdated",
                                 f"message time {message['indicators']['lastUpdated']} is not later than the stored "
                                 f"A3 update ({stored['lastUpdated']}); older or repeated messages are not recorded"))
    if problems:
        return record, problems
    updated = copy.deepcopy(record)
    entries = updated["lcaIndicators"]["indicatorsPerModule"]
    new_entry = dict(message["indicators"], module="A3")
    for i, e in enumerate(entries):
        if e.get("module") == "A3":
            entries[i] = new_entry
            break
    else:
        entries.append(new_entry)
    problems = validate_record(updated, schema)
    return (record, problems) if problems else (updated, [])


def demo(record_path):
    with open(record_path, encoding="utf-8") as f:
        record = json.load(f)
    good = {"batchID": record["batchID"], "module": "A3",
            "indicators": {"gwpTotal": 41.5, "primaryEnergyRenewableTotal": 31.0,
                           "primaryEnergyNonRenewableTotal": 462.0,
                           "dataSource": "plantSensor", "lastUpdated": "2026-03-03T06:00:00Z"}}
    bad = {"batchID": record["batchID"], "module": "A3",
           "indicators": dict(good["indicators"], primaryEnergyNonRenewableTotal=-5.0)}
    wrong_batch = dict(good, batchID="DCP-EX-2026-999999")
    older = {"batchID": record["batchID"], "module": "A3",
             "indicators": dict(good["indicators"], lastUpdated="2026-03-01T06:00:00Z")}
    results = []
    for label, msg in (("valid message", good), ("negative energy value", bad), ("wrong batchID", wrong_batch),
                       ("message older than the stored A3 value", older)):
        updated, problems = apply_a3_update(record, msg)
        results.append((label, msg, updated, problems))
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    for label, msg, updated, problems in demo(sys.argv[1]):
        status = "RECORDED" if not problems else "DISCARDED"
        print(f"{status:9} {label}: {json.dumps(msg['indicators'])}")
        for loc, m in problems:
            print(f"          - {loc}: {m}")
