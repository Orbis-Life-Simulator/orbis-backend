from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from ..dependencies import get_db
from ..schemas import clans as clan_schemas

COLLECTION_NAME = "clans"

router = APIRouter(
    prefix="/api/clans",
    tags=["Clans (MongoDB)"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/", response_model=clan_schemas.ClanResponse, status_code=status.HTTP_201_CREATED
)
async def create_clan(
    clan: clan_schemas.ClanCreate, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Cria um novo documento de clã na coleção 'clans'.
    """
    clan_dict = clan.dict()

    species_doc = await db.species.find_one({"_id": clan_dict["species_id"]})
    if not species_doc:
        raise HTTPException(
            status_code=404,
            detail=f"Species with id {clan_dict['species_id']} not found.",
        )

    world_doc = await db.worlds.find_one({"_id": clan_dict["world_id"]})
    if not world_doc:
        raise HTTPException(
            status_code=404, detail=f"World with id {clan_dict['world_id']} not found."
        )

    last_clan = await db[COLLECTION_NAME].find_one(sort=[("_id", -1)])
    new_id = (last_clan["_id"] + 1) if last_clan else 1

    new_clan_doc = {
        "_id": new_id,
        **clan_dict,
    }

    result = await db[COLLECTION_NAME].insert_one(new_clan_doc)

    created_doc = await db[COLLECTION_NAME].find_one({"_id": result.inserted_id})
    created_doc["species"] = {
        "id": species_doc["_id"],
        "name": species_doc["name"],
    }

    return created_doc


@router.get("/", response_model=List[clan_schemas.ClanResponse])
async def read_all_clans(
    skip: int = 0, limit: int = 100, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Retorna uma lista de clãs com paginação.
    Esta versão usa um pipeline de agregação para embutir os dados da espécie.
    """
    pipeline = [
        {"$sort": {"_id": 1}},
        {"$skip": skip},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "species",
                "localField": "species_id",
                "foreignField": "_id",
                "as": "species_info",
            }
        },
        {"$unwind": "$species_info"},
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "world_id": 1,
                "species": {"id": "$species_info._id", "name": "$species_info.name"},
            }
        },
    ]
    cursor = db[COLLECTION_NAME].aggregate(pipeline)
    clans_list = await cursor.to_list(length=limit)
    return clans_list


@router.get("/{clan_id}", response_model=clan_schemas.ClanResponse)
async def read_clan_by_id(clan_id: int, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Retorna um único clã pelo seu ID, com informações da espécie embutidas.
    """
    clan_doc = await db[COLLECTION_NAME].find_one({"_id": clan_id})

    if clan_doc is None:
        raise HTTPException(status_code=404, detail=f"Clan with id {clan_id} not found")

    species_doc = await db.species.find_one({"_id": clan_doc["species_id"]})
    if species_doc:
        clan_doc["species"] = {"id": species_doc["_id"], "name": species_doc["name"]}
    else:
        clan_doc["species"] = {"id": clan_doc["species_id"], "name": "Unknown"}

    return clan_doc
