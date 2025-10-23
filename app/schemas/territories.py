from pydantic import BaseModel, Field
from typing import Optional


class TerritoryBase(BaseModel):
    name: str
    world_id: int
    start_x: float
    end_x: float
    start_y: float
    end_y: float


class TerritoryCreate(TerritoryBase):
    owner_clan_id: Optional[int] = None


class TerritoryResponse(TerritoryBase):
    """Schema de resposta da API para um território."""

    id: int = Field(..., alias="_id")
    owner_clan_id: Optional[int] = None

    class Config:
        populate_by_name = True
        from_attributes = True
