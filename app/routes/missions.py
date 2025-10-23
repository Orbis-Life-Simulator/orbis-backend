import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Body
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from ..dependencies import get_db
from ..schemas import missions as mission_schemas

COLLECTION_NAME = "missions"

router = APIRouter(
    prefix="/api/missions",
    tags=["Missions (MongoDB)"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/",
    response_model=mission_schemas.MissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_mission_with_objectives(
    mission: mission_schemas.MissionCreate, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Cria uma nova missão, incluindo seus objetivos, em um único documento.
    """
    mission_dict = mission.dict(exclude_unset=True)

    if not await db.worlds.find_one({"_id": mission_dict["world_id"]}):
        raise HTTPException(status_code=404, detail="World not found")
    if not await db.clans.find_one({"_id": mission_dict["assignee_clan_id"]}):
        raise HTTPException(status_code=404, detail="Assignee clan not found")

    last_item = await db[COLLECTION_NAME].find_one(sort=[("_id", -1)])
    new_id = (last_item["_id"] + 1) if last_item else 1

    doc_to_insert = {
        "_id": new_id,
        "created_at": datetime.now(datetime.timezone.utc),
        **mission_dict,
    }

    result = await db[COLLECTION_NAME].insert_one(doc_to_insert)
    created_doc = await db[COLLECTION_NAME].find_one({"_id": result.inserted_id})
    return created_doc


@router.get("/", response_model=List[mission_schemas.MissionResponse])
async def get_all_missions(
    status: mission_schemas.MissionStatus = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Lista todas as missões, com a opção de filtrar por status.
    """
    query_filter = {}
    if status:
        query_filter["status"] = status

    cursor = db[COLLECTION_NAME].find(query_filter)
    return await cursor.to_list(length=None)


@router.patch(
    "/{mission_id}/objectives/{objective_index}",
    response_model=mission_schemas.MissionResponse,
)
async def update_objective_status(
    mission_id: int,
    objective_index: int,
    is_complete: bool = Body(..., embed=True),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Atualiza o status de um objetivo específico DENTRO de uma missão.

    - `objective_index`: A posição do objetivo no array 'objectives' (começando em 0).
    - `is_complete`: O novo status booleano, enviado no corpo da requisição como `{"is_complete": true}`.
    """
    update_field = f"objectives.{objective_index}.is_complete"

    updated_mission = await db[COLLECTION_NAME].find_one_and_update(
        {"_id": mission_id},
        {"$set": {update_field: is_complete}},
        return_document=True,
    )

    if not updated_mission:
        raise HTTPException(
            status_code=404, detail=f"Mission with id {mission_id} not found."
        )

    return updated_mission
