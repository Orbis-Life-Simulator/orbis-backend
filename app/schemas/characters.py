from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CharacterPosition(BaseModel):
    """Sub-documento para a posição do personagem."""

    x: float
    y: float


class CharacterVitals(BaseModel):
    """Sub-documento para os atributos vitais que mudam constantemente."""

    fome: int
    energia: int
    idade: int


class CharacterPersonality(BaseModel):
    """Sub-documento para os traços de personalidade, que são mais estáticos."""

    bravura: int
    cautela: int
    sociabilidade: int
    ganancia: int
    inteligencia: int


class CharacterStats(BaseModel):
    """Sub-documento para as estatísticas agregadas de desempenho."""

    kills: int
    deaths: int
    damageDealt: int
    resourcesCollected: int


class CharacterInventoryItem(BaseModel):
    """Schema para um único item no inventário do personagem."""

    resource_id: int
    name: str
    quantity: int


class NotableEvent(BaseModel):
    """Schema para um evento na "timeline" de um personagem."""

    timestamp: datetime
    type: str
    description: str


class EmbeddedClan(BaseModel):
    """Representação embutida de um clã, para evitar a necessidade de 'joins'."""

    id: int
    name: str


class EmbeddedSpecies(BaseModel):
    """Representação embutida de uma espécie."""

    id: int
    name: str
    base_strength: int


class CharacterSummaryResponse(BaseModel):
    """
    Este é o novo schema principal para um personagem, representando o documento
    da coleção `characters` (character_summaries). É usado para validar e
    documentar as respostas da API quando retornamos dados de um personagem.
    """

    id: int = Field(..., alias="_id")
    name: str
    world_id: int
    status: str
    species: EmbeddedSpecies
    clan: Optional[EmbeddedClan] = None
    current_health: int
    position: CharacterPosition
    vitals: CharacterVitals
    personality: CharacterPersonality
    stats: CharacterStats
    inventory: List[CharacterInventoryItem] = []
    notableEvents: List[NotableEvent] = []
    lastUpdate: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {datetime: lambda dt: dt.isoformat()}


class CharacterCreate(BaseModel):
    """
    Schema para criar um novo personagem via API (se você tiver essa funcionalidade).
    Os campos aqui seriam mais simples do que o schema de resposta.
    """

    name: str
    world_id: int
    species_id: int
    clan_id: Optional[int] = None
    start_pos_x: float = 500.0
    start_pos_y: float = 500.0
