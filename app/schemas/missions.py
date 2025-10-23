from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class MissionStatus(str, Enum):
    ACTIVE = "ATIVA"
    COMPLETED = "CONCLUÍDA"
    FAILED = "FALHOU"


class ObjectiveType(str, Enum):
    GATHER_RESOURCE = "GATHER_RESOURCE"
    CONQUER_TERRITORY = "CONQUER_TERRITORY"
    DEFEAT_CHARACTER = "DEFEAT_CHARACTER"


class MissionObjective(BaseModel):
    """
    Este schema representa um sub-documento embutido no documento da Missão.
    Não tem um ID próprio, pois só existe no contexto de uma missão.
    """

    objective_type: ObjectiveType
    is_complete: bool = False
    target_resource_id: Optional[int] = None
    target_territory_id: Optional[int] = None
    target_quantity: Optional[int] = None
    current_progress: int = 0


class MissionBase(BaseModel):
    title: str
    world_id: int
    assignee_clan_id: int
    status: MissionStatus = MissionStatus.ACTIVE


class MissionCreate(MissionBase):
    objectives: List[MissionObjective]


class MissionResponse(MissionBase):
    """Schema de resposta da API para uma Missão."""

    id: int = Field(..., alias="_id")
    created_at: datetime
    objectives: List[MissionObjective]

    class Config:
        populate_by_name = True
        from_attributes = True
        json_encoders = {datetime: lambda dt: dt.isoformat()}
