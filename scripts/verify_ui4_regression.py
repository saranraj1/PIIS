"""Verify UI-4.1 regression baseline against UI-3.2 manifest."""

import hashlib
import os

manifest_path = os.path.join("docs", "ui", "UI3_2_REGRESSION_MANIFEST.md")
with open(manifest_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

matches = []
for line in lines:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) >= 4 and "tests" in parts[1]:
        fpath = parts[1].replace("`", "").strip()
        fhash = parts[2].replace("`", "").strip()
        tcount = int(parts[3])
        matches.append((fpath, fhash, tcount))

print(f"Parsed {len(matches)} files from UI-3.2 manifest.")

match_count = 0
mismatch_count = 0
for filepath, expected_hash, test_count in matches:
    norm_path = os.path.normpath(filepath)
    if not os.path.exists(norm_path):
        print(f"MISSING: {norm_path}")
        mismatch_count += 1
        continue
    with open(norm_path, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()
    if actual_hash == expected_hash:
        match_count += 1
    else:
        print(f"HASH MISMATCH: {norm_path}")
        print(f"  expected={expected_hash}")
        print(f"  actual=  {actual_hash}")
        mismatch_count += 1

print(f"Reconciliation: {match_count} exact hash matches, {mismatch_count} mismatches out of {len(matches)} files.")
