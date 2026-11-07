#!/bin/sh
# Run from Terminal:  sh run_pilot_mac_linux.sh
# Creates a private Python environment in the folder ".venv" (nothing is installed system-wide).
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Creating a private Python environment (first run only)..."
  python3 -m venv .venv || { echo "Python 3 not found. Install it from https://www.python.org/downloads/"; exit 1; }
fi
.venv/bin/python -m pip install -q -r requirements.txt || exit 1
echo "===== Running the pilot ====="
.venv/bin/python src/run_pilot.py
echo "===== Running the automated tests ====="
.venv/bin/python -m unittest discover -s tests -v
echo "Done. The QR code and the log are in the output folder."
