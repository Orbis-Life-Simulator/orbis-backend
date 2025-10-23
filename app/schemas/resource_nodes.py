from typing import Optional
from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float
    y: float


class ResourceNodeBase(BaseModel):
    world_id: int
    resource_type_id: int
    territory_id: Optional[int] = None
    position: Position
    quantity: int


class ResourceNodeCreate(ResourceNodeBase):
    pass


class ResourceNodeResponse(ResourceNodeBase):
    """Schema de resposta da API para um nó de recurso."""

    id: int = Field(..., alias="_id")
    is_depleted: bool

    class Config:
        populate_by_name = True
        from_attributes = True
