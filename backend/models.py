"""
backend/models.py
-----------------
SQLAlchemy ORM models representing the graph structure:
  - Drug: Node in the graph
  - Interaction: Undirected edge in the graph
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import relationship
from backend.database import Base


class Drug(Base):
    """
    Represents a Drug entity (Graph Node).

    Attributes:
        drug_id: Unique integer identifier and primary key.
        name: Normalized unique drug name, indexed for fast case-insensitive search.
    """
    __tablename__ = "drugs"

    drug_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, index=True)

    def __repr__(self) -> str:
        return f"<Drug(drug_id={self.drug_id}, name='{self.name}')>"


class Interaction(Base):
    """
    Represents an Interaction between two drugs (Undirected Graph Edge).

    Undirected Integrity Strategy:
      In an undirected graph, an interaction between Drug A and Drug B is identical
      to an interaction between Drug B and Drug A (A-B == B-A).
      To guarantee that no duplicate reverse rows exist in the database:
        1. A CheckConstraint enforces that drug_a_id < drug_b_id (canonical ordering).
        2. A UniqueConstraint enforces that the canonical pair (drug_a_id, drug_b_id) is unique.
        3. Foreign keys link drug_a_id and drug_b_id directly to drugs.drug_id.
    """
    __tablename__ = "interactions"

    interaction_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    drug_a_id = Column(
        Integer,
        ForeignKey("drugs.drug_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    drug_b_id = Column(
        Integer,
        ForeignKey("drugs.drug_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    severity = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    source = Column(String(255), nullable=True)

    # Relationships to access the Drug models easily from Python
    drug_a = relationship("Drug", foreign_keys=[drug_a_id], backref="interactions_as_a")
    drug_b = relationship("Drug", foreign_keys=[drug_b_id], backref="interactions_as_b")

    # Table constraints:
    # 1. Enforce canonical ordering: drug_a_id must always be strictly less than drug_b_id.
    #    This prevents self-interactions (A-A) and eliminates reversed duplicates (B-A).
    # 2. Enforce uniqueness on the canonical pair.
    __table_args__ = (
        CheckConstraint("drug_a_id < drug_b_id", name="check_canonical_drug_order"),
        UniqueConstraint("drug_a_id", "drug_b_id", name="uq_canonical_drug_pair"),
        Index("ix_interactions_pair", "drug_a_id", "drug_b_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Interaction(id={self.interaction_id}, "
            f"pair=({self.drug_a_id}, {self.drug_b_id}), severity='{self.severity}')>"
        )
