"""
One-time, OPT-IN migration: relabel any existing seats.status == 'BAG' to 'OBJECT'.

Context: the seat-classification label was renamed BAG -> OBJECT (sketch + GUI +
backend + frontend). Historical seat rows written before the rename still hold the
string 'BAG'; with the old BAG->BAG_DETECTED response alias removed, the frontend
now renders those rows as an unlabelled/neutral tile until they are reclassified by
a fresh sensor reading.

This script fixes only the going-forward classification column `seats.status`.
It does NOT touch trips, billing, or the vehicle_log_entries event text (that
audit history is left verbatim).

Dry-run by default. Pass --yes to actually commit.

    python relabel_bag_to_object.py          # show what would change
    python relabel_bag_to_object.py --yes     # apply
"""
import sys
import sqlite3
from database import DATABASE_URL

DB_PATH = DATABASE_URL.replace("sqlite:///", "", 1)
APPLY = "--yes" in sys.argv[1:]

conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    "SELECT shuttle_id, seat_number FROM seats WHERE status = 'BAG' ORDER BY shuttle_id, seat_number"
).fetchall()

if not rows:
    print("No seats with status 'BAG' found. Nothing to do.")
    conn.close()
    sys.exit(0)

print(f"{len(rows)} seat row(s) currently classified 'BAG':")
for shuttle_id, seat_number in rows:
    print(f"  {shuttle_id} seat {seat_number}:  BAG -> OBJECT")

if not APPLY:
    print("\nDry run only. Re-run with --yes to apply these changes.")
    conn.close()
    sys.exit(0)

conn.execute("UPDATE seats SET status = 'OBJECT' WHERE status = 'BAG'")
conn.commit()
print(f"\nApplied: {len(rows)} row(s) updated 'BAG' -> 'OBJECT'.")
conn.close()
