#!/bin/sh
# Runs the whole pipeline in chronological order. Needs: python3 (+ matplotlib numpy markdown), g++ (C++17).
set -e
mkdir -p Data processed results
for f in Distance.gz Travel_Time.gz Coordinates.gz; do
  [ -f "Data/$f" ] || { echo "missing Data/$f (see README for download links)"; exit 1; }
done
echo "[1/3] preprocessing (Python)";                          python3 Preprocessing.py
echo "[2/3] compiling (C++) and running experiments (Python)"; python3 experiments.py
echo "[3/3] analysis (Python)";                                python3 Analysis.py
echo "Done. Open results/report.html (single-page report) or results/report.md"