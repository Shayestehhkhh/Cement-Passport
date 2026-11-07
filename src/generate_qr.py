"""Generate QR codes for a DCP batch record.

Two QR codes are produced for a record that passes the schema:

1. ``qr_<batchID>_uri.png`` - the data carrier of the proposed design. It encodes only the
   passport URI (which contains the batchID); the passport data stay in the repository the
   URI points to. In this pilot the URI uses the reserved domain example.org, so scanning it
   opens no page: no passport server is operated.
2. ``qr_<batchID>_summary.png`` - a demonstration QR for this pilot only. It encodes a short
   plain-text summary of the cement passport, so that any phone can display the batch data
   offline, without a server.

Invalid records get no QR code.

Usage:
    python src/generate_qr.py examples/batch-valid.json [output_dir]
"""
import json
import sys
from pathlib import Path

import qrcode

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_passport import validate_record  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _a1_a3_gwp(record):
    by_module = {e["module"]: e for e in record["lcaIndicators"]["indicatorsPerModule"]}
    if "A1-A3" in by_module:
        return by_module["A1-A3"]["gwpTotal"]
    if all(m in by_module for m in ("A1", "A2", "A3")):
        return round(sum(by_module[m]["gwpTotal"] for m in ("A1", "A2", "A3")), 6)
    return None


def summary_text(record):
    """Short plain-text passport summary encoded in the demonstration QR.

    Kept short on purpose (about 150 characters) so that the QR stays small and is read
    reliably by phone cameras, also from a screen.
    """
    comp, safety, strength = record["composition"], record["safety"], record["strength"]
    gwp = _a1_a3_gwp(record)
    lines = [
        "CEMENT PASSPORT (synthetic example)",
        f"Batch {record['batchID']}",
        f"{comp['cementType']} {comp['strengthClass']}",
        f"Clinker {comp['clinkerRatio']:g}%  28d {strength['standardStrength28Days']:g} MPa",
        f"Cr(VI) {safety['solubleChromiumVI']:g} mg/kg (max 2)",
    ]
    if gwp is not None:
        unit = record["lcaIndicators"]["declaredUnit"]
        per = "/t" if unit == "1 t cement" else f" per {unit}"
        lines.append(f"GWP A1-A3 {gwp:g} kgCO2e{per}")
    return "\n".join(lines)


def _save_qr(content, target):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=4)
    qr.add_data(content)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(target)
    return target


def _check(record):
    problems = validate_record(record)
    if problems:
        raise ValueError(f"record rejected, no QR generated: {problems}")


def make_qr(record, out_dir=ROOT / "output"):
    """Design data carrier: QR with the passport URI only. Returns (path, encoded content)."""
    _check(record)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = _save_qr(record["passportURI"], out_dir / f"qr_{record['batchID']}_uri.png")
    return target, record["passportURI"]


def make_summary_qr(record, out_dir=ROOT / "output"):
    """Demonstration QR with a readable text summary. Returns (path, encoded content)."""
    _check(record)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    content = summary_text(record)
    target = _save_qr(content, out_dir / f"qr_{record['batchID']}_summary.png")
    return target, content


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as f:
        rec = json.load(f)
    out = sys.argv[2] if len(sys.argv) > 2 else ROOT / "output"
    p1, c1 = make_qr(rec, out)
    p2, c2 = make_summary_qr(rec, out)
    print(f"Design QR (passport URI): {p1}\n  content: {c1}")
    print(f"Demonstration QR (readable on any phone): {p2}\n  content:\n{c2}")
