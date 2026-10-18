"""
backend/crud.py
---------------
Data Access / Service Layer for database queries.
Separates SQL / ORM logic from route controllers for modularity and readability.
"""

from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from backend.models import Drug, Interaction


def get_drug(db: Session, drug_id: int) -> Optional[Drug]:
    """
    Fetches a single drug by its primary key ID.
    Returns None if not found.
    """
    return db.query(Drug).filter(Drug.drug_id == drug_id).first()


def get_drugs(db: Session, skip: int = 0, limit: int = 20) -> List[Drug]:
    """
    Fetches a paginated list of drugs ordered by drug_id.
    """
    return db.query(Drug).order_by(Drug.drug_id.asc()).offset(skip).limit(limit).all()


def search_drugs(db: Session, query: str, limit: int = 20) -> List[Drug]:
    """
    Performs case-insensitive substring search on drug names.
    Orders results alphabetically.
    """
    clean_query = query.strip()
    return (
        db.query(Drug)
        .filter(Drug.name.ilike(f"%{clean_query}%"))
        .order_by(Drug.name.asc())
        .limit(limit)
        .all()
    )


def get_drugs_by_ids(db: Session, drug_ids: List[int]) -> List[Drug]:
    """
    Fetches multiple drugs matching a list of drug IDs in a single query.
    """
    return db.query(Drug).filter(Drug.drug_id.in_(drug_ids)).all()


def get_drug_interactions(db: Session, drug_id: int) -> List[Tuple[Interaction, Drug]]:
    """
    Finds all direct interactions involving the given drug_id.
    Because our graph is undirected, the drug may be stored as either drug_a_id or drug_b_id.

    Returns:
        A list of tuples: (interaction_record, other_drug_record)
    """
    # Fetch interactions where the drug appears on either side of the edge
    # Eagerly load drug_a and drug_b relationships to avoid N+1 queries
    interactions = (
        db.query(Interaction)
        .options(joinedload(Interaction.drug_a), joinedload(Interaction.drug_b))
        .filter(or_(Interaction.drug_a_id == drug_id, Interaction.drug_b_id == drug_id))
        .order_by(Interaction.interaction_id.asc())
        .all()
    )

    results: List[Tuple[Interaction, Drug]] = []
    for inter in interactions:
        # Determine which side of the relationship is the "other" drug
        other_drug = inter.drug_b if inter.drug_a_id == drug_id else inter.drug_a
        results.append((inter, other_drug))

    return results


def check_direct_interaction(db: Session, drug1_id: int, drug2_id: int) -> Optional[Interaction]:
    """
    Determines whether a direct interaction exists between two drugs.
    Canonicalizes the input (min_id, max_id) so the query is order-independent:
    check(1, 5) and check(5, 1) evaluate identically against canonical storage.
    """
    min_id, max_id = sorted([drug1_id, drug2_id])
    return (
        db.query(Interaction)
        .options(joinedload(Interaction.drug_a), joinedload(Interaction.drug_b))
        .filter(Interaction.drug_a_id == min_id, Interaction.drug_b_id == max_id)
        .first()
    )


def check_multiple_interactions(db: Session, drug_ids: List[int]) -> List[Interaction]:
    """
    Finds all direct interactions that occur entirely within a set of drug IDs.
    Executes a single efficient SQL query instead of querying each pair separately:
      SELECT * FROM interactions WHERE drug_a_id IN (...) AND drug_b_id IN (...)
    """
    return (
        db.query(Interaction)
        .options(joinedload(Interaction.drug_a), joinedload(Interaction.drug_b))
        .filter(
            Interaction.drug_a_id.in_(drug_ids),
            Interaction.drug_b_id.in_(drug_ids),
        )
        .order_by(Interaction.interaction_id.asc())
        .all()
    )


def get_statistics(db: Session) -> Dict[str, Any]:
    """
    Aggregates database counts for drugs, interactions, and severity categories.
    Only computes statistics from actual stored data without inventing categories.
    """
    total_drugs = db.query(func.count(Drug.drug_id)).scalar() or 0
    total_interactions = db.query(func.count(Interaction.interaction_id)).scalar() or 0

    severity_counts_query = (
        db.query(Interaction.severity, func.count(Interaction.interaction_id))
        .group_by(Interaction.severity)
        .all()
    )

    # Convert query results to dictionary: { 'major': 4, 'moderate': 6, ... }
    severity_counts = {severity: count for severity, count in severity_counts_query}

    return {
        "total_drugs": total_drugs,
        "total_interactions": total_interactions,
        "severity_counts": severity_counts,
    }
