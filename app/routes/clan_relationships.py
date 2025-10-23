from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from ..dependencies import get_db
from ..schemas import clan_relationships as cr_schemas

COLLECTION_NAME = "clan_relationships"

router = APIRouter(
    prefix="/api/relationships/clans",
    tags=["Clan Relationships (MongoDB)"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/",
    response_model=cr_schemas.ClanRelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_clan_relationship(
    relationship: cr_schemas.ClanRelationshipCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Define uma nova relação política/diplomática entre dois clãs.
    """
    rel_dict = relationship.dict()

    result = await db[COLLECTION_NAME].insert_one(rel_dict)
    created_doc = await db[COLLECTION_NAME].find_one({"_id": result.inserted_id})
    return created_doc


@router.get("/", response_model=List[cr_schemas.ClanRelationshipResponse])
async def get_all_clan_relationships(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Lista todas as relações políticas (diplomacia) ativas entre clãs.
    """
    cursor = db[COLLECTION_NAME].find()
    return await cursor.to_list(length=None)
