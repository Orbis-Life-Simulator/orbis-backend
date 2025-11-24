from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from ..dependencies import get_db
from ..schemas import resource_types as rt_schemas

COLLECTION_NAME = "resource_types"

router = APIRouter(
    prefix="/api/resource-types",
    tags=["Resource Types (MongoDB)"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/",
    response_model=rt_schemas.ResourceTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_resource_type(
    resource_type: rt_schemas.ResourceTypeCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Cria um novo tipo de recurso (template) que pode existir no mundo.
    """
    resource_dict = resource_type.dict()

    last_item = await db[COLLECTION_NAME].find_one(sort=[("_id", -1)])
    new_id = (last_item["_id"] + 1) if last_item else 1

    doc_to_insert = {"_id": new_id, **resource_dict}

    result = await db[COLLECTION_NAME].insert_one(doc_to_insert)
    created_doc = await db[COLLECTION_NAME].find_one({"_id": result.inserted_id})
    return created_doc


@router.get("/", response_model=List[rt_schemas.ResourceTypeResponse])
async def get_all_resource_types(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Lista todos os tipos de recursos definidos no sistema.
    """
    cursor = db[COLLECTION_NAME].find()
    return await cursor.to_list(length=None)
