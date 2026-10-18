"""
clean_data.py
-------------
Step 3 of the Drug Interaction Graph Explorer pipeline (Phase 1).

Purpose:
    Cleans, normalizes, and transforms the raw interaction dataset into two
    relational CSV files ready for graph representation:
      1. data/processed/drugs.csv        (Nodes)
      2. data/processed/interactions.csv (Edges)

Duplicate & Conflict Policy:
    In an undirected graph, an interaction between Drug A and Drug B is identical
    to an interaction between Drug B and Drug A (A-B == B-A).
    When duplicate records exist for the same canonical drug pair:
      - If severities are identical:
          We keep that severity and combine unique provenance sources and descriptions.
      - If severities conflict (e.g., 'minor' vs 'moderate'):
          We DO NOT silently discard conflicting records.
          Instead, we apply a conservative clinical safety policy:
          1. Resolve to the highest reported severity ranking:
             unknown (0) < minor (1) < moderate (2) < major (3).
          2. Document the conflict transparently in the description field with an audit note.
          3. Combine all distinct source names to preserve complete provenance.

Usage:
    python scripts/clean_data.py
"""

from pathlib import Path
import sys
from typing import Dict, List, Tuple
import pandas as pd


# Required input columns in the raw dataset
REQUIRED_COLUMNS = ["drug_a", "drug_b", "severity", "description", "source"]

# Allowed normalized severity values
ALLOWED_SEVERITIES = ["unknown", "minor", "moderate", "major"]

# Severity ranking for conservative conflict resolution (higher = more critical)
SEVERITY_HIERARCHY = {
    "unknown": 0,
    "minor": 1,
    "moderate": 2,
    "major": 3,
}


def get_project_paths() -> Tuple[Path, Path, Path]:
    """
    Returns (raw_csv_path, processed_drugs_path, processed_interactions_path)
    relative to the project root.
    """
    project_root = Path(__file__).resolve().parent.parent
    raw_path = project_root / "data" / "raw" / "interactions_raw.csv"
    processed_dir = project_root / "data" / "processed"
    drugs_path = processed_dir / "drugs.csv"
    interactions_path = processed_dir / "interactions.csv"
    return raw_path, drugs_path, interactions_path


def load_and_validate_columns(file_path: Path) -> pd.DataFrame:
    """
    Loads raw CSV and checks for presence of required columns.
    """
    if not file_path.exists():
        print(f"[ERROR] Raw data file not found at: {file_path}")
        print("Please verify the file exists or run from the project root.")
        sys.exit(1)

    df = pd.read_csv(file_path)
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        print(f"[ERROR] Missing required columns in raw CSV: {missing_cols}")
        print(f"Expected columns: {REQUIRED_COLUMNS}")
        sys.exit(1)

    return df


def remove_missing_drugs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Removes rows where either drug_a or drug_b is null, NaN, or whitespace only.
    """
    initial_count = len(df)

    # Condition: non-null and non-empty after stripping
    valid_drug_a = df["drug_a"].notna() & (df["drug_a"].astype(str).str.strip() != "")
    valid_drug_b = df["drug_b"].notna() & (df["drug_b"].astype(str).str.strip() != "")
    cleaned_df = df[valid_drug_a & valid_drug_b].copy()

    dropped_count = initial_count - len(cleaned_df)
    print(f"  - Dropped {dropped_count} row(s) missing 'drug_a' or 'drug_b'.")
    return cleaned_df


def normalize_strings_and_severities(df: pd.DataFrame) -> pd.DataFrame:
    """
    1. Normalizes drug names by trimming whitespace and converting to lowercase.
    2. Normalizes severity values: trims whitespace, converts to lowercase,
       and replaces missing/empty severities with 'unknown'.
       Never guesses a medical severity.
    3. Trims whitespace for description and source.
    """
    cleaned_df = df.copy()

    # Normalize drug names
    cleaned_df["drug_a"] = cleaned_df["drug_a"].astype(str).str.strip().str.lower()
    cleaned_df["drug_b"] = cleaned_df["drug_b"].astype(str).str.strip().str.lower()

    # Normalize severities: handle missing/empty values by assigning 'unknown'
    def clean_severity(val) -> str:
        if pd.isna(val) or str(val).strip() == "":
            return "unknown"
        normalized = str(val).strip().lower()
        if normalized not in SEVERITY_HIERARCHY:
            print(f"    [WARNING] Unrecognized severity '{val}' found. Defaulting to 'unknown'.")
            return "unknown"
        return normalized

    cleaned_df["severity"] = cleaned_df["severity"].apply(clean_severity)

    # Clean description and source
    cleaned_df["description"] = (
        cleaned_df["description"]
        .fillna("No description provided.")
        .astype(str)
        .str.strip()
    )
    cleaned_df["source"] = (
        cleaned_df["source"]
        .fillna("Unknown Source")
        .astype(str)
        .str.strip()
    )

    print("  - Normalized drug names (trimmed and converted to lowercase).")
    print("  - Normalized severity values and replaced missing/blank values with 'unknown'.")
    return cleaned_df


def remove_self_interactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifies and removes self-interactions (where drug_a == drug_b).
    """
    is_self = df["drug_a"] == df["drug_b"]
    self_count = is_self.sum()

    if self_count > 0:
        dropped_examples = df[is_self][["drug_a", "drug_b"]].to_dict(orient="records")
        print(f"  - Dropped {self_count} self-interaction row(s): {dropped_examples}")
        return df[~is_self].copy()

    print("  - No self-interactions detected.")
    return df.copy()


def resolve_duplicate_interactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Treats drug interactions as undirected pairs (A-B == B-A).
    Groups records by canonical pair (min_drug, max_drug).
    
    Conflict & Deduplication Policy:
      1. If multiple records for the same pair have the SAME severity:
         - Keep the severity.
         - Combine unique sources (e.g. 'Source A; Source B').
         - Combine unique descriptions.
      2. If multiple records have CONFLICTING severities:
         - Select the highest severity (conservative clinical safety principle).
         - Annotate the description with an explicit audit note:
           '[CONFLICT RESOLVED: Reported severities: ...; selected highest ...]'
         - Combine all distinct sources to preserve provenance.
    """
    # Create canonical pair columns
    canonical_a = []
    canonical_b = []
    for _, row in df.iterrows():
        drug1, drug2 = sorted([row["drug_a"], row["drug_b"]])
        canonical_a.append(drug1)
        canonical_b.append(drug2)

    df_canonical = df.copy()
    df_canonical["canonical_a"] = canonical_a
    df_canonical["canonical_b"] = canonical_b

    resolved_rows = []
    # Group by the undirected canonical pair
    grouped = df_canonical.groupby(["canonical_a", "canonical_b"], sort=False)

    for (drug1, drug2), group in grouped:
        unique_severities = sorted(group["severity"].unique())
        unique_sources = sorted(group["source"].unique())
        unique_descriptions = list(dict.fromkeys(group["description"].dropna()))

        # Check for conflicts
        if len(unique_severities) == 1:
            chosen_severity = unique_severities[0]
            merged_description = " | ".join(unique_descriptions)
        else:
            # Conflict detected: resolve by choosing highest severity rank
            chosen_severity = max(
                unique_severities,
                key=lambda sev: SEVERITY_HIERARCHY.get(sev, 0)
            )
            conflict_note = (
                f"[CONFLICT RESOLVED: Severities reported were {unique_severities}. "
                f"Selected '{chosen_severity}' following conservative clinical safety policy.]"
            )
            merged_description = f"{conflict_note} " + " | ".join(unique_descriptions)
            print(
                f"    [CONFLICT RESOLVED] Pair ({drug1}, {drug2}): "
                f"Severities {unique_severities} -> '{chosen_severity}'"
            )

        merged_source = "; ".join(unique_sources)

        resolved_rows.append({
            "canonical_a": drug1,
            "canonical_b": drug2,
            "severity": chosen_severity,
            "description": merged_description,
            "source": merged_source,
        })

    resolved_df = pd.DataFrame(resolved_rows)
    print(f"  - Canonicalized undirected pairs and merged duplicates: "
          f"{len(df)} rows reduced to {len(resolved_df)} unique interaction edge(s).")
    return resolved_df


def extract_unique_drugs_and_assign_ids(interactions_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Extracts all unique drug names from canonical_a and canonical_b.
    Sorts alphabetically for deterministic and reproducible ID assignment.
    Assigns each drug a unique 1-based integer drug_id.
    
    Returns:
        drugs_df: DataFrame with columns [drug_id, name]
        name_to_id: dictionary mapping normalized drug name to drug_id
    """
    unique_drugs = sorted(
        set(interactions_df["canonical_a"].tolist() + interactions_df["canonical_b"].tolist())
    )

    drug_records = []
    name_to_id = {}
    for idx, drug_name in enumerate(unique_drugs, start=1):
        drug_records.append({
            "drug_id": idx,
            "name": drug_name,
        })
        name_to_id[drug_name] = idx

    drugs_df = pd.DataFrame(drug_records)
    print(f"  - Extracted {len(drugs_df)} unique drugs; assigned integer IDs (1 to {len(drugs_df)}).")
    return drugs_df, name_to_id


def build_final_interactions(resolved_df: pd.DataFrame, name_to_id: Dict[str, int]) -> pd.DataFrame:
    """
    Replaces drug names with drug_a_id and drug_b_id.
    Assigns a unique 1-based integer interaction_id.
    Retains severity, description, and source.
    """
    interactions = []
    for idx, row in resolved_df.iterrows():
        interactions.append({
            "interaction_id": idx + 1,
            "drug_a_id": name_to_id[row["canonical_a"]],
            "drug_b_id": name_to_id[row["canonical_b"]],
            "severity": row["severity"],
            "description": row["description"],
            "source": row["source"],
        })

    final_df = pd.DataFrame(interactions)
    print(f"  - Built interactions table with {len(final_df)} edges and assigned interaction IDs.")
    return final_df


def save_processed_datasets(drugs_df: pd.DataFrame, interactions_df: pd.DataFrame,
                           drugs_path: Path, interactions_path: Path) -> None:
    """
    Ensures the target directory exists and saves drugs.csv and interactions.csv.
    """
    # Create data/processed directory if it does not exist
    drugs_path.parent.mkdir(parents=True, exist_ok=True)

    drugs_df.to_csv(drugs_path, index=False)
    interactions_df.to_csv(interactions_path, index=False)

    print(f"  [SAVED] {drugs_path} ({len(drugs_df)} records)")
    print(f"  [SAVED] {interactions_path} ({len(interactions_df)} records)")


def main() -> None:
    """
    Main orchestration function for the cleaning pipeline.
    """
    raw_path, drugs_path, interactions_path = get_project_paths()

    print("=" * 70)
    print("STEP 2: RUNNING DATA CLEANING PIPELINE")
    print("=" * 70)
    print(f"Input file  : {raw_path}")
    print(f"Outputs     : {drugs_path}\n              {interactions_path}")
    print("-" * 70)

    # 1. Load and validate columns
    raw_df = load_and_validate_columns(raw_path)
    print(f"Loaded {len(raw_df)} initial raw records.")

    # 2. Remove rows missing drug names
    df_valid_drugs = remove_missing_drugs(raw_df)

    # 3. Normalize strings and severities
    df_normalized = normalize_strings_and_severities(df_valid_drugs)

    # 4. Remove self-interactions
    df_no_self = remove_self_interactions(df_normalized)

    # 5. Resolve duplicate and undirected interactions (with conflict handling)
    df_resolved = resolve_duplicate_interactions(df_no_self)

    # 6. Extract unique drugs and assign IDs
    drugs_df, name_to_id = extract_unique_drugs_and_assign_ids(df_resolved)

    # 7. Build interactions table with foreign keys (drug_a_id, drug_b_id)
    interactions_df = build_final_interactions(df_resolved, name_to_id)

    # 8. Save outputs to data/processed/
    print("-" * 70)
    print("SAVING PROCESSED CSV FILES")
    print("-" * 70)
    save_processed_datasets(drugs_df, interactions_df, drugs_path, interactions_path)

    print("=" * 70)
    print("CLEANING COMPLETE")
    print(f"Summary:")
    print(f"  - Initial raw rows    : {len(raw_df)}")
    print(f"  - Unique drugs (nodes): {len(drugs_df)}")
    print(f"  - Unique interactions (edges): {len(interactions_df)}")
    print("Next step: Run 'python scripts/validate_data.py' to verify data integrity.")
    print("=" * 70)


if __name__ == "__main__":
    main()
