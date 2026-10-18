# Drug Interaction Graph Explorer

A modular academic project designed to model, analyze, and explore biomedical drug-drug interaction (DDI) networks using graph structures.

---

## 1. Project Vision (What the Application Will Eventually Do)

In pharmacology and healthcare, polypharmacy (prescribing multiple medications concurrently) can trigger unanticipated drug-drug interactions (DDIs). These interactions can reduce therapeutic efficacy or cause severe adverse clinical outcomes.

The **Drug Interaction Graph Explorer** aims to model these biomedical relationships as an undirected, weighted graph:

- **Nodes (Vertices)**: Represent individual medications/drugs (e.g., `Drug A`, `Drug B`).
- **Edges (Links)**: Represent documented interactions between pairs of drugs.
- **Edge Attributes / Weights**: Represent interaction severity levels (`minor`, `moderate`, `major`, or `unknown`).

In future development phases, this graph foundation will power interactive network visualizations (using Cytoscape.js), shortest path traversals, risk cluster analysis, and frontend dashboards built with React.

---

## 2. What Phase 1 Does

**Phase 1** establishes the clean data engineering foundation. It focuses **strictly on data collection, inspection, cleaning, normalization, conflict resolution, ID assignment, and integrity validation**.

No frontend, machine learning, or complex graph traversal algorithms are built yet. The goal is to produce reliable, normalized, relational CSV datasets that serve as the clean ground truth for all subsequent phases.

### Graph Data Mapping in Phase 1:

| Domain Entity | Graph Concept | Phase 1 File | Schema |
| :--- | :--- | :--- | :--- |
| **Drug** | Graph Node | `data/processed/drugs.csv` | `drug_id,name` |
| **Interaction** | Graph Edge | `data/processed/interactions.csv` | `interaction_id,drug_a_id,drug_b_id,severity,description,source` |
| **Severity** | Edge Weight / Attribute | `interactions.csv` (`severity` column) | Categorical: `minor`, `moderate`, `major`, `unknown` |

---

## 3. Project Folder Structure

```text
drug-interaction-explorer/
├── data/
│   ├── raw/
│   │   └── interactions_raw.csv        # Synthetic raw dataset with deliberate anomalies
│   └── processed/
│       ├── drugs.csv                   # Extracted unique drug nodes with integer IDs
│       └── interactions.csv            # Cleaned undirected interaction edges with foreign keys
├── scripts/
│   ├── inspect_data.py                 # Phase 1: Read-only inspection of the raw dataset
│   ├── clean_data.py                   # Phase 1: Cleaning, normalization, and ID generation
│   ├── validate_data.py                # Phase 1: Integrity and relational constraint checks
│   └── import_to_db.py                 # Phase 2: PostgreSQL ingestion script (idempotent / reset)
├── backend/
│   ├── __init__.py                     # Backend package initialization
│   ├── main.py                         # FastAPI app entrypoint, routes, and CORS setup
│   ├── database.py                     # PostgreSQL connection, engine, and get_db dependency
│   ├── models.py                       # SQLAlchemy ORM models (Drug, Interaction)
│   ├── schemas.py                      # Pydantic request & response schemas
│   ├── crud.py                         # Reusable database access & query service layer
│   └── routes/
│       ├── __init__.py
│       ├── drugs.py                    # Endpoints for listing, search, and direct interactions
│       ├── interactions.py             # Endpoints for pairwise & multi-drug checks
│       └── stats.py                    # Endpoint for database & graph summary metrics
├── tests/
│   ├── __init__.py
│   └── test_api.py                     # Automated pytest suite (uses isolated SQLite memory DB)
├── .env.example                        # Template for database configuration
├── .gitignore                          # Standard Python ignores (venv, cache, IDE, .env)
├── README.md                           # Comprehensive documentation & student guide
└── requirements.txt                    # Project dependencies (FastAPI, SQLAlchemy, psycopg, etc.)
```

---

## 4. Phase 1 — Data Pipeline & Execution

### Environment Setup

Open your terminal in the project root directory:

**Create virtual environment:**
```bash
# Windows
python -m venv venv

# macOS / Linux
python3 -m venv venv
```

**Activate virtual environment:**
```powershell
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.\venv\Scripts\activate.bat

# macOS / Linux
source venv/bin/activate
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

### Running Phase 1 Scripts:

```bash
# Step 1: Inspect raw dataset without modifications
python scripts/inspect_data.py

# Step 2: Clean, normalize, resolve duplicate/conflicts, and generate processed CSVs
python scripts/clean_data.py

# Step 3: Run 10 automated data integrity checks
python scripts/validate_data.py
```

---

## 5. Phase 2 — PostgreSQL + FastAPI Backend API

### Architecture

```text
Processed CSV files (drugs.csv, interactions.csv)
                      │
                      ▼
            PostgreSQL Database
          (drugs & interactions tables)
                      │
                      ▼
             SQLAlchemy ORM Layer
          (models.py, crud.py, database.py)
                      │
                      ▼
               FastAPI Backend
          (main.py, routers, schemas.py)
                      │
                      ▼
             REST API Endpoints
     (/drugs, /interactions/check, /stats)
                      │
                      ▼
                JSON Responses
```

---

### Step-by-Step Setup Guide

#### Step 1: Install PostgreSQL
- **Windows**: Download the interactive installer from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/). Remember the master password assigned to the `postgres` user during installation (default port is `5432`).
- **macOS** (Homebrew):
  ```bash
  brew install postgresql@16
  brew services start postgresql@16
  ```
- **Linux** (Ubuntu/Debian):
  ```bash
  sudo apt update
  sudo apt install postgresql postgresql-contrib
  sudo systemctl start postgresql
  ```

#### Step 2: Create the `drug_graph` Database
Open `psql` or pgAdmin:

**In terminal via psql:**
```bash
# Connect as postgres user
psql -U postgres
```

**Inside the psql shell:**
```sql
CREATE DATABASE drug_graph;
\q
```

#### Step 3: Configure Environment Variables (`.env`)
Copy `.env.example` to create your local `.env` file:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Open `.env` in your editor and update the username and password with your PostgreSQL credentials:
```env
DATABASE_URL=postgresql+psycopg://postgres:your_password_here@localhost:5432/drug_graph
```
*(Note: `.env` is already added to `.gitignore` so your personal credentials will never be committed to Git).*

#### Step 4: Import Processed Data to PostgreSQL
Run the import script to automatically create database tables and ingest data from Phase 1:

```bash
python scripts/import_to_db.py
```

*Tip*: If you ever need to completely wipe and reload the database tables fresh:
```bash
python scripts/import_to_db.py --reset
```

#### Step 5: Start the FastAPI Server
Launch the development server with Uvicorn:

```bash
uvicorn backend.main:app --reload
```

The terminal will confirm:
```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

#### Step 6: Interactive Swagger Documentation
Open your browser and navigate to:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

You can click any endpoint, choose **Try it out**, fill in parameters, and click **Execute** to inspect live responses.

---

### API Endpoints Reference

| Method | Endpoint | Description | Example Query |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | API welcome message & root links | `/` |
| `GET` | `/health` | Health status probe (`{"status": "ok"}`) | `/health` |
| `GET` | `/drugs` | Paginated list of drugs | `/drugs?limit=10&offset=0` |
| `GET` | `/drugs/search` | Case-insensitive drug name search | `/drugs/search?q=demo` |
| `GET` | `/drugs/{drug_id}` | Retrieve single drug details | `/drugs/1` |
| `GET` | `/drugs/{drug_id}/interactions` | Retrieve all direct interactions for a drug | `/drugs/1/interactions` |
| `GET` | `/interactions/check` | Check direct interaction between 2 drugs (symmetric) | `/interactions/check?drug1_id=1&drug2_id=2` |
| `POST` | `/interactions/check-multiple` | Check all mutual pairwise combinations in a drug list | `{"drug_ids": [1, 2, 5, 9]}` |
| `GET` | `/stats` | Graph summary metrics & severity distribution | `/stats` |

---

## 6. Automated Testing

The backend includes an automated test suite verifying all required behaviors.

### Isolated Testing Strategy
- Tests execute against an isolated in-memory **SQLite database** using SQLAlchemy's `StaticPool`.
- FastAPI's `get_db` dependency is overridden in [`tests/test_api.py`](file:///c:/Users/kabir/Desktop/princy/Aurora/tests/test_api.py).
- **Zero Risk**: Tests run fast in any environment without needing PostgreSQL running, and will **NEVER** alter or wipe your local/production database.

### Running Tests:
```bash
python -m pytest -v
```

All 18 tests cover:
- Root & health check endpoints
- Drug listing & pagination
- Drug retrieval & 404 error responses
- Case-insensitive search
- Direct interaction retrieval (handling edges whether drug is `drug_a` or `drug_b`)
- Symmetric two-drug interaction checks ($A \leftrightarrow B \equiv B \leftrightarrow A$)
- Multi-drug pairwise combination checking in a single SQL query
- Multi-drug validation (duplicate removal, minimum 2 drugs, nonexistent IDs)
- Statistical aggregation

---

## 7. Duplicate & Conflict Handling Policy (Phase 1 Ground Truth)

In an undirected graph, an edge between Drug A and Drug B is identical to an edge between Drug B and Drug A (`A-B == B-A`).

### Canonical Pair Representation
To eliminate directional redundancy, the cleaning pipeline sorts every drug pair alphabetically:
$$\text{canonical\_a} = \min(\text{drug\_a}, \text{drug\_b}), \quad \text{canonical\_b} = \max(\text{drug\_a}, \text{drug\_b})$$

### Duplicate Resolution Rules
When multiple records exist for the same canonical pair:

1. **Identical Severity**:
   - The agreed-upon severity is retained.
   - Unique sources are combined (e.g., `Demo Trial Alpha; Demo Trial Beta`).
   - Unique descriptions are preserved.

2. **Conflicting Severity (Non-Silent Resolution)**:
   - When different sources report different severity levels for the same drug pair:
     - **Conservative Clinical Safety Principle**: The pipeline selects the **highest reported severity** using the ranking:
       $$\text{unknown (0)} < \text{minor (1)} < \text{moderate (2)} < \text{major (3)}$$
     - **Audit Trail in Description**: The conflict is explicitly logged and prepended to the description:
       `[CONFLICT RESOLVED: Severities reported were ['minor', 'moderate']. Selected 'moderate' following conservative clinical safety policy.]`
     - **Provenance Preservation**: All unique sources are combined and preserved. Conflicting records are **never silently discarded**.

---

## 8. Academic & Educational Notice (NOT Medical Advice)

> [!WARNING]
> **ACADEMIC DEMONSTRATION ONLY — NOT CLINICAL ADVICE**
> 
> The Drug Interaction Graph Explorer is an educational and research software project.
> - The initial dataset uses synthetic demo drugs (`DemoDrugA` through `DemoDrugK`).
> - The backend API reports strictly documented interactions found in the current dataset.
> - The application **NEVER** claims a medication is safe to take, that a combination is safe, that a medication should be stopped, or that an indirect graph traversal represents a clinical interaction.
> - **Do NOT** use this software for actual medical diagnosis, prescription advice, or clinical guidance.

---

## 9. Transitioning to Real-World Datasets

When transitioning to real-world biomedical data in future phases:
1. Replace `data/raw/interactions_raw.csv` with an export from DrugBank, TWOSIDES/BioSNAP, or DrugCentral.
2. Maintain a `DATASET_METADATA.md` recording Provider, Download URL, Download Date, and License.
3. Re-run `python scripts/clean_data.py`, `python scripts/validate_data.py`, and `python scripts/import_to_db.py --reset`.
