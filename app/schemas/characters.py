from pydantic import BaseModel
from typing import Optional

class CharacterBase(BaseModel):
    name: str
    species_id: int
    clan_id: Optional[int] = None
    current_health: int
    position_x: float
    position_y: float
    current_state: str
    target_character_id: Optional[int]

class CharacterCreate(CharacterBase):
    pass

# Schema para atualização, onde todos os campos são opcionais.
class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    clan_id: Optional[int] = None
    current_health: Optional[int] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    current_state: Optional[str] = None
    target_character_id: Optional[int] = None

class Character(CharacterBase):
    id: int

    class Config:
        from_attributes = True
