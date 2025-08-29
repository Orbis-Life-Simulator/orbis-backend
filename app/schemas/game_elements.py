from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum

# --- Schemas para ResourceTypes (Tipos de Recurso) ---
# Define os diferentes tipos de recursos que podem existir no mundo, como "Madeira", "Pedra" ou "Comida".

class ResourceTypeBase(BaseModel):
    """
    Schema base para um tipo de recurso. Contém as propriedades fundamentais.
    """
    name: str       # O nome do recurso (ex: "Fruta Silvestre").
    category: str   # A categoria do recurso (ex: "COMIDA", "MATERIAL").
    base_value: int # Um valor base, que pode ser usado para comércio ou pontuação.

class ResourceTypeCreate(ResourceTypeBase):
    """
    Schema para criar um novo tipo de recurso. Herda todos os campos do Base.
    """
    pass

class ResourceType(ResourceTypeBase):
    """
    Schema completo para representar um tipo de recurso lido do banco de dados.
    """
    id: int # O ID único do tipo de recurso.

    class Config:
        # Permite que o Pydantic crie uma instância deste schema a partir de um objeto ORM.
        from_attributes = True

# --- Schemas para Territories (Territórios) ---
# Define as áreas geográficas nomeadas no mapa do mundo.

class TerritoryBase(BaseModel):
    """
    Schema base para um território.
    """
    name: str                   # Nome do território (ex: "Floresta Sombria").
    owner_clan_id: Optional[int] = None # ID do clã que atualmente controla o território. Opcional.
    start_x: float              # Coordenada X inicial da área retangular do território.
    end_x: float                # Coordenada X final da área retangular.
    start_y: float              # Coordenada Y inicial da área retangular.
    end_y: float                # Coordenada Y final da área retangular.

class TerritoryCreate(TerritoryBase):
    """
    Schema para criar um novo território.
    """
    pass

class Territory(TerritoryBase):
    """
    Schema completo para representar um território lido do banco de dados.
    """
    id: int # O ID único do território.

    class Config:
        from_attributes = True

# --- Schemas para Missions (Missões) ---
# Define as missões ou quests que podem ser atribuídas aos clãs.

class MissionStatus(str, Enum):
    """
    Define os possíveis status de uma missão usando um Enum para garantir
    consistência e evitar erros de digitação.
    """
    ACTIVE = "ATIVA"
    COMPLETED = "CONCLUÍDA"
    FAILED = "FALHOU"

class MissionBase(BaseModel):
    """
    Schema base para uma missão.
    """
    title: str              # O título ou nome da missão.
    assignee_clan_id: int   # O ID do clã responsável por completar a missão.
    status: MissionStatus = MissionStatus.ACTIVE # O status atual da missão, com "ATIVA" como padrão.

class MissionCreate(MissionBase):
    """
    Schema para criar uma nova missão.
    """
    pass

class Mission(MissionBase):
    """
    Schema completo para representar uma missão lida do banco de dados.
    """
    id: int                 # O ID único da missão.
    created_at: datetime    # A data e hora em que a missão foi criada.

    class Config:
        from_attributes = True

# --- Schemas para MissionObjectives (Objetivos da Missão) ---
# Define as tarefas específicas que precisam ser concluídas para uma missão ter sucesso.

class ObjectiveType(str, Enum):
    """
    Define os tipos de objetivos possíveis para uma missão.
    """
    GATHER_RESOURCE = "GATHER_RESOURCE"       # Coletar uma quantidade de um recurso.
    CONQUER_TERRITORY = "CONQUER_TERRITORY"   # Conquistar um território.
    DEFEAT_CHARACTER = "DEFEAT_CHARACTER"     # Derrotar um personagem específico (não implementado no schema base).

class MissionObjectiveBase(BaseModel):
    """
    Schema base para um objetivo de missão.
    """
    mission_id: int             # O ID da missão à qual este objetivo pertence.
    objective_type: ObjectiveType # O tipo de objetivo, conforme definido no Enum.
    
    # Os campos de alvo são opcionais, pois um objetivo terá apenas um deles preenchido.
    # Por exemplo, um objetivo GATHER_RESOURCE terá target_resource_id e target_quantity.
    # Um objetivo CONQUER_TERRITORY terá apenas target_territory_id.
    target_resource_id: Optional[int] = None
    target_territory_id: Optional[int] = None
    target_quantity: Optional[int] = None
    
    is_complete: bool = False   # Um booleano que indica se o objetivo foi concluído. Padrão é False.

class MissionObjectiveCreate(MissionObjectiveBase):
    """
    Schema para criar um novo objetivo de missão.
    """
    pass

class MissionObjective(MissionObjectiveBase):
    """
    Schema completo para representar um objetivo de missão lido do banco de dados.
    """
    id: int # O ID único do objetivo.

    class Config:
        from_attributes = True

# --- Schema para ResourceNode (Nó de Recurso) ---
# Define uma instância específica de um recurso no mapa, que pode ser coletada.

class ResourceNode(BaseModel):
    """
    Representa um ponto de recurso no mapa (ex: uma árvore, uma mina).
    Este schema é usado principalmente para leitura/envio de dados do estado do mundo.
    """
    id: int                 # ID único do nó de recurso.
    position_x: float       # Coordenada X da localização do nó no mapa.
    position_y: float       # Coordenada Y da localização do nó.
    resource_type_id: int   # O ID do tipo de recurso que este nó fornece.
    is_depleted: bool       # Indica se o nó já foi esgotado e não pode mais ser coletado.

    # Esta é a sintaxe atualizada do Pydantic v2 para habilitar o "ORM mode".
    # Ela tem a mesma função da 'class Config' nos outros schemas.
    model_config = ConfigDict(from_attributes=True)
