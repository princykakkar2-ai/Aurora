"""
tests/test_api.py
-----------------
Automated test suite for Phase 2 FastAPI backend endpoints and business logic.

Testing Strategy:
  - Uses an isolated, in-memory SQLite database (StaticPool) via SQLAlchemy.
  - Overrides FastAPI's get_db dependency so tests run in complete isolation.
  - Never touches or modifies the production PostgreSQL database.
  - Verifies:
      1. Root and health check endpoints.
      2. Drug listing, pagination, single retrieval, and 404 behavior.
      3. Case-insensitive drug name search.
      4. Direct interaction retrieval (finding interactions where drug is drug_a OR drug_b).
      5. Symmetric two-drug interaction checking (order independence: 1,2 vs 2,1).
      6. Multi-drug pairwise generation and single-query matching.
      7. Input validation (duplicate IDs, < 2 drugs, nonexistent IDs).
      8. Statistical aggregation (/stats).
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import app
from backend.database import Base, get_db
from backend.models import Drug, Interaction


# 1. Create an isolated in-memory SQLite engine for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module")
def setup_test_db():
    """
    Creates tables and seeds initial test data once for the test module.
    Cleans up after all tests complete.
    """
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()

    # Seed 4 test drugs
    drugs = [
        Drug(drug_id=1, name="aspirin"),
        Drug(drug_id=2, name="warfarin"),
        Drug(drug_id=3, name="ibuprofen"),
        Drug(drug_id=4, name="acetaminophen"),
    ]
    session.add_all(drugs)
    session.commit()

    # Seed test interactions (canonical order: drug_a_id < drug_b_id)
    # 1 <-> 2 (aspirin <-> warfarin, major)
    # 1 <-> 3 (aspirin <-> ibuprofen, moderate)
    # 2 <-> 3 (warfarin <-> ibuprofen, major)
    # Note: acetaminophen (4) has NO interactions (isolated node)
    interactions = [
        Interaction(
            interaction_id=1,
            drug_a_id=1,
            drug_b_id=2,
            severity="major",
            description="Increased bleeding risk.",
            source="Test Registry",
        ),
        Interaction(
            interaction_id=2,
            drug_a_id=1,
            drug_b_id=3,
            severity="moderate",
            description="Increased gastrointestinal ulceration risk.",
            source="Test Registry",
        ),
        Interaction(
            interaction_id=3,
            drug_a_id=2,
            drug_b_id=3,
            severity="major",
            description="Additive anticoagulant risk.",
            source="Test Registry",
        ),
    ]
    session.add_all(interactions)
    session.commit()
    session.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(setup_test_db):
    """
    FastAPI TestClient fixture that overrides the get_db dependency.
    """
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# =====================================================================
# GENERAL ENDPOINT TESTS
# =====================================================================

def test_root_endpoint(client):
    """Verify GET / returns welcome information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "Drug Interaction Graph Explorer API"


def test_health_check(client):
    """Verify GET /health returns status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# =====================================================================
# DRUG ENDPOINT TESTS
# =====================================================================

def test_list_drugs_pagination(client):
    """Verify GET /drugs supports pagination."""
    response = client.get("/drugs?limit=2&offset=0")
    assert response.status_code == 200
    drugs = response.json()
    assert len(drugs) == 2
    assert drugs[0]["drug_id"] == 1
    assert drugs[1]["drug_id"] == 2

    # Test offset
    response_offset = client.get("/drugs?limit=2&offset=2")
    assert response_offset.status_code == 200
    drugs_offset = response_offset.json()
    assert len(drugs_offset) == 2
    assert drugs_offset[0]["drug_id"] == 3


def test_get_drug_by_id_success(client):
    """Verify GET /drugs/{id} returns the correct drug."""
    response = client.get("/drugs/1")
    assert response.status_code == 200
    data = response.json()
    assert data["drug_id"] == 1
    assert data["name"] == "aspirin"


def test_get_drug_by_id_not_found(client):
    """Verify GET /drugs/{id} returns 404 for nonexistent drug."""
    response = client.get("/drugs/9999")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "9999" in data["detail"]


def test_search_drugs_case_insensitive(client):
    """Verify GET /drugs/search finds matches case-insensitively."""
    # Search 'ASP' should match 'aspirin'
    response = client.get("/drugs/search?q=ASP")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "aspirin"

    # Search 'pro' should match 'ibuprofen'
    response2 = client.get("/drugs/search?q=pro")
    assert response2.status_code == 200
    data2 = response2.json()
    assert any(d["name"] == "ibuprofen" for d in data2)

    # Search nonexistent term
    response3 = client.get("/drugs/search?q=xyznonexistent")
    assert response3.status_code == 200
    assert response3.json() == []


# =====================================================================
# DIRECT INTERACTION ENDPOINT TESTS
# =====================================================================

def test_get_drug_direct_interactions(client):
    """
    Verify GET /drugs/{id}/interactions finds all edges where the drug is
    either drug_a or drug_b.
    Drug 1 (aspirin) has interactions with Drug 2 (as drug_a) and Drug 3 (as drug_a).
    Drug 2 (warfarin) has interactions with Drug 1 (as drug_b) and Drug 3 (as drug_a).
    """
    response = client.get("/drugs/2/interactions")
    assert response.status_code == 200
    data = response.json()
    assert data["drug"]["drug_id"] == 2
    assert data["drug"]["name"] == "warfarin"
    assert data["interaction_count"] == 2

    # Check other drugs returned
    other_drug_ids = {item["other_drug"]["drug_id"] for item in data["interactions"]}
    assert other_drug_ids == {1, 3}


def test_get_drug_interactions_isolated_node(client):
    """Verify a drug with no interactions returns an empty interaction list."""
    response = client.get("/drugs/4/interactions")
    assert response.status_code == 200
    data = response.json()
    assert data["drug"]["drug_id"] == 4
    assert data["interaction_count"] == 0
    assert data["interactions"] == []


# =====================================================================
# TWO-DRUG INTERACTION CHECK TESTS (SYMMETRY)
# =====================================================================

def test_two_drug_interaction_check_symmetry(client):
    """
    Verify that check(1, 2) and check(2, 1) return the exact same interaction.
    """
    res1 = client.get("/interactions/check?drug1_id=1&drug2_id=2")
    assert res1.status_code == 200
    data1 = res1.json()

    res2 = client.get("/interactions/check?drug1_id=2&drug2_id=1")
    assert res2.status_code == 200
    data2 = res2.json()

    assert data1["interaction_found"] is True
    assert data2["interaction_found"] is True
    assert data1["interaction"]["interaction_id"] == data2["interaction"]["interaction_id"]
    assert data1["interaction"]["severity"] == "major"


def test_two_drug_interaction_not_found(client):
    """Verify check for two drugs without interaction returns interaction_found=false."""
    response = client.get("/interactions/check?drug1_id=1&drug2_id=4")
    assert response.status_code == 200
    data = response.json()
    assert data["interaction_found"] is False
    assert data["interaction"] is None


def test_two_drug_interaction_same_id_400(client):
    """Verify checking a drug against itself returns 400 Bad Request."""
    response = client.get("/interactions/check?drug1_id=1&drug2_id=1")
    assert response.status_code == 400


def test_two_drug_interaction_nonexistent_404(client):
    """Verify checking with a nonexistent drug ID returns 404."""
    response = client.get("/interactions/check?drug1_id=1&drug2_id=9999")
    assert response.status_code == 404


# =====================================================================
# MULTI-DRUG CHECK TESTS
# =====================================================================

def test_multi_drug_check_success(client):
    """
    Verify checking [1, 2, 3] generates 3 pairs (1-2, 1-3, 2-3) and finds all 3 interactions.
    """
    response = client.post("/interactions/check-multiple", json={"drug_ids": [1, 2, 3]})
    assert response.status_code == 200
    data = response.json()
    assert data["selected_drug_count"] == 3
    assert data["pairs_checked"] == 3
    assert data["interactions_found"] == 3


def test_multi_drug_check_with_isolated_drug(client):
    """
    Checking [1, 2, 4]: pairs are 1-2, 1-4, 2-4.
    Only 1-2 interacts; 1-4 and 2-4 do not.
    """
    response = client.post("/interactions/check-multiple", json={"drug_ids": [1, 2, 4]})
    assert response.status_code == 200
    data = response.json()
    assert data["selected_drug_count"] == 3
    assert data["pairs_checked"] == 3
    assert data["interactions_found"] == 1


def test_multi_drug_check_handles_duplicate_ids(client):
    """Verify duplicate IDs in the request list are deduplicated cleanly."""
    response = client.post("/interactions/check-multiple", json={"drug_ids": [1, 2, 1, 2]})
    assert response.status_code == 200
    data = response.json()
    assert data["selected_drug_count"] == 2
    assert data["pairs_checked"] == 1
    assert data["interactions_found"] == 1


def test_multi_drug_check_insufficient_drugs_400(client):
    """Verify requesting fewer than 2 unique drugs returns 400/422."""
    response = client.post("/interactions/check-multiple", json={"drug_ids": [1]})
    assert response.status_code in (400, 422)

    # Identical IDs resulting in 1 unique drug
    response_dup = client.post("/interactions/check-multiple", json={"drug_ids": [1, 1]})
    assert response_dup.status_code == 400


def test_multi_drug_check_nonexistent_ids_404(client):
    """Verify requesting nonexistent drug IDs returns 404."""
    response = client.post("/interactions/check-multiple", json={"drug_ids": [1, 9999]})
    assert response.status_code == 404
    assert "9999" in response.json()["detail"]


# =====================================================================
# DATABASE STATISTICS TEST
# =====================================================================

def test_database_stats(client):
    """Verify GET /stats returns counts of drugs, interactions, and severities."""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_drugs"] == 4
    assert data["total_interactions"] == 3
    assert "major" in data["severity_counts"]
    assert "moderate" in data["severity_counts"]
    assert data["severity_counts"]["major"] == 2
    assert data["severity_counts"]["moderate"] == 1
