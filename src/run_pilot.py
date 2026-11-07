"""Run the complete illustrative pilot and write a log to output/pilot_run_log.txt.

Steps: (1) schema validation of the synthetic valid record and of the synthetic invalid
records, (2) the resulting cement passport, (3) QR codes and the HTML passport page,
(4) role-dependent views, (5) offline simulation of the MQTT-based A3 update.
All data are synthetic.

Usage:
    python src/run_pilot.py
"""
import io
import json
import platform
import sys
from contextlib import redirect_stdout
from pathlib import Path

from importlib.metadata import version

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_qr import make_qr, make_summary_qr, summary_text  # noqa: E402
from passport_report import ROLES, view  # noqa: E402
from render_passport import render  # noqa: E402
from simulate_a3_update import demo  # noqa: E402
from validate_passport import load_schema, validate_record  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def run():
    schema = load_schema()
    valid_path = ROOT / "examples" / "batch-valid.json"
    expected = json.loads((ROOT / "examples" / "expected_rejections.json").read_text(encoding="utf-8"))
    ok = True

    print("DCP illustrative pilot - SYNTHETIC DATA ONLY")
    print(f"Python {platform.python_version()}, jsonschema {version('jsonschema')}, qrcode {version('qrcode')}")
    print("=" * 72)

    print("\n[1] Schema validation")
    record = json.loads(valid_path.read_text(encoding="utf-8"))
    problems = validate_record(record, schema)
    print(f"  {'ACCEPTED' if not problems else 'REJECTED'}  examples/batch-valid.json")
    ok &= not problems
    for name, exp in expected.items():
        rec = json.loads((ROOT / "examples" / "invalid" / name).read_text(encoding="utf-8"))
        probs = validate_record(rec, schema)
        hit = any(loc == exp["expectedErrorLocation"] for loc, _ in probs)
        ok &= bool(probs) and hit
        print(f"  {'REJECTED' if probs else 'ACCEPTED'}  invalid/{name}  "
              f"(expected: {exp['expectedRejectionReason']}) -> {'as expected' if probs and hit else 'UNEXPECTED'}")
        for loc, msg in probs:
            print(f"            - {loc}: {msg}")

    print("\n[2] The cement passport of the accepted synthetic batch")
    for line in summary_text(record).splitlines():
        print(f"  {line}")

    print("\n[3] QR codes and passport page")
    path, content = make_qr(record, ROOT / "output")
    print(f"  design QR (passport URI, needs a server):  {path.relative_to(ROOT)}")
    path, _ = make_summary_qr(record, ROOT / "output")
    print(f"  demonstration QR (readable on any phone):  {path.relative_to(ROOT)}")
    demo_url_file = ROOT / "demo_url.txt"
    demo_url = demo_url_file.read_text(encoding="utf-8").strip() if demo_url_file.exists() else None
    page = render(record, ROOT / "output", demo_url)
    print(f"  passport page (open in a web browser):     {page.relative_to(ROOT)}")
    if demo_url:
        print(f"  online copy of the passport page:          {demo_url}")

    print("\n[4] Role-dependent views")
    for role in ROLES:
        v = view(record, role)
        print(f"  {role:8}: {len(v)} fields -> {', '.join(v)}")

    print("\n[5] Offline simulation of the MQTT-based A3 update")
    for label, msg, updated, probs in demo(valid_path):
        print(f"  {'RECORDED' if not probs else 'DISCARDED':9} {label}")
        for loc, m in probs:
            print(f"            - {loc}: {m}")
        if label == "valid message":
            ok &= not probs
            (ROOT / "output" / "batch-after-a3-update.json").write_text(
                json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            ok &= bool(probs)

    print("\n" + "=" * 72)
    print("RESULT:", "all checks behaved as expected" if ok else "SOME CHECKS DID NOT BEHAVE AS EXPECTED")

    card = summary_text(record).splitlines()
    width = max(len(line) for line in card) + 4
    print("\nYOUR CEMENT PASSPORT (accepted synthetic batch)")
    print("+" + "-" * width + "+")
    for line in card:
        print("|  " + line.ljust(width - 2) + "|")
    print("+" + "-" * width + "+")
    print("Open output/passport_" + record["batchID"] + ".html in a web browser to see the full passport and its QR code.")
    return ok


if __name__ == "__main__":
    buf = io.StringIO()
    with redirect_stdout(buf):
        success = run()
    text = buf.getvalue()
    print(text)
    (ROOT / "output").mkdir(exist_ok=True)
    (ROOT / "output" / "pilot_run_log.txt").write_text(text, encoding="utf-8")
    sys.exit(0 if success else 1)
