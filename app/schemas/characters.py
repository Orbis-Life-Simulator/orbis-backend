from pydantic import BaseModel
from typing import Optional


class CharacterBase(BaseModel):

    name: str
    species_id: int
    clan_id: Optional[int] = None

    current_health: int
    position_x: float
    position_y: float

    fome: int
    energia: int
    idade: int
    reproduction_progress: int

    bravura: int
    cautela: int
    sociabilidade: int
    ganancia: int
    inteligencia: int


class CharacterCreate(CharacterBase):

    pass


class CharacterUpdate(BaseModel):

    name: Optional[str] = None
    clan_id: Optional[int] = None
    current_health: Optional[int] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None

    fome: Optional[int] = None
    energia: Optional[int] = None


class Character(CharacterBase):

    id: int

    class Config:

        from_attributes = True
