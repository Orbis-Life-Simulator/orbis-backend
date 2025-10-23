from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING
from typing import List, Optional

from bson import ObjectId

from ..dependencies import get_db
from ..schemas import events as event_schemas

COLLECTION_NAME = "events"

router = APIRouter(
    prefix="/api/events",
    tags=["Event Logs (MongoDB)"],
    responses={404: {"description": "Not found"}},
)


@router.get("/{world_id}", response_model=List[event_schemas.EventResponse])
async def get_world_events(
    world_id: str,
    limit: int = 50,
    char_id: Optional[int] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Retorna o log de eventos para um mundo específico, ordenado do mais recente
    para o mais antigo. Permite filtrar opcionalmente por um personagem envolvido.
    """

    candidates = []
    try:
        candidates.append(int(world_id))
    except Exception:
        pass

    if len(world_id) == 24:
        try:
            candidates.append(ObjectId(world_id))
        except Exception:
            pass

    candidates.append(world_id)

    if len(set(map(type, candidates))) == 1 and len(candidates) == 1:
        query_filter = {"worldId": candidates[0]}
    else:
        query_filter = {"worldId": {"$in": list(dict.fromkeys(candidates))}}

    cursor = (
        db[COLLECTION_NAME]
        .find(filter=query_filter)
        .sort("timestamp", DESCENDING)
        .limit(limit)
    )
    events_list = await cursor.to_list(length=limit)

    # Normaliza ObjectId para string recursivamente
    def _stringify_oids(obj):
        if isinstance(obj, dict):
            return {k: _stringify_oids(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_stringify_oids(i) for i in obj]
        if isinstance(obj, ObjectId):
            return str(obj)
        return obj

    normalized = [_stringify_oids(ev) for ev in events_list]

    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(normalized)
