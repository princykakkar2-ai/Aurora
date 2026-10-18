"""
backend/schemas.py
------------------
Pydantic schemas for request validation and response serialization.
Keeps API contracts separate from SQLAlchemy database models.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict, Field, field_validator


# =====================================================================
# DRUG SCHEMAS
# =====================================================================

class DrugBase(BaseModel):
    """Base schema containing core drug fields."""
    name: str = Field(..., description="Normalized name of the drug")


class DrugResponse(DrugBase):
    """Schema for returning a single drug entity."""
    drug_id: int = Field(..., description="Unique integer ID of the drug")

    model_config = ConfigDict(from_attributes=True)


class DrugSummary(BaseModel):
    """Lightweight representation of a drug for nested interaction responses."""
    drug_id: int = Field(..., description="Unique integer ID of the drug")
    name: str = Field(..., description="Name of the drug")

    model_config = ConfigDict(from_attributes=True)


# =====================================================================
# INTERACTION SCHEMAS
# =====================================================================

class InteractionResponse(BaseModel):
    """Schema for returning raw interaction edge details."""
    interaction_id: int = Field(..., description="Unique interaction edge ID")
    drug_a_id: int = Field(..., description="ID of the first drug (canonical min)")
    drug_b_id: int = Field(..., description="ID of the second drug (canonical max)")
    severity: str = Field(..., description="Severity category (minor, moderate, major, unknown)")
    description: Optional[str] = Field(None, description="Clinical description or notes")
    source: Optional[str] = Field(None, description="Provenance source of the record")

    model_config = ConfigDict(from_attributes=True)


class DrugDirectInteraction(BaseModel):
    """
    Schema for an interaction relative to a requested drug.
    Specifies 'other_drug' instead of drug_a/drug_b for intuitive client consumption.
    """
    interaction_id: int
    other_drug: DrugSummary
    severity: str
    description: Optional[str] = None
    source: Optional[str] = None


class DrugWithInteractionsResponse(BaseModel):
    """Schema for GET /drugs/{drug_id}/interactions."""
    drug: DrugSummary
    interaction_count: int = Field(..., description="Total direct interactions for this drug")
    interactions: List[DrugDirectInteraction]


class DirectInteractionDetail(BaseModel):
    """Full detail of a direct interaction with both drug objects expanded."""
    interaction_id: int
    drug_a: DrugSummary
    drug_b: DrugSummary
    severity: str
    description: Optional[str] = None
    source: Optional[str] = None


class DirectInteractionCheckResponse(BaseModel):
    """Schema for GET /interactions/check?drug1_id=X&drug2_id=Y."""
    interaction_found: bool = Field(..., description="True if a direct interaction exists in the dataset")
    interaction: Optional[DirectInteractionDetail] = Field(
        None, description="Interaction detail if found, or null if none documented"
    )


# =====================================================================
# MULTI-DRUG CHECK SCHEMAS
# =====================================================================

class MultiDrugCheckRequest(BaseModel):
    """
    Request schema for POST /interactions/check-multiple.
    Accepts a list of drug IDs to check for pairwise interactions.
    """
    drug_ids: List[int] = Field(
        ...,
        description="List of integer drug IDs to check for mutual interactions (between 2 and 50 drugs)",
        examples=[[1, 2, 5, 9]],
    )

    @field_validator("drug_ids")
    @classmethod
    def validate_drug_ids(cls, v: List[int]) -> List[int]:
        if not v or len(v) < 2:
            raise ValueError("At least 2 drug IDs are required to perform an interaction check.")
        if len(v) > 50:
            raise ValueError("A maximum of 50 drugs can be checked at one time to prevent system overload.")
        return v


class MultiDrugCheckItem(BaseModel):
    """Represents a single direct interaction found among multiple drugs."""
    interaction_id: int
    drug_a: DrugSummary
    drug_b: DrugSummary
    severity: str
    description: Optional[str] = None
    source: Optional[str] = None


class MultiDrugCheckResponse(BaseModel):
    """Response schema for POST /interactions/check-multiple."""
    selected_drug_count: int = Field(..., description="Number of unique valid drugs selected")
    pairs_checked: int = Field(..., description="Number of pairwise combinations evaluated")
    interactions_found: int = Field(..., description="Number of direct interactions documented in the dataset")
    interactions: List[MultiDrugCheckItem] = Field(..., description="List of direct interactions detected")


# =====================================================================
# STATISTICS SCHEMA
# =====================================================================

class StatsResponse(BaseModel):
    """Schema for GET /stats."""
    total_drugs: int = Field(..., description="Total unique drug nodes in the database")
    total_interactions: int = Field(..., description="Total unique interaction edges in the database")
    severity_counts: Dict[str, int] = Field(
        ..., description="Count of interactions grouped by severity category"
    )
