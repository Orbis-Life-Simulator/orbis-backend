# app/schemas/characters.py

from pydantic import BaseModel
from typing import Optional

# Estes schemas definem a estrutura de dados para a entidade 'Character'.
# Eles são usados pelo FastAPI para validar dados e formatar respostas da API.


class CharacterBase(BaseModel):
    """
    Schema base para um Personagem. Contém todos os campos que definem um personagem
    na simulação, refletindo o novo modelo de dados do banco.
    """

    # --- Atributos Fundamentais ---
    name: str
    species_id: int
    clan_id: Optional[int] = None

    # --- Atributos de Estado Dinâmicos ---
    current_health: int
    position_x: float
    position_y: float

    # --- Atributos de Necessidades e Progressão ---
    fome: int
    energia: int
    idade: int
    reproduction_progress: int

    # --- Traços de Personalidade (Fixos) ---
    bravura: int
    cautela: int
    sociabilidade: int
    ganancia: int
    inteligencia: int


class CharacterCreate(CharacterBase):
    """
    Schema para criar um novo personagem (ex: via POST /api/characters).
    Herda todos os campos do CharacterBase.
    """

    # Você pode adicionar validações específicas para criação aqui no futuro, se necessário.
    pass


class CharacterUpdate(BaseModel):
    """
    Schema para atualizar parcialmente um personagem (PATCH).
    Permite a modificação de estados dinâmicos pela API.
    Os traços de personalidade geralmente não são alterados via PATCH,
    mas poderiam ser adicionados aqui se necessário.
    """

    # Campos que podem ser atualizados durante a simulação ou por um administrador.
    name: Optional[str] = None
    clan_id: Optional[int] = None
    current_health: Optional[int] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None

    # Também podemos permitir a atualização de necessidades via API, se desejado.
    fome: Optional[int] = None
    energia: Optional[int] = None


class Character(CharacterBase):
    """
    Schema completo para representar um personagem em respostas da API (GET).
    Herda do CharacterBase e adiciona o 'id' gerado pelo banco de dados.
    """

    id: int

    class Config:
        """
        Permite que o Pydantic crie este schema a partir de um objeto de modelo SQLAlchemy.
        """

        from_attributes = True
