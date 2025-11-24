from pydantic import BaseModel, Field
from typing import Any, Dict
from datetime import datetime
import uuid


class EventResponse(BaseModel):
    """
    Schema para um documento de evento, conforme a arquitetura de Big Data.
    Ajustado para aceitar os tipos reais gerados por create_event():
    - eventId é armazenado como string UUID
    - worldId pode ser string (ObjectId em string) ou int; aqui usamos str para compatibilidade
    """

    mongo_id: str = Field(..., alias="_id")

    eventId: str

    worldId: str

    timestamp: datetime
    eventType: str

    payload: Dict[str, Any]

    class Config:
        populate_by_name = True
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
        }
