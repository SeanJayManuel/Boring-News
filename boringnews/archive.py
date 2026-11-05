"""Rebuild the database from the daily edition files (see edition.py).

    python -m boringnews.archive restore            # archive/ -> data/boringnews.db
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .edition import restore


def main(argv=None):
    ap = argparse.ArgumentParser(prog="boringnews.archive")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("restore", help="rebuild the database from archive files")
    r.add_argument("--from", dest="src", default=str(config.ARCHIVE_DIR))
    r.add_argument("--db", default=str(config.DB_PATH))
    args = ap.parse_args(argv)
    n = restore(Path(args.src), Path(args.db))
    print(f"Restored {n} editions into {args.db}.")


if __name__ == "__main__":
    main()
