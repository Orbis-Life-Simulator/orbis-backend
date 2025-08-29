from pydantic import BaseModel

# Propriedades base compartilhadas por todos os schemas de espécie.
class SpeciesBase(BaseModel):
    name: str
    base_health: int
    base_strength: int

# Schema para a criação de uma espécie (usado em requisições POST).
class SpeciesCreate(SpeciesBase):
    pass

# Schema para a leitura de uma espécie (usado em respostas GET).
class Species(SpeciesBase):
    id: int

    class Config:
        from_attributes = True
