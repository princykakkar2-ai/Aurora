"""
validate_data.py
----------------
Step 4 of the Drug Interaction Graph Explorer pipeline (Phase 1).

Purpose:
    Validates the integrity, relational consistency, and quality of the processed
    datasets (drugs.csv and interactions.csv). Ensures that the data is 100%
    ready for future graph modeling (Phase 2).

Validations Performed:
    1. Drug IDs are unique.
    2. Interaction IDs are unique.
    3. No drug ID is missing (in drugs.csv or interactions.csv).
    4. Referential integrity: Every drug_a_id exists in drugs.csv.
    5. Referential integrity: Every drug_b_id exists in drugs.csv.
    6. No unwanted self-interactions exist (drug_a_id != drug_b_id).
    7. No accidental duplicate undirected pairs exist (A-B and B-A uniqueness).
    8. Severity values belong to the allowed set {'minor', 'moderate', 'major', 'unknown'}.
    9. Source / provenance information is preserved where available.
   10. Descriptions are preserved without blank entries.

Usage:
    python scripts/validate_data.py
"""

from pathlib import Path
import sys
from typing import List, Tuple
import pandas as pd


ALLOWED_SEVERITIES = {"minor", "moderate", "major", "unknown"}


def get_processed_paths() -> Tuple[Path, Path]:
    """
    Returns (drugs_csv_path, interactions_csv_path) relative to the project root.
    """
    project_root = Path(__file__).resolve().parent.parent
    drugs_path = project_root / "data" / "processed" / "drugs.csv"
    interactions_path = project_root / "data" / "processed" / "interactions.csv"
    return drugs_path, interactions_path


def load_processed_data(drugs_path: Path, interactions_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Loads both processed CSVs, checking for file existence.
    """
    if not drugs_path.exists() or not interactions_path.exists():
        print("[ERROR] Processed data files not found!")
        print(f"  Missing: {drugs_path if not drugs_path.exists() else interactions_path}")
        print("Please run 'python scripts/clean_data.py' first to generate processed files.")
        sys.exit(1)

    try:
        drugs_df = pd.read_csv(drugs_path)
        interactions_df = pd.read_csv(interactions_path)
        return drugs_df, interactions_df
    except Exception as error:
        print(f"[ERROR] Failed to read processed CSV files: {error}")
        sys.exit(1)


def validate_drug_ids_unique(drugs_df: pd.DataFrame, failure_reasons: List[str]) -> bool:
    """Check 1: drug IDs in drugs.csv must be unique."""
    if drugs_df["drug_id"].is_unique:
        print(f"PASS: All drug IDs are unique ({len(drugs_df)} unique IDs found).")
        return True
    duplicates = drugs_df[drugs_df["drug_id"].duplicated(keep=False)]["drug_id"].tolist()
    failure_reasons.append(f"Duplicate drug IDs found in drugs.csv: {duplicates}")
    print(f"FAIL: Duplicate drug IDs found: {duplicates}")
    return False


def validate_interaction_ids_unique(interactions_df: pd.DataFrame, failure_reasons: List[str]) -> bool:
    """Check 2: interaction IDs in interactions.csv must be unique."""
    if interactions_df["interaction_id"].is_unique:
        print(f"PASS: All interaction IDs are unique ({len(interactions_df)} unique IDs found).")
        return True
    duplicates = interactions_df[interactions_df["interaction_id"].duplicated(keep=False)]["interaction_id"].tolist()
    failure_reasons.append(f"Duplicate interaction IDs found in interactions.csv: {duplicates}")
    print(f"FAIL: Duplicate interaction IDs found: {duplicates}")
    return False


def validate_no_missing_ids(drugs_df: pd.DataFrame, interactions_df: pd.DataFrame, failure_reasons: List[str]) -> bool:
    """Check 3: No drug ID or interaction reference should be null/missing."""
    passed = True
    if drugs_df["drug_id"].isnull().any():
        failure_reasons.append("Missing/null drug_id found in drugs.csv.")
        print("FAIL: Missing/null drug_id values detected in drugs.csv.")
        passed = False

    if drugs_df["name"].isnull().any():
        failure_reasons.append("Missing/null drug name found in drugs.csv.")
        print("FAIL: Missing/null drug names detected in drugs.csv.")
        passed = False

    if interactions_df["drug_a_id"].isnull().any() or interactions_df["drug_b_id"].isnull().any():
        failure_reasons.append("Missing/null drug reference (drug_a_id or drug_b_id) in interactions.csv.")
        print("FAIL: Missing/null drug references detected in interactions.csv.")
        passed = False

    if passed:
        print("PASS: No drug ID or reference fields are missing.")
    return passed


def validate_referential_integrity(drugs_df: pd.DataFrame, interactions_df: pd.DataFrame, failure_reasons: List[str]) -> bool:
    """Check 4 & 5: Every drug_a_id and drug_b_id must exist in drugs.csv."""
    valid_drug_ids = set(drugs_df["drug_id"])
    invalid_a = set(interactions_df["drug_a_id"]) - valid_drug_ids
    invalid_b = set(interactions_df["drug_b_id"]) - valid_drug_ids

    passed = True
    if invalid_a:
        failure_reasons.append(f"interactions.csv contains drug_a_id references not in drugs.csv: {invalid_a}")
        print(f"FAIL: Invalid drug_a_id references: {invalid_a}")
        passed = False

    if invalid_b:
        failure_reasons.append(f"interactions.csv contains drug_b_id references not in drugs.csv: {invalid_b}")
        print(f"FAIL: Invalid drug_b_id references: {invalid_b}")
        passed = False

    if passed:
        print("PASS: All interaction references are valid (referential integrity verified).")
    return passed


def validate_no_self_interactions(interactions_df: pd.DataFrame, failure_reasons: List[str]) -> bool:
    """Check 6: No row should have drug_a_id == drug_b_id."""
    self_inter = interactions_df[interactions_df["drug_a_id"] == interactions_df["drug_b_id"]]
    if self_inter.empty:
        print("PASS: No self-interactions found.")
        return True
    failure_reasons.append(f"Self-interactions detected in interactions.csv: {self_inter.to_dict(orient='records')}")
    print(f"FAIL: Self-interactions detected in {len(self_inter)} row(s).")
    return False


def validate_no_duplicate_undirected_pairs(interactions_df: pd.DataFrame, failure_reasons: List[str]) -> bool:
    """Check 7: No accidental duplicate undirected pairs (A-B and B-A)."""
    canonical_pairs = interactions_df.apply(
        lambda r: tuple(sorted([int(r["drug_a_id"]), int(r["drug_b_id"])])), axis=1
    )
    duplicates = canonical_pairs[canonical_pairs.duplicated(keep=False)]
    if duplicates.empty:
        print("PASS: No duplicate undirected interaction pairs found.")
        return True
    unique_dup_pairs = duplicates.unique().tolist()
    failure_reasons.append(f"Duplicate undirected pairs detected: {unique_dup_pairs}")
    print(f"FAIL: Duplicate undirected pairs detected: {unique_dup_pairs}")
    return False


def validate_severity_values(interactions_df: pd.DataFrame, failure_reasons: List[str]) -> bool:
    """Check 8: Severity values must belong to the allowed set."""
    actual_severities = set(interactions_df["severity"].dropna().unique())
    invalid_severities = actual_severities - ALLOWED_SEVERITIES

    if not invalid_severities:
        print(f"PASS: Severity values belong to the allowed set {sorted(ALLOWED_SEVERITIES)}.")
        return True
    failure_reasons.append(f"Invalid severity values detected: {invalid_severities}")
    print(f"FAIL: Invalid severity values detected: {invalid_severities}")
    return False


def validate_provenance_and_descriptions(interactions_df: pd.DataFrame, failure_reasons: List[str]) -> bool:
    """Check 9 & 10: Source and description fields must be preserved and non-empty."""
    missing_sources = interactions_df["source"].isnull() | (interactions_df["source"].astype(str).str.strip() == "")
    missing_descs = interactions_df["description"].isnull() | (interactions_df["description"].astype(str).str.strip() == "")

    passed = True
    if missing_sources.any():
        count = missing_sources.sum()
        failure_reasons.append(f"{count} interaction row(s) have missing source/provenance.")
        print(f"FAIL: Missing source/provenance in {count} row(s).")
        passed = False

    if missing_descs.any():
        count = missing_descs.sum()
        failure_reasons.append(f"{count} interaction row(s) have missing descriptions.")
        print(f"FAIL: Missing description in {count} row(s).")
        passed = False

    if passed:
        print("PASS: Source/provenance and interaction descriptions are properly preserved.")
    return passed


def main() -> None:
    """
    Main orchestration function running all Phase 1 validation tests.
    """
    drugs_path, interactions_path = get_processed_paths()

    print("=" * 70)
    print("STEP 3: RUNNING PROCESSED DATA VALIDATION")
    print("=" * 70)
    print(f"Checking:")
    print(f"  1. {drugs_path}")
    print(f"  2. {interactions_path}")
    print("-" * 70)

    drugs_df, interactions_df = load_processed_data(drugs_path, interactions_path)

    failure_reasons: List[str] = []

    # Run all validation rules
    validate_drug_ids_unique(drugs_df, failure_reasons)
    validate_interaction_ids_unique(interactions_df, failure_reasons)
    validate_no_missing_ids(drugs_df, interactions_df, failure_reasons)
    validate_referential_integrity(drugs_df, interactions_df, failure_reasons)
    validate_no_self_interactions(interactions_df, failure_reasons)
    validate_no_duplicate_undirected_pairs(interactions_df, failure_reasons)
    validate_severity_values(interactions_df, failure_reasons)
    validate_provenance_and_descriptions(interactions_df, failure_reasons)

    print("=" * 70)
    if not failure_reasons:
        print("SUMMARY: ALL VALIDATION CHECKS PASSED (10/10)")
        print("=" * 70)
        print("The processed data is clean, consistent, and ready for graph modeling.")
        sys.exit(0)
    else:
        print(f"SUMMARY: {len(failure_reasons)} VALIDATION CHECK(S) FAILED")
        print("=" * 70)
        for idx, reason in enumerate(failure_reasons, start=1):
            print(f"  {idx}. {reason}")
        print("\nPlease fix the data cleaning pipeline and re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
