"""Peek inside the latest snapshot — show what a vehicle record looks like, and find route 102."""
import json
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "raw" / "vehicle_positions"
# grab the most recent snapshot file
latest = max(RAW.rglob("snapshot_*.json"), key=lambda p: p.stat().st_mtime)
print(f"Reading: {latest.name}\n")

data = json.loads(latest.read_text())
entities = data.get("entity", [])
print(f"Total vehicles: {len(entities)}\n")

# show the FULL structure of one vehicle so you see the fields
print("=== One vehicle record (structure) ===")
print(json.dumps(entities[0], indent=2))

# now find route 102 vehicles
print("\n=== Route 102 vehicles in this snapshot ===")
count = 0
for e in entities:
    v = e.get("vehicle", {})
    route = v.get("trip", {}).get("routeId", "")
    if route == "102":
        pos = v.get("position", {})
        print(f"  vehicle {v.get('vehicle',{}).get('id','?')}: "
              f"lat={pos.get('latitude')}, lon={pos.get('longitude')}, "
              f"trip={v.get('trip',{}).get('tripId','?')}")
        count += 1
print(f"\nRoute 102 vehicles found: {count}")