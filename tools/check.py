#!/usr/bin/env python3
"""Validate data/certs.csv and data/ladders.txt and list every problem at once.

usage: python3 tools/check.py
"""
import csv, os, re, sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLS = ("label issuer_host name status status_note display_label display_name column link format intensity prereq tier "
        "tier_source board basis price_text price_kind source_url checked confidence").split()
DOMAINS = [(2, 4), (6, 6), (8, 14), (16, 17), (19, 27), (29, 31), (33, 33), (35, 40), (41, 47)]
errs, warns = [], []
with open(os.path.join(ROOT, "data", "certs.csv"), encoding="utf-8", newline="") as f:
    rd = csv.DictReader(f)
    if rd.fieldnames != COLS:
        sys.exit(f"data/certs.csv: the header row was changed. Expected:\n{','.join(COLS)}")
    rows = list(rd)
seen = {}
for n, r in enumerate(rows, start=2):
    who = f"line {n} ({r['label'] or '?'})"
    if None in r or any(v is None for v in r.values()):
        errs.append(f"{who}: wrong number of columns, check commas and quotes"); continue
    key = (r["label"], r["issuer_host"])
    if not r["label"] or not r["issuer_host"]:
        errs.append(f"{who}: label and issuer_host are required")
    if key in seen:
        errs.append(f"{who}: same label and issuer_host as line {seen[key]}")
    seen[key] = n
    if r["status"] not in ("", "flagged", "soon", "retired"):
        errs.append(f"{who}: status must be empty, flagged, soon or retired")
    if r["status"] in ("flagged", "retired") and not r["status_note"]:
        errs.append(f"{who}: status {r['status']} needs a reason in status_note")
    for c in ("link", "source_url"):
        if r[c] and not re.match(r"https?://", r[c].strip()):
            errs.append(f"{who}: {c} must start with http:// or https://")
    if r["checked"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["checked"]):
        errs.append(f"{who}: checked must be a date like 2026-11-25")
    if r["status"] == "retired":
        if not r["source_url"] or not r["checked"]:
            errs.append(f"{who}: a retired certification needs source_url and checked")
        continue
    if r["format"] not in "PXSEBQC" or len(r["format"]) != 1:
        errs.append(f"{who}: format must be one of P X S E B Q C")
    for c, hi in (("intensity", 5), ("prereq", 4), ("tier", 4), ("board", 1)):
        if not r[c].isdigit() or int(r[c]) > hi:
            errs.append(f"{who}: {c} must be a whole number from 0 to {hi}")
    if r["basis"] not in ("V", "K", "U"):
        errs.append(f"{who}: basis must be V, K or U")
    if r["column"]:
        if not r["column"].isdigit() or not any(lo <= int(r["column"]) <= hi for lo, hi in DOMAINS):
            errs.append(f"{who}: column {r['column']} is not inside a domain, see the table in CONTRIBUTING.md")
        if not r["link"] or not r["name"]:
            errs.append(f"{who}: a certification added through certs.csv needs name and link")
        elif urlparse(r["link"]).netloc.replace("www.", "") != r["issuer_host"]:
            errs.append(f"{who}: issuer_host must be the host of link without www ({urlparse(r['link']).netloc.replace('www.', '')})")
    if r["price_text"]:
        if not (r["price_kind"] and r["source_url"] and r["checked"] and r["confidence"]):
            errs.append(f"{who}: price_text needs price_kind, source_url, checked and confidence")
    elif r["label"] != "Programming Language":
        warns.append(f"{who}: no price_text")
    if r["basis"] == "V" and not r["source_url"]:
        warns.append(f"{who}: basis V but no source_url")

labels = {r["label"] for r in rows if r["status"] != "retired"}
for n, line in enumerate(open(os.path.join(ROOT, "data", "ladders.txt"), encoding="utf-8"), start=1):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    for name in re.split(r"[>|]", line):
        if name.strip() not in labels:
            errs.append(f"data/ladders.txt line {n}: {name.strip()!r} is not a label in certs.csv (or it is retired)")

for w in warns:
    print("warning:", w)
for e in errs:
    print("ERROR:", e)
print(f"{len(rows)} rows, {len(errs)} errors, {len(warns)} warnings")
sys.exit(1 if errs else 0)
