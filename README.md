# Drug Interaction Graph Explorer

A modular academic project designed to model, analyze, and explore biomedical drug-drug interaction (DDI) networks using graph structures.

---

## 1. Project Vision (What the Application Will Eventually Do)

In pharmacology and healthcare, polypharmacy (prescribing multiple medications concurrently) can trigger unanticipated drug-drug interactions (DDIs). These interactions can reduce therapeutic efficacy or cause severe adverse clinical outcomes.

The **Drug Interaction Graph Explorer** aims to model these biomedical relationships as an undirected, weighted graph:

- **Nodes (Vertices)**: Represent individual medications/drugs (e.g., `Drug A`, `Drug B`).
- **Edges (Links)**: Represent documented interactions between pairs of drugs.
- **Edge Attributes / Weights**: Represent interaction severity levels (`minor`, `moderate`, `major`, or `unknown`).

In future development phases, this graph foundation will power interactive network visualizations (using Cytoscape.js), shortest path traversals, risk cluster analysis, and query APIs built with FastAPI and PostgreSQL.

---

## 2. What Phase 1 Does

**Phase 1** establishes the clean data engineering foundation. It focuses **strictly on data collection, inspection, cleaning, normalization, conflict resolution, ID assignment, and integrity validation**.

No frontend, backend API, database, machine learning, or complex graph traversal algorithms are built yet. The goal is to produce reliable, normalized, relational CSV datasets that can serve as the clean ground truth for all subsequent phases.

### Graph Data Mapping in Phase 1:

| Domain Entity | Graph Concept | Phase 1 File | Schema |
| :--- | :--- | :--- | :--- |
| **Drug** | Graph Node | `data/processed/drugs.csv` | `drug_id,name` |
| **Interaction** | Graph Edge | `data/processed/interactions.csv` | `interaction_id,drug_a_id,drug_b_id,severity,description,source` |
| **Severity** | Edge Weight / Attribute | `interactions.csv` (`severity` column) | Categorical: `minor`, `moderate`, `major`, `unknown` |

---

## 3. Current Folder Structure

```text
drug-interaction-explorer/
├── data/
│   ├── raw/
│   │   └── interactions_raw.csv        # Synthetic raw dataset with deliberate anomalies
│   └── processed/
│       ├── drugs.csv                   # Extracted unique drug nodes with integer IDs
│       └── interactions.csv            # Cleaned undirected interaction edges with foreign keys
├── scripts/
│   ├── inspect_data.py                 # Step 2: Read-only inspection of the raw dataset
│   ├── clean_data.py                   # Step 3: Cleaning, normalization, and ID generation
│   └── validate_data.py                # Step 4: Integrity and relational constraint checks
├── .gitignore                          # Standard Python ignores (venv, cache, IDE)
├── README.md                           # Project documentation and guide
└── requirements.txt                    # Project dependencies (pandas)
```

---

## 4. Environment Setup & Dependencies

This project uses Python 3 and `pandas`. Follow these steps to set up your environment:

### Step 4.1: Create a Python Virtual Environment

Open your terminal in the project root directory:

**Windows (PowerShell or Command Prompt):**
```bash
python -m venv venv
```

**macOS / Linux:**
```bash
python3 -m venv venv
```

### Step 4.2: Activate the Virtual Environment

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```
*(If PowerShell restricts script execution, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` first, or use `.\venv\Scripts\activate.bat` in Command Prompt).*

**macOS / Linux:**
```bash
source venv/bin/activate
```

### Step 4.3: Install Dependencies

With your virtual environment active, run:
```bash
pip install -r requirements.txt
```

---

## 5. How to Run the Pipeline

Run each script from the project root directory in sequence:

### Step 5.1: Inspect the Raw Data
Examines raw records, dimensions, missing values, severity distributions, and potential anomalies without modifying any file:
```bash
python scripts/inspect_data.py
```

### Step 5.2: Clean and Transform the Data
Processes raw records, eliminates invalid entries, normalizes casing/whitespace, canonicalizes undirected pairs, resolves duplicate/conflicting interactions, generates integer IDs, and outputs clean CSVs:
```bash
python scripts/clean_data.py
```

### Step 5.3: Validate the Processed Data
Verifies relational integrity, uniqueness constraints, absence of self-interactions, absence of duplicate pairs, and schema compliance:
```bash
python scripts/validate_data.py
```

---

## 6. The Complete Data Pipeline

The data flows through the following 8-stage pipeline:

```text
+------------------------------+
| 1. Raw CSV                   |  data/raw/interactions_raw.csv
+------------------------------+
               |
               v
+------------------------------+
| 2. Inspection                |  scripts/inspect_data.py
|    - Read-only diagnostics   |  (Identifies nulls, duplicates, casing issues)
+------------------------------+
               |
               v
+------------------------------+
| 3. Cleaning & Validation     |  scripts/clean_data.py
|    - Drop missing drug names |
|    - Drop self-interactions  |
+------------------------------+
               |
               v
+------------------------------+
| 4. Normalization             |
|    - Lowercase & strip names |
|    - Unknown for blank sev   |
+------------------------------+
               |
               v
+------------------------------+
| 5. Duplicate & Conflict      |  Canonicalize undirected pairs (min, max)
|    Resolution                |  Conservative clinical safety policy for conflicts
+------------------------------+
               |
               v
+------------------------------+
| 6. Unique Drug Extraction    |  Deterministic alphabetical sorting
|    & ID Generation           |  Assign 1-based integer drug_id & interaction_id
+------------------------------+
               |
               v
+------------------------------+
| 7. Export Processed CSVs     |  data/processed/drugs.csv
|                              |  data/processed/interactions.csv
+------------------------------+
               |
               v
+------------------------------+
| 8. Validation                |  scripts/validate_data.py
|    - 10 Automated checks     |  (Referential integrity, uniqueness, schemas)
+------------------------------+
```

---

## 7. Duplicate & Conflict Handling Policy

In an undirected graph, an edge between Drug A and Drug B is identical to an edge between Drug B and Drug A (`A-B == B-A`).

### Canonical Pair Representation
To eliminate directional redundancy, the cleaning pipeline sorts every drug pair alphabetically:
$$\text{canonical\_a} = \min(\text{drug\_a}, \text{drug\_b})$$
$$\text{canonical\_b} = \max(\text{drug\_a}, \text{drug\_b})$$

### Duplicate Resolution Rules
When multiple records exist for the same canonical pair:

1. **Identical Severity**:
   - The agreed-upon severity is retained.
   - Unique sources are combined (e.g., `Demo Trial Alpha; Demo Trial Beta`).
   - Unique descriptions are preserved.

2. **Conflicting Severity (Non-Silent Resolution)**:
   - When different sources report different severity levels for the same drug pair (e.g., one source reports `minor` while another reports `moderate`):
     - **Conservative Clinical Safety Principle**: The pipeline selects the **highest reported severity** using the ranking:
       $$\text{unknown (0)} < \text{minor (1)} < \text{moderate (2)} < \text{major (3)}$$
     - **Audit Trail in Description**: The conflict is explicitly logged and prepended to the description:
       `[CONFLICT RESOLVED: Severities reported were ['minor', 'moderate']. Selected 'moderate' following conservative clinical safety policy.]`
     - **Provenance Preservation**: All unique sources are combined and preserved, ensuring full traceability.
     - Conflicting records are **never silently discarded**.

---

## 8. Synthetic Dataset Notice (NOT Medical Advice)

> [!WARNING]
> **ACADEMIC DEMONSTRATION ONLY — NOT MEDICAL ADVICE**
> 
> The initial dataset (`data/raw/interactions_raw.csv`) uses synthetic drug names (`DemoDrugA`, `DemoDrugB`, etc.) and mock interactions. It is generated strictly for computer science education, software engineering coursework, and data pipeline demonstration.
> 
> - **Do NOT** use this dataset or code for real clinical, pharmaceutical, or diagnostic decisions.
> - The authors and contributors do not make any clinical claims or accept any medical liability.

---

## 9. Transitioning to Real-World Datasets

When transitioning to a real-world biomedical dataset in future phases, the synthetic CSV in `data/raw/` can be replaced with an open biomedical database export.

### Potential Real-World Sources
- **DrugBank Open Data / Academic Release**: Comprehensive drug interaction descriptions and severity tiers.
- **TWOSIDES / BioSNAP**: Polypharmacy side-effects and adverse drug-drug interaction network datasets.
- **DrugCentral**: Curated pharmaceutical active ingredient database maintained by UNM.
- **FDA National Drug Code (NDC) & Adverse Event Reporting System (FAERS)**.

### Real-World Data Provenance Checklist
When integrating a real dataset, document the following in a `data/raw/DATASET_METADATA.md` file:
1. **Source Name & Provider**: Name of the database/institution (e.g., Stanford BioSNAP, DrugCentral).
2. **Download URL**: Permanent URL or DOI where the dataset was retrieved.
3. **Retrieval Date**: Exact UTC timestamp when the data was downloaded.
4. **License & Terms of Use**: Permitted usage terms (e.g., CC-BY 4.0, academic research license).
5. **Preprocessing & Mapping Log**: Any script used to map raw source column names (e.g., `stitch_id_1`, `stitch_id_2`, `pubchem_cid`) to our canonical schema (`drug_a`, `drug_b`, `severity`, `description`, `source`).

---

## 10. Phase 1 Verification Status

All 10 validation checks have been automated and verified:
- [x] All drug IDs are unique (11 unique nodes)
- [x] All interaction IDs are unique (13 unique edges)
- [x] No missing drug IDs or reference fields
- [x] Referential integrity: All `drug_a_id` references exist in `drugs.csv`
- [x] Referential integrity: All `drug_b_id` references exist in `drugs.csv`
- [x] No self-interactions (`drug_a != drug_b`)
- [x] No duplicate undirected interaction pairs (`A-B` vs `B-A`)
- [x] Allowed severity values only (`minor`, `moderate`, `major`, `unknown`)
- [x] Provenance (`source`) preserved for all records
- [x] Interaction descriptions preserved with conflict audit notes
