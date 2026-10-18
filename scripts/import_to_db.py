"""
scripts/import_to_db.py
-----------------------
Step 4 of the Drug Interaction Graph Explorer pipeline (Phase 2).

Purpose:
    Imports processed Phase 1 CSV files (drugs.csv and interactions.csv) into PostgreSQL.
    Preserves existing integer IDs, severities, descriptions, and source provenance.

Features:
    - Creates tables if they do not exist.
    - Safe default: skips existing records to avoid accidental duplicate insertion.
    - Optional '--reset' flag: cleanly drops and recreates tables when explicitly requested.
    - Provides clear progress metrics and handles foreign-key errors gracefully.

Usage:
    python scripts/import_to_db.py
    python scripts/import_to_db.py --reset
"""

import sys
import argparse
from pathlib import Path
from typing import Tuple
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, IntegrityError

# Add project root to sys.path so backend package can be imported reliably
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import engine, SessionLocal, Base, get_database_url
from backend.models import Drug, Interaction


DRUGS_REQUIRED_COLS = ["drug_id", "name"]
INTERACTIONS_REQUIRED_COLS = ["interaction_id", "drug_a_id", "drug_b_id", "severity", "description", "source"]


def get_csv_paths() -> Tuple[Path, Path]:
    """Resolves processed CSV file paths."""
    drugs_path = PROJECT_ROOT / "data" / "processed" / "drugs.csv"
    interactions_path = PROJECT_ROOT / "data" / "processed" / "interactions.csv"
    return drugs_path, interactions_path


def load_and_validate_csvs(drugs_path: Path, interactions_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Loads both processed CSVs and validates presence of required columns.
    """
    if not drugs_path.exists():
        print(f"[ERROR] Processed drugs file not found at: {drugs_path}")
        print("Please run 'python scripts/clean_data.py' first.")
        sys.exit(1)

    if not interactions_path.exists():
        print(f"[ERROR] Processed interactions file not found at: {interactions_path}")
        print("Please run 'python scripts/clean_data.py' first.")
        sys.exit(1)

    drugs_df = pd.read_csv(drugs_path)
    interactions_df = pd.read_csv(interactions_path)

    # Validate columns
    missing_drug_cols = [c for c in DRUGS_REQUIRED_COLS if c not in drugs_df.columns]
    if missing_drug_cols:
        print(f"[ERROR] drugs.csv is missing required columns: {missing_drug_cols}")
        sys.exit(1)

    missing_inter_cols = [c for c in INTERACTIONS_REQUIRED_COLS if c not in interactions_df.columns]
    if missing_inter_cols:
        print(f"[ERROR] interactions.csv is missing required columns: {missing_inter_cols}")
        sys.exit(1)

    return drugs_df, interactions_df


def test_database_connection():
    """
    Verifies that the database is reachable before proceeding.
    """
    try:
        url = get_database_url()
        # Mask password for secure display
        masked_url = url
        if "@" in url and "://" in url:
            prefix, rest = url.split("://", 1)
            credentials, host_db = rest.split("@", 1)
            if ":" in credentials:
                user = credentials.split(":", 1)[0]
                masked_url = f"{prefix}://{user}:*****@{host_db}"

        print(f"Connecting to database: {masked_url}")
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[SUCCESS] Database connection established successfully.")
    except RuntimeError as config_err:
        print(config_err)
        sys.exit(1)
    except OperationalError as op_err:
        print(f"\n[ERROR] Unable to connect to PostgreSQL: {op_err}")
        print("\nPlease check that:")
        print("  1. PostgreSQL service is running on your machine.")
        print("  2. The database 'drug_graph' exists (CREATE DATABASE drug_graph;).")
        print("  3. Credentials in '.env' are correct.")
        sys.exit(1)
    except Exception as general_err:
        print(f"\n[ERROR] Unexpected error connecting to database: {general_err}")
        sys.exit(1)


def reset_tables():
    """
    Drops and recreates all tables when --reset is explicitly requested.
    """
    print("Dropping existing tables per --reset flag...")
    Base.metadata.drop_all(bind=engine)
    print("Creating clean tables...")
    Base.metadata.create_all(bind=engine)
    print("[SUCCESS] Database schema initialized freshly.")


def import_drugs(drugs_df: pd.DataFrame, session) -> Tuple[int, int]:
    """
    Imports drugs from drugs_df into the drugs table.
    Preserves exact drug_id values. Skips already existing records.
    """
    existing_ids = {row[0] for row in session.query(Drug.drug_id).all()}

    imported = 0
    skipped = 0

    for _, row in drugs_df.iterrows():
        drug_id = int(row["drug_id"])
        name = str(row["name"]).strip()

        if drug_id in existing_ids:
            skipped += 1
            continue

        drug = Drug(drug_id=drug_id, name=name)
        session.add(drug)
        existing_ids.add(drug_id)
        imported += 1

    session.commit()
    return imported, skipped


def import_interactions(interactions_df: pd.DataFrame, session) -> Tuple[int, int]:
    """
    Imports interactions from interactions_df into the interactions table.
    Preserves exact interaction_id values. Skips already existing records.
    """
    existing_ids = {row[0] for row in session.query(Interaction.interaction_id).all()}
    existing_pairs = {
        (row[0], row[1]) for row in session.query(Interaction.drug_a_id, Interaction.drug_b_id).all()
    }

    imported = 0
    skipped = 0

    for _, row in interactions_df.iterrows():
        interaction_id = int(row["interaction_id"])
        drug_a_id = int(row["drug_a_id"])
        drug_b_id = int(row["drug_b_id"])
        severity = str(row["severity"]).strip()
        description = None if pd.isna(row["description"]) else str(row["description"]).strip()
        source = None if pd.isna(row["source"]) else str(row["source"]).strip()

        # Enforce canonical order: drug_a_id < drug_b_id
        min_id, max_id = sorted([drug_a_id, drug_b_id])

        if interaction_id in existing_ids or (min_id, max_id) in existing_pairs:
            skipped += 1
            continue

        interaction = Interaction(
            interaction_id=interaction_id,
            drug_a_id=min_id,
            drug_b_id=max_id,
            severity=severity,
            description=description,
            source=source,
        )
        session.add(interaction)
        existing_ids.add(interaction_id)
        existing_pairs.add((min_id, max_id))
        imported += 1

    session.commit()
    return imported, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Import processed Phase 1 CSV files into the PostgreSQL database."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables before importing (caution: removes existing data).",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("STEP 4: IMPORTING PROCESSED CSV DATA INTO DATABASE")
    print("=" * 70)

    # 1. Load CSVs
    drugs_path, interactions_path = get_csv_paths()
    drugs_df, interactions_df = load_and_validate_csvs(drugs_path, interactions_path)
    print(f"Loaded {len(drugs_df)} drugs from: {drugs_path}")
    print(f"Loaded {len(interactions_df)} interactions from: {interactions_path}\n")

    # 2. Test Connection
    test_database_connection()

    # 3. Create or Reset Tables
    if args.reset:
        reset_tables()
    else:
        # Create tables if they do not exist
        Base.metadata.create_all(bind=engine)

    # 4. Perform Import
    session = SessionLocal()
    try:
        print("\nImporting drugs...")
        imported_drugs, skipped_drugs = import_drugs(drugs_df, session)

        print("Importing interactions...")
        imported_interactions, skipped_interactions = import_interactions(interactions_df, session)

        print("\n" + "=" * 70)
        print("IMPORT SUMMARY")
        print("=" * 70)
        print(f"Imported drugs               : {imported_drugs}")
        print(f"Imported interactions        : {imported_interactions}")
        print(f"Skipped existing drugs       : {skipped_drugs}")
        print(f"Skipped existing interactions: {skipped_interactions}")
        print("=" * 70)
        print("Database is ready! You can now launch FastAPI:")
        print("  uvicorn backend.main:app --reload")
        print("=" * 70)

    except IntegrityError as integ_err:
        session.rollback()
        print(f"\n[ERROR] Foreign key or integrity constraint violation: {integ_err}")
        print("Ensure all drug_a_id and drug_b_id references exist in the drugs table.")
        sys.exit(1)
    except Exception as err:
        session.rollback()
        print(f"\n[ERROR] Failed to import data: {err}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
