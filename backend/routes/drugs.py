"""
backend/routes/drugs.py
-----------------------
API endpoints for querying drug entities and their direct interactions.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import crud, schemas

router = APIRouter(prefix="/drugs", tags=["Drugs"])


@router.get(
    "",
    response_model=List[schemas.DrugResponse],
    summary="List drugs with pagination",
    description="Retrieves a paginated list of drugs ordered by ID. Does not return the full dataset automatically.",
)
def list_drugs(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of drugs to return (1-100)"),
    offset: int = Query(0, ge=0, description="Number of drugs to skip for pagination"),
    db: Session = Depends(get_db),
):
    return crud.get_drugs(db, skip=offset, limit=limit)


@router.get(
    "/search",
    response_model=List[schemas.DrugResponse],
    summary="Search drugs by name",
    description="Performs a case-insensitive search for drugs whose name contains the search string.",
)
def search_drugs(
    q: str = Query(..., min_length=1, description="Search term (e.g., 'asp', 'demo')"),
    limit: int = Query(20, ge=1, le=50, description="Maximum matching results to return"),
    db: Session = Depends(get_db),
):
    return crud.search_drugs(db, query=q, limit=limit)


@router.get(
    "/{drug_id}",
    response_model=schemas.DrugResponse,
    summary="Retrieve a single drug by ID",
    description="Returns detailed information for a single drug node. Returns 404 if not found.",
)
def get_drug(
    drug_id: int,
    db: Session = Depends(get_db),
):
    drug = crud.get_drug(db, drug_id=drug_id)
    if not drug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drug with ID {drug_id} was not found in the database.",
        )
    return drug


@router.get(
    "/{drug_id}/interactions",
    response_model=schemas.DrugWithInteractionsResponse,
    summary="Retrieve all direct interactions for a drug",
    description=(
        "Returns all direct interactions for the specified drug. Finds interactions "
        "where the drug appears as either drug_a or drug_b in the undirected graph. "
        "Reports only documented interactions in the current dataset (NOT clinical advice)."
    ),
)
def get_drug_interactions(
    drug_id: int,
    db: Session = Depends(get_db),
):
    drug = crud.get_drug(db, drug_id=drug_id)
    if not drug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drug with ID {drug_id} was not found in the database.",
        )

    interaction_pairs = crud.get_drug_interactions(db, drug_id=drug_id)

    formatted_interactions: List[schemas.DrugDirectInteraction] = []
    for inter, other_drug in interaction_pairs:
        formatted_interactions.append(
            schemas.DrugDirectInteraction(
                interaction_id=inter.interaction_id,
                other_drug=schemas.DrugSummary(
                    drug_id=other_drug.drug_id,
                    name=other_drug.name,
                ),
                severity=inter.severity,
                description=inter.description,
                source=inter.source,
            )
        )

    return schemas.DrugWithInteractionsResponse(
        drug=schemas.DrugSummary(drug_id=drug.drug_id, name=drug.name),
        interaction_count=len(formatted_interactions),
        interactions=formatted_interactions,
    )
