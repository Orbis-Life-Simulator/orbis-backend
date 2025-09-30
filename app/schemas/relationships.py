from pydantic import BaseModel
from enum import Enum


class SpeciesRelationshipType(str, Enum):

    FRIEND = "FRIEND"
    ENEMY = "ENEMY"
    INDIFFERENT = "INDIFFERENT"


class SpeciesRelationshipBase(BaseModel):

    species_a_id: int
    species_b_id: int
    relationship_type: SpeciesRelationshipType


class SpeciesRelationshipCreate(SpeciesRelationshipBase):
    pass


class SpeciesRelationship(SpeciesRelationshipBase):

    id: int

    class Config:
        from_attributes = True


class ClanRelationshipType(str, Enum):

    WAR = "WAR"
    ALLIANCE = "ALLIANCE"
    NEUTRAL = "NEUTRAL"


class ClanRelationshipBase(BaseModel):

    clan_a_id: int
    clan_b_id: int
    relationship: ClanRelationshipType


class ClanRelationshipCreate(ClanRelationshipBase):

    pass


class ClanRelationship(ClanRelationshipBase):

    id: int

    class Config:

        from_attributes = True
