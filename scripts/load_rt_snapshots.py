"""Load RT snapshots into DuckDB in batches to avoid memory overload."""
import duckdb
from pathlib import Path
import glob

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "ttc.duckdb"
RAW = ROOT / "raw" / "vehicle_positions"

files = sorted(glob.glob(str(RAW / "**" / "*.json"), recursive=True))
print(f"Found {len(files)} snapshot files")

con = duckdb.connect(str(DB))
con.execute("DROP TABLE IF EXISTS raw_rt_vehicle_positions")

BATCH = 30  # process 30 files at a time
first = True
for i in range(0, len(files), BATCH):
    batch = files[i:i+BATCH]
    # build a list of quoted paths for this batch
    paths = "[" + ",".join(f"'{f.replace(chr(92), '/')}'" for f in batch) + "]"
    if first:
        con.execute(f"""
            CREATE TABLE raw_rt_vehicle_positions AS
            SELECT filename, unnest(entity) AS entity
            FROM read_json({paths}, filename=true, union_by_name=true)
        """)
        first = False
    else:
        con.execute(f"""
            INSERT INTO raw_rt_vehicle_positions
            SELECT filename, unnest(entity) AS entity
            FROM read_json({paths}, filename=true, union_by_name=true)
        """)
    print(f"  loaded batch {i//BATCH + 1} ({len(batch)} files)")

n = con.execute("SELECT count(*) FROM raw_rt_vehicle_positions").fetchone()[0]
print(f"Done. Total: {n:,} vehicle-rows")
con.close()