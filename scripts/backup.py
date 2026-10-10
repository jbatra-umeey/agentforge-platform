"""Online SQLite backup with integrity verification. Store backups encrypted outside the host."""

import argparse
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("source")
parser.add_argument("destination")
args = parser.parse_args()
if Path(args.destination).exists():
    raise SystemExit("Backup destination exists; choose a new filename")
source = sqlite3.connect("file:" + str(Path(args.source).resolve()) + "?mode=ro", uri=True)
with source, sqlite3.connect(args.destination) as target:
    source.backup(target)
    if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("Backup integrity check failed")
Path(args.destination).chmod(0o600)
print("Backup completed and verified")
