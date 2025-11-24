from pydantic import BaseModel, Field
from enum import Enum


class SpeciesRelationshipType(str, Enum):
    FRIEND = "FRIEND"
    ENEMY = "ENEMY"
    INDIFFERENT = "INDIFFERENT"


class SpeciesRelationshipBase(BaseModel):
    """Schema base para uma relação entre espécies."""

    species_a_id: int
    species_b_id: int
    relationship_type: SpeciesRelationshipType


class SpeciesRelationshipCreate(SpeciesRelationshipBase):
    """Schema para criar uma nova relação entre espécies via API."""

    pass


class SpeciesRelationshipResponse(SpeciesRelationshipBase):
    """Schema de resposta da API para uma relação entre espécies."""

    id: str = Field(..., alias="_id")

    class Config:
        populate_by_name = True
        from_attributes = True
