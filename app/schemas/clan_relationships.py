from pydantic import BaseModel, Field
from enum import Enum


class ClanRelationshipType(str, Enum):
    WAR = "WAR"
    ALLIANCE = "ALLIANCE"
    NEUTRAL = "NEUTRAL"


class ClanRelationshipBase(BaseModel):
    """Schema base para uma relação entre clãs."""

    clan_a_id: int
    clan_b_id: int
    relationship_type: ClanRelationshipType


class ClanRelationshipCreate(ClanRelationshipBase):
    """Schema para criar uma nova relação entre clãs via API."""

    pass


class ClanRelationshipResponse(ClanRelationshipBase):
    """Schema de resposta da API para uma relação entre clãs."""

    id: str = Field(..., alias="_id")

    class Config:
        populate_by_name = True
        from_attributes = True
