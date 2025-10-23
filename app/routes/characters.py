from fastapi import APIRouter, Depends, HTTPException, Body, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from ..dependencies import get_db

from ..schemas import characters as char_schemas

COLLECTION_NAME = "characters"

router = APIRouter(
    prefix="/api/characters",
    tags=["Characters (MongoDB)"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/",
    response_model=char_schemas.CharacterSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_character(
    character: char_schemas.CharacterCreate, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Cria um novo documento de personagem na coleção 'characters'.
    Retorna o personagem recém-criado.
    """
    character_dict = character.dict()

    species_doc = await db.species.find_one({"_id": character_dict["species_id"]})
    if not species_doc:
        raise HTTPException(
            status_code=404,
            detail=f"Species with id {character_dict['species_id']} not found.",
        )

    last_char = await db[COLLECTION_NAME].find_one(sort=[("_id", -1)])
    new_id = (last_char["_id"] + 1) if last_char else 1

    new_character_doc = {
        "_id": new_id,
        "name": character_dict["name"],
        "world_id": character_dict["world_id"],
        "status": "VIVO",
        "species": {
            "id": species_doc["_id"],
            "name": species_doc["name"],
            "base_strength": species_doc["base_strength"],
        },
        "current_health": species_doc["base_health"],
        "position": {"x": 500.0, "y": 500.0},
    }

    result = await db[COLLECTION_NAME].insert_one(new_character_doc)

    created_doc = await db[COLLECTION_NAME].find_one({"_id": result.inserted_id})

    return created_doc


@router.get("/", response_model=List[char_schemas.CharacterSummaryResponse])
async def read_all_characters(
    skip: int = 0, limit: int = 100, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Retorna uma lista de todos os personagens com paginação.
    """
    characters_cursor = db[COLLECTION_NAME].find().skip(skip).limit(limit)

    return await characters_cursor.to_list(length=limit)


@router.get("/{character_id}", response_model=char_schemas.CharacterSummaryResponse)
async def read_character_by_id(
    character_id: int, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Retorna um único personagem pelo seu ID.
    """
    character_doc = await db[COLLECTION_NAME].find_one({"_id": character_id})

    if character_doc is None:
        raise HTTPException(
            status_code=404, detail=f"Character with id {character_id} not found"
        )

    return character_doc
