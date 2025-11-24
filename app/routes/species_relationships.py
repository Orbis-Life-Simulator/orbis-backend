# app/routes/species_relationships.py

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import List

from ..dependencies import get_db
from ..schemas import species_relationships as sr_schemas

COLLECTION_NAME = "species_relationships"

router = APIRouter(
    prefix="/api/relationships/species",
    tags=["Species Relationships (MongoDB)"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/",
    response_model=sr_schemas.SpeciesRelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_species_relationship(
    relationship: sr_schemas.SpeciesRelationshipCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Define uma nova relação padrão entre duas espécies.
    """
    rel_dict = relationship.dict()

    result = await db[COLLECTION_NAME].insert_one(rel_dict)
    created_doc = await db[COLLECTION_NAME].find_one({"_id": result.inserted_id})
    return created_doc


@router.get("/", response_model=List[sr_schemas.SpeciesRelationshipResponse])
async def get_all_species_relationships(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Lista todas as relações padrão definidas entre as espécies.
    """
    cursor = db[COLLECTION_NAME].find()
    return await cursor.to_list(length=None)


@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_species_relationship(
    relationship_id: str, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Deleta uma relação entre espécies pelo seu _id (ObjectID string).
    """
    try:
        obj_id = ObjectId(relationship_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectID format.")

    delete_result = await db[COLLECTION_NAME].delete_one({"_id": obj_id})

    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return
