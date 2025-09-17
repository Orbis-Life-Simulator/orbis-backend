from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class WorldBase(BaseModel):

    name: str
    map_width: int
    map_height: int

    current_time_of_day: str = "Dia"
    global_event: Optional[str] = None


class WorldCreate(WorldBase):

    pass


class WorldUpdate(BaseModel):

    current_tick: Optional[int] = None
    current_time_of_day: Optional[str] = None
    global_event: Optional[str] = None


class World(WorldBase):

    id: int
    current_tick: int
    created_at: datetime

    class Config:

        from_attributes = True


class EventLogBase(BaseModel):

    event_type: str
    description: str

    primary_char_id: Optional[int] = None
    secondary_char_id: Optional[int] = None
    clan_a_id: Optional[int] = None
    clan_b_id: Optional[int] = None


class EventLogCreate(EventLogBase):
    pass


class EventLog(EventLogBase):

    id: int
    timestamp: datetime

    class Config:
        from_attributes = True
