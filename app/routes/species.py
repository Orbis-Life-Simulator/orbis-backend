from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from ..dependencies import get_db
from ..schemas import species as species_schemas

COLLECTION_NAME = "species"

router = APIRouter(
    prefix="/api/species",
    tags=["Species (MongoDB)"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/",
    response_model=species_schemas.SpeciesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_species(
    species: species_schemas.SpeciesCreate, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Cria um novo documento de espécie na coleção 'species'.
    """
    species_dict = species.dict()

    last_item = await db[COLLECTION_NAME].find_one(sort=[("_id", -1)])
    new_id = (last_item["_id"] + 1) if last_item else 1

    doc_to_insert = {"_id": new_id, **species_dict}

    result = await db[COLLECTION_NAME].insert_one(doc_to_insert)
    created_doc = await db[COLLECTION_NAME].find_one({"_id": result.inserted_id})
    return created_doc


@router.get("/", response_model=List[species_schemas.SpeciesResponse])
async def read_all_species(
    skip: int = 0, limit: int = 100, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Retorna uma lista de todas as espécies, com suporte a paginação.
    """
    cursor = db[COLLECTION_NAME].find().skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


@router.get("/{species_id}", response_model=species_schemas.SpeciesResponse)
async def read_species_by_id(
    species_id: int, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Retorna uma única espécie pelo seu ID.
    """
    species_doc = await db[COLLECTION_NAME].find_one({"_id": species_id})
    if species_doc is None:
        raise HTTPException(status_code=404, detail="Species not found")
    return species_doc


@router.put("/{species_id}", response_model=species_schemas.SpeciesResponse)
async def update_species(
    species_id: int,
    species: species_schemas.SpeciesCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Atualiza (substitui) completamente os dados de uma espécie existente.
    """
    update_data = species.dict()

    updated_doc = await db[COLLECTION_NAME].find_one_and_replace(
        {"_id": species_id},
        update_data,
        return_document=True,
    )

    if updated_doc is None:
        raise HTTPException(
            status_code=404, detail=f"Species with id {species_id} not found to update"
        )

    updated_doc["_id"] = species_id
    return updated_doc


@router.delete("/{species_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_species(species_id: int, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Deleta uma espécie pelo seu ID.
    """
    delete_result = await db[COLLECTION_NAME].delete_one({"_id": species_id})

    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Species not found")

    return
