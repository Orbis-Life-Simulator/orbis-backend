from pydantic import BaseModel, Field


class ResourceTypeBase(BaseModel):
    name: str
    category: str
    base_value: int


class ResourceTypeCreate(ResourceTypeBase):
    pass


class ResourceTypeResponse(ResourceTypeBase):
    """Schema de resposta da API para um tipo de recurso."""

    id: int = Field(..., alias="_id")

    class Config:
        populate_by_name = True
        from_attributes = True
