from pydantic import BaseModel, Field
from typing import Optional


class EmbeddedSpeciesInfo(BaseModel):
    """
    Uma representação simplificada da espécie, para ser embutida
    nas respostas da API sobre clãs.
    """

    id: int
    name: str


class ClanBase(BaseModel):
    """
    Schema base com os campos essenciais para um clã.
    """

    name: str
    species_id: int
    world_id: int


class ClanCreate(ClanBase):
    """

    Schema usado para validar os dados ao criar um novo clã via API.
    Herda todos os campos do ClanBase.
    """

    pass


class ClanResponse(BaseModel):
    """
    Este é o novo schema de resposta da API para um clã.
    Ele representa um documento da coleção `clans` e enriquece os dados
    com informações da espécie.
    """

    id: int = Field(..., alias="_id")
    name: str
    world_id: int

    species: EmbeddedSpeciesInfo

    class Config:
        from_attributes = True
        populate_by_name = True
