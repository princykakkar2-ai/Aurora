"""
inspect_data.py
---------------
Step 2 of the Drug Interaction Graph Explorer pipeline (Phase 1).

Purpose:
    Examines the raw drug interactions dataset without modifying it.
    Identifies data structure, data types, missing values, severity distributions,
    and potential anomalies (such as duplicates, casing inconsistencies, and self-interactions).

Usage:
    python scripts/inspect_data.py
"""

from pathlib import Path
import sys
import pandas as pd


def get_raw_data_path() -> Path:
    """
    Resolves the absolute path to the raw dataset file.
    Works whether the script is run from the project root or the scripts/ directory.
    """
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "data" / "raw" / "interactions_raw.csv"


def load_raw_dataset(file_path: Path) -> pd.DataFrame:
    """
    Loads the raw CSV dataset into a pandas DataFrame.
    Provides a clear error message if the file is missing.
    """
    print("=" * 70)
    print("STEP 1: LOADING RAW DATASET")
    print("=" * 70)
    print(f"Target file: {file_path}")

    if not file_path.exists():
        print(f"\n[ERROR] File not found: {file_path}")
        print("Please ensure that 'data/raw/interactions_raw.csv' exists before running.")
        sys.exit(1)

    try:
        df = pd.read_csv(file_path)
        print(f"[SUCCESS] Dataset successfully loaded into memory.\n")
        return df
    except Exception as error:
        print(f"\n[ERROR] Failed to read CSV file: {error}")
        sys.exit(1)


def display_head(df: pd.DataFrame, num_rows: int = 5) -> None:
    """
    Displays the first few rows of the dataset.
    """
    print("-" * 70)
    print(f"FIRST {num_rows} ROWS (PREVIEW)")
    print("-" * 70)
    print(df.head(num_rows).to_string(index=True))
    print()


def display_dataset_shape_and_columns(df: pd.DataFrame) -> None:
    """
    Displays dimensions, column names, and column data types.
    """
    print("-" * 70)
    print("DIMENSIONS & COLUMN METADATA")
    print("-" * 70)
    total_rows, total_cols = df.shape
    print(f"Total rows    : {total_rows}")
    print(f"Total columns : {total_cols}")
    print("\nColumns and Data Types:")
    for column_name, dtype in df.dtypes.items():
        print(f"  - {column_name:<15}: {dtype}")
    print()


def display_missing_values(df: pd.DataFrame) -> None:
    """
    Counts and reports missing (null/NaN) values per column.
    Also checks for empty strings masquerading as valid entries.
    """
    print("-" * 70)
    print("MISSING VALUE ANALYSIS")
    print("-" * 70)
    missing_counts = df.isnull().sum()
    has_missing = False

    for column_name, count in missing_counts.items():
        # Check for whitespace-only strings
        empty_str_count = 0
        if df[column_name].dtype == "object":
            empty_str_count = df[column_name].dropna().apply(lambda x: str(x).strip() == "").sum()

        total_missing = count + empty_str_count
        if total_missing > 0:
            has_missing = True
            print(f"  [!] Column '{column_name}': {count} nulls + {empty_str_count} empty strings (Total: {total_missing})")
        else:
            print(f"  [OK] Column '{column_name}': 0 missing values")

    if not has_missing:
        print("  No missing values detected.")
    print()


def display_severity_distribution(df: pd.DataFrame) -> None:
    """
    Displays the unique values and frequency of the 'severity' column.
    """
    print("-" * 70)
    print("SEVERITY COLUMN INSPECTION")
    print("-" * 70)
    if "severity" not in df.columns:
        print("  [!] 'severity' column is missing from the dataset!")
        return

    # Count values including NaNs
    severity_counts = df["severity"].value_counts(dropna=False)
    print("Value counts (raw, case-sensitive):")
    for value, count in severity_counts.items():
        display_val = "<MISSING / NaN>" if pd.isna(value) else f"'{value}'"
        print(f"  - {display_val:<20} : {count} occurrences")
    print()


def detect_potential_anomalies(df: pd.DataFrame) -> None:
    """
    Detects potential data quality issues in the raw data without modifying it:
    1. Exact duplicate rows
    2. Case/whitespace inconsistencies in drug names
    3. Self-interactions (Drug A == Drug B)
    4. Reversed duplicate pairs (e.g. A-B and B-A)
    """
    print("-" * 70)
    print("POTENTIAL DATA QUALITY ANOMALIES")
    print("-" * 70)

    # 1. Exact duplicate rows
    exact_duplicates_count = df.duplicated().sum()
    if exact_duplicates_count > 0:
        print(f"  [!] Exact duplicate rows: {exact_duplicates_count} row(s)")
    else:
        print("  [OK] Exact duplicate rows: 0")

    # 2. Inconsistent whitespace and casing
    whitespace_issues = 0
    casing_issues = 0
    for col in ["drug_a", "drug_b"]:
        if col in df.columns:
            for val in df[col].dropna().astype(str):
                if val != val.strip():
                    whitespace_issues += 1
                if val != val.lower() and val != val.title() and val != val.upper():
                    # Mixed casing
                    casing_issues += 1

    if whitespace_issues > 0:
        print(f"  [!] Drug names with leading/trailing whitespace: {whitespace_issues} instance(s)")
    else:
        print("  [OK] No whitespace padding detected in drug names")

    # 3. Self-interactions (Drug A == Drug B)
    if "drug_a" in df.columns and "drug_b" in df.columns:
        self_interactions = df[
            df["drug_a"].astype(str).str.strip().str.lower()
            == df["drug_b"].astype(str).str.strip().str.lower()
        ]
        if not self_interactions.empty:
            print(f"  [!] Self-interactions found (Drug A == Drug B): {len(self_interactions)} row(s)")
            for idx, row in self_interactions.iterrows():
                print(f"      Row {idx}: drug_a='{row['drug_a']}', drug_b='{row['drug_b']}'")
        else:
            print("  [OK] No self-interactions detected")

        # 4. Normalized and reversed duplicates (undirected pairs)
        valid_pairs_df = df.dropna(subset=["drug_a", "drug_b"]).copy()
        valid_pairs_df["clean_a"] = valid_pairs_df["drug_a"].astype(str).str.strip().str.lower()
        valid_pairs_df["clean_b"] = valid_pairs_df["drug_b"].astype(str).str.strip().str.lower()

        # Build canonical pair tuple (min, max) to detect undirected equivalence
        valid_pairs_df["canonical_pair"] = valid_pairs_df.apply(
            lambda r: tuple(sorted([r["clean_a"], r["clean_b"]])), axis=1
        )
        duplicate_pairs_count = valid_pairs_df["canonical_pair"].duplicated(keep=False).sum()
        if duplicate_pairs_count > 0:
            unique_duplicated_pairs = valid_pairs_df[
                valid_pairs_df["canonical_pair"].duplicated(keep=False)
            ]["canonical_pair"].unique()
            print(f"  [!] Undirected duplicate pairs (A-B / B-A or repeated): {len(unique_duplicated_pairs)} unique pair(s) across {duplicate_pairs_count} rows")
            for pair in unique_duplicated_pairs:
                print(f"      Pair: {pair[0]} <-> {pair[1]}")
        else:
            print("  [OK] No undirected duplicate pairs detected")

    print()


def print_summary_report(df: pd.DataFrame) -> None:
    """
    Prints a concise closing summary of the inspection findings.
    """
    print("=" * 70)
    print("INSPECTION SUMMARY & NEXT STEPS")
    print("=" * 70)
    print("The raw dataset was inspected successfully with 0 modifications made.")
    print("Observed issues that need handling in scripts/clean_data.py:")
    print("  1. Remove rows missing drug_a or drug_b.")
    print("  2. Trim whitespace and normalize drug names to lowercase.")
    print("  3. Normalize severity strings and fill missing values with 'unknown'.")
    print("  4. Remove invalid self-interactions.")
    print("  5. Resolve undirected duplicate pairs (A-B and B-A) with a clear conflict policy.")
    print("  6. Extract unique drugs and assign deterministic drug IDs.")
    print("  7. Produce clean drugs.csv and interactions.csv tables.")
    print("=" * 70)


def main() -> None:
    """
    Main entry point for raw data inspection.
    """
    raw_data_path = get_raw_data_path()
    df = load_raw_dataset(raw_data_path)

    display_head(df, num_rows=5)
    display_dataset_shape_and_columns(df)
    display_missing_values(df)
    display_severity_distribution(df)
    detect_potential_anomalies(df)
    print_summary_report(df)


if __name__ == "__main__":
    main()
