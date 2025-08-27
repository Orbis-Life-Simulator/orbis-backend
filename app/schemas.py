from pydantic import BaseModel

class SpeciesBase(BaseModel):
    name: str
    base_health: int
    base_strength: int

class SpeciesCreate(SpeciesBase):
    pass

class Species(SpeciesBase):
    id: int

    class Config:
        orm_mode = True
