from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CharacterRelationshipBase(BaseModel):

    character_a_id: int
    character_b_id: int
    relationship_score: float


class CharacterRelationshipCreate(CharacterRelationshipBase):
    pass


class CharacterRelationship(CharacterRelationshipBase):
    id: int
    last_interaction: datetime

    class Config:
        from_attributes = True


class CharacterAttributeBase(BaseModel):

    character_id: int
    attribute_name: str
    attribute_value: int


class CharacterAttributeCreate(CharacterAttributeBase):
    pass


class CharacterAttribute(CharacterAttributeBase):

    id: int

    class Config:
        from_attributes = True


class CharacterInventoryBase(BaseModel):

    character_id: int
    resource_type_id: int
    quantity: int


class CharacterInventoryCreate(CharacterInventoryBase):
    pass


class CharacterInventory(CharacterInventoryBase):

    id: int

    class Config:
        from_attributes = True
