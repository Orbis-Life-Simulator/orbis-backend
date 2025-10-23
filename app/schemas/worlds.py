from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from .types import PyObjectId


class WorldBase(BaseModel):
    name: str
    map_width: int = 1000
    map_height: int = 1000


class WorldCreate(WorldBase):
    pass


class WorldResponse(WorldBase):
    """Schema de resposta da API para um mundo, adaptado para Pydantic V2."""

    id: PyObjectId = Field(..., alias="_id")
    user_id: PyObjectId = Field(..., alias="user_id")
    current_tick: int
    global_event: Optional[str] = None
    created_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {datetime: lambda dt: dt.isoformat()}
