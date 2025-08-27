from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

# --- Schemas para ResourceTypes ---
class ResourceTypeBase(BaseModel):
    name: str
    category: str
    base_value: int

class ResourceTypeCreate(ResourceTypeBase):
    pass

class ResourceType(ResourceTypeBase):
    id: int
    class Config:
        orm_mode = True

# --- Schemas para Territories ---
class TerritoryBase(BaseModel):
    name: str
    owner_clan_id: Optional[int] = None
    start_x: float
    end_x: float
    start_y: float
    end_y: float

class TerritoryCreate(TerritoryBase):
    pass

class Territory(TerritoryBase):
    id: int
    class Config:
        orm_mode = True

# --- Schemas para Missions ---
class MissionStatus(str, Enum):
    ACTIVE = "ATIVA"
    COMPLETED = "CONCLUÍDA"
    FAILED = "FALHOU"

class MissionBase(BaseModel):
    title: str
    assignee_clan_id: int
    status: MissionStatus = MissionStatus.ACTIVE

class MissionCreate(MissionBase):
    pass

class Mission(MissionBase):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

# --- Schemas para MissionObjectives ---
class ObjectiveType(str, Enum):
    GATHER_RESOURCE = "GATHER_RESOURCE"
    CONQUER_TERRITORY = "CONQUER_TERRITORY"
    DEFEAT_CHARACTER = "DEFEAT_CHARACTER"

class MissionObjectiveBase(BaseModel):
    mission_id: int
    objective_type: ObjectiveType
    target_resource_id: Optional[int] = None
    target_territory_id: Optional[int] = None
    target_quantity: Optional[int] = None
    is_complete: bool = False

class MissionObjectiveCreate(MissionObjectiveBase):
    pass

class MissionObjective(MissionObjectiveBase):
    id: int
    class Config:
        orm_mode = True
