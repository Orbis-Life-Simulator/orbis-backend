from pydantic import BaseModel, Field


class SpeciesBase(BaseModel):
    """
    Schema base com os campos essenciais para uma espécie.
    Estes são os dados estáticos que definem o arquétipo de uma raça.
    """

    name: str
    base_health: int
    base_strength: int


class SpeciesCreate(SpeciesBase):
    """
    Schema usado para validar os dados ao criar uma nova espécie via API.
    Nenhum campo adicional é necessário para a criação.
    """

    pass


class SpeciesResponse(SpeciesBase):
    """
    Este é o schema de resposta da API para uma espécie.
    Ele representa um documento da coleção `species`.
    """

    id: int = Field(..., alias="_id")

    class Config:
        populate_by_name = True
        from_attributes = True
