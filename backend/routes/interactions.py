"""
backend/routes/interactions.py
------------------------------
API endpoints for verifying pairwise and multi-drug direct interactions.
"""

from typing import List
from itertools import combinations
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import crud, schemas

router = APIRouter(prefix="/interactions", tags=["Interactions"])


@router.get(
    "/check",
    response_model=schemas.DirectInteractionCheckResponse,
    summary="Check direct interaction between two drugs",
    description=(
        "Checks whether a direct interaction exists between two drugs. "
        "The order of inputs does not matter: check(1, 5) and check(5, 1) evaluate identically. "
        "Does NOT infer indirect or unverified clinical interactions."
    ),
)
def check_two_drug_interaction(
    drug1_id: int = Query(..., description="ID of the first drug"),
    drug2_id: int = Query(..., description="ID of the second drug"),
    db: Session = Depends(get_db),
):
    if drug1_id == drug2_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot check interaction between a drug and itself (self-interactions are not permitted).",
        )

    # Verify both drugs exist
    drug1 = crud.get_drug(db, drug_id=drug1_id)
    if not drug1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drug with ID {drug1_id} was not found.",
        )

    drug2 = crud.get_drug(db, drug_id=drug2_id)
    if not drug2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drug with ID {drug2_id} was not found.",
        )

    # Check for direct interaction
    interaction = crud.check_direct_interaction(db, drug1_id=drug1_id, drug2_id=drug2_id)

    if not interaction:
        return schemas.DirectInteractionCheckResponse(
            interaction_found=False,
            interaction=None,
        )

    return schemas.DirectInteractionCheckResponse(
        interaction_found=True,
        interaction=schemas.DirectInteractionDetail(
            interaction_id=interaction.interaction_id,
            drug_a=schemas.DrugSummary(
                drug_id=interaction.drug_a.drug_id,
                name=interaction.drug_a.name,
            ),
            drug_b=schemas.DrugSummary(
                drug_id=interaction.drug_b.drug_id,
                name=interaction.drug_b.name,
            ),
            severity=interaction.severity,
            description=interaction.description,
            source=interaction.source,
        ),
    )


@router.post(
    "/check-multiple",
    response_model=schemas.MultiDrugCheckResponse,
    summary="Check interactions among multiple drugs",
    description=(
        "Evaluates all unique pairwise combinations among a list of drugs in a single database query. "
        "Deduplicates input IDs, validates that all drugs exist, and returns all documented direct interactions. "
        "Reports only interactions documented in the current dataset (NOT clinical advice)."
    ),
)
def check_multiple_interactions(
    request: schemas.MultiDrugCheckRequest,
    db: Session = Depends(get_db),
):
    # 1. Deduplicate IDs while preserving stable order
    unique_drug_ids = list(dict.fromkeys(request.drug_ids))

    if len(unique_drug_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 unique drug IDs are required to perform an interaction check.",
        )

    # 2. Verify all requested drugs exist in database
    existing_drugs = crud.get_drugs_by_ids(db, drug_ids=unique_drug_ids)
    existing_id_set = {d.drug_id for d in existing_drugs}
    missing_ids = [d_id for d_id in unique_drug_ids if d_id not in existing_id_set]

    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The following requested drug ID(s) do not exist in the database: {missing_ids}",
        )

    # 3. Compute total pairwise combinations: N * (N - 1) / 2
    n = len(unique_drug_ids)
    pairs_count = (n * (n - 1)) // 2

    # 4. Perform a single SQL query to find all interactions within the drug set
    interactions = crud.check_multiple_interactions(db, drug_ids=unique_drug_ids)

    # 5. Format response items
    formatted_items: List[schemas.MultiDrugCheckItem] = []
    for inter in interactions:
        formatted_items.append(
            schemas.MultiDrugCheckItem(
                interaction_id=inter.interaction_id,
                drug_a=schemas.DrugSummary(
                    drug_id=inter.drug_a.drug_id,
                    name=inter.drug_a.name,
                ),
                drug_b=schemas.DrugSummary(
                    drug_id=inter.drug_b.drug_id,
                    name=inter.drug_b.name,
                ),
                severity=inter.severity,
                description=inter.description,
                source=inter.source,
            )
        )

    return schemas.MultiDrugCheckResponse(
        selected_drug_count=n,
        pairs_checked=pairs_count,
        interactions_found=len(formatted_items),
        interactions=formatted_items,
    )
