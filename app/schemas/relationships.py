from pydantic import BaseModel
from enum import Enum

# Enum para os tipos de relacionamento entre espécies
class SpeciesRelationshipType(str, Enum):
    FRIEND = "FRIEND"
    ENEMY = "ENEMY"
    INDIFFERENT = "INDIFFERENT"

class SpeciesRelationshipBase(BaseModel):
    species_a_id: int
    species_b_id: int
    relationship: SpeciesRelationshipType

class SpeciesRelationshipCreate(SpeciesRelationshipBase):
    pass

class SpeciesRelationship(SpeciesRelationshipBase):
    id: int

    class Config:
        orm_mode = True


# Enum para os tipos de relacionamento entre clãs
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
        orm_mode = True
