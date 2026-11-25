#!/usr/bin/env python3
"""Rebuild index.html and the generated files in data/ from data/certs.csv.

usage: python3 tools/make.py

Runs the three steps (grid -> build -> rank) and checks that the chart still has
27 rows of 47 columns. Exits non-zero with a message if anything is wrong.
"""
import os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, "tools")
SRC = os.path.join(ROOT, "source", "Security-Certification-Roadmap9.html")
PY = [sys.executable, "-I"]


def run(*args):
    p = subprocess.run([*PY, *args], cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        sys.stderr.write(p.stdout + p.stderr)
        sys.exit(p.returncode)
    return p.stdout


with tempfile.TemporaryDirectory() as tmp:
    cells, built = os.path.join(tmp, "cells.json"), os.path.join(tmp, "built.html")
    run(os.path.join(T, "grid.py"), SRC, cells)
    run(os.path.join(T, "build.py"), SRC, cells, built)
    out = run(os.path.join(T, "rank.py"), built, os.path.join(ROOT, "index.html"), os.path.join(ROOT, "data", "ranked.csv"))
    rows = [l.split() for l in run(os.path.join(T, "grid.py"), os.path.join(ROOT, "index.html")).splitlines()[1:]]
    bad = [r for r in rows if len(r) > 1 and r[1] != "47"]
    if len(rows) != 27 or bad:
        sys.exit(f"chart layout is broken: expected 27 rows of 47 columns, got {len(rows)} rows, bad rows {bad}")
print([l for l in out.splitlines() if l.startswith("items")][0])
print("still inverted:", [l for l in out.splitlines() if l.startswith("still inverted")][0].split(":", 1)[1].strip())
print("OK: index.html and data/*.csv rebuilt")
