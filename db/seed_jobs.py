from pathlib import Path
import sys

# Add parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.database import JobDatabase


def seed_jobs():
    """Make sure every job in db/job_catalog.py exists in the database (safe to run repeatedly)."""
    db = JobDatabase()  # creating it already syncs the catalog
    added = db.sync_catalog()
    print(f"Database ready: {len(db.get_unique_jobs())} unique jobs ({added} added just now).")


if __name__ == "__main__":
    seed_jobs()
