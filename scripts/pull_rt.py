"""
pull_rt.py — pulls live GTFS-Realtime vehicle positions from the TTC's own feed.
Free, no API key. Same script works as historical puller and live poller.
Run: python scripts/pull_rt.py
"""
import json, time, requests
from pathlib import Path
from datetime import datetime, timezone
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "raw" / "vehicle_positions"
TTC_VP_URL = "https://bustime.ttc.ca/gtfsrt/vehicles"

def land_snapshot(payload: dict) -> Path:
    now = datetime.now(timezone.utc)
    date_dir = RAW_DIR / f"date={now:%Y-%m-%d}"
    date_dir.mkdir(parents=True, exist_ok=True)
    out = date_dir / f"snapshot_{now:%Y%m%dT%H%M%SZ}.json"
    out.write_text(json.dumps(payload))
    return out

def pull_once():
    resp = requests.get(TTC_VP_URL, timeout=30)
    resp.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)
    data = MessageToDict(feed)
    path = land_snapshot(data)
    n = len(data.get("entity", []))
    print(f"  landed {path.name}  ({n} vehicles in snapshot)")
    return path

def pull_loop(n_snapshots=5, seconds_between=60):
    print(f"Pulling {n_snapshots} snapshots, {seconds_between}s apart...")
    for i in range(n_snapshots):
        try:
            pull_once()
        except Exception as e:
            print(f"  ! snapshot {i} failed: {e}")
        if i < n_snapshots - 1:
            time.sleep(seconds_between)
    print("Done.")

if __name__ == "__main__":
    pull_loop(n_snapshots=360, seconds_between=30)