"""Regenerate chordpro sheets from source_url when full/easy drift from the tab."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.database import SessionLocal, init_db
from services.enrichment import repair_drifted_sheets


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        summary = repair_drifted_sheets(db)
        db.commit()
        print(
            f"Repair done: scanned={summary.scanned} repaired={summary.repaired} "
            f"skipped={summary.skipped} failed={summary.failed}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
