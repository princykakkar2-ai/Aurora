"""
backend/routes/stats.py
-----------------------
API endpoint for retrieving database and graph summary statistics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import crud, schemas

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get(
    "",
    response_model=schemas.StatsResponse,
    summary="Retrieve database and graph statistics",
    description=(
        "Returns summary metrics including total drug nodes, total interaction edges, "
        "and distribution counts by severity. Only reports categories present in the stored data."
    ),
)
def get_database_stats(
    db: Session = Depends(get_db),
):
    stats = crud.get_statistics(db)
    return schemas.StatsResponse(
        total_drugs=stats["total_drugs"],
        total_interactions=stats["total_interactions"],
        severity_counts=stats["severity_counts"],
    )
