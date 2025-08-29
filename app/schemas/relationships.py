from pydantic import BaseModel
from enum import Enum

# Este arquivo define os schemas Pydantic para gerenciar os relacionamentos
# em dois níveis distintos:
# 1. SpeciesRelationship: A relação natural e padrão entre duas espécies (ex: predador/presa).
# 2. ClanRelationship: A relação diplomática entre dois clãs (ex: guerra/aliança),
#    que pode sobrepor a relação natural entre as espécies.


# --- Schemas para Relacionamento entre Espécies ---

class SpeciesRelationshipType(str, Enum):
    """
    Define os tipos de relacionamento padrão possíveis entre duas espécies.
    O uso de um Enum garante que apenas valores válidos possam ser usados,
    evitando erros de digitação e mantendo a consistência dos dados.
    """
    FRIEND = "FRIEND"           # Espécies que cooperam ou são amigáveis por natureza.
    ENEMY = "ENEMY"             # Espécies que são predadoras/presas ou naturalmente hostis.
    INDIFFERENT = "INDIFFERENT" # Espécies que se ignoram mutuamente por padrão.

class SpeciesRelationshipBase(BaseModel):
    """
    Schema base para definir um relacionamento entre duas espécies.
    """
    species_a_id: int   # O ID da primeira espécie no relacionamento.
    species_b_id: int   # O ID da segunda espécie no relacionamento.
    relationship_type: SpeciesRelationshipType # O tipo de relacionamento, usando o Enum definido acima.

class SpeciesRelationshipCreate(SpeciesRelationshipBase):
    """
    Schema para validar os dados ao criar um novo relacionamento entre espécies.
    Herda todos os campos do Base.
    """
    pass

class SpeciesRelationship(SpeciesRelationshipBase):
    """
    Schema completo para representar um relacionamento entre espécies,
    geralmente ao ser retornado pela API. Inclui o ID do banco de dados.
    """
    id: int # O ID único deste registro de relacionamento.

    class Config:
        """
        Configuração do Pydantic para permitir a criação do schema a partir
        de um modelo de ORM (como SQLAlchemy).
        """
        from_attributes = True


# --- Schemas para Relacionamento entre Clãs ---

class ClanRelationshipType(str, Enum):
    """
    Define os possíveis status diplomáticos entre dois clãs.
    Essas relações são dinâmicas e podem mudar durante a simulação.
    """
    WAR = "WAR"           # Os clãs estão em guerra e seus membros são inimigos.
    ALLIANCE = "ALLIANCE" # Os clãs são aliados e seus membros são amigos.
    NEUTRAL = "NEUTRAL"   # Os clãs têm uma relação neutra/indiferente.

class ClanRelationshipBase(BaseModel):
    """
    Schema base para definir um relacionamento diplomático entre dois clãs.
    """
    clan_a_id: int    # O ID do primeiro clã.
    clan_b_id: int    # O ID do segundo clã.
    relationship: ClanRelationshipType # O status diplomático entre eles.

class ClanRelationshipCreate(ClanRelationshipBase):
    """
    Schema para validar os dados ao criar uma nova relação diplomática entre clãs.
    """
    pass

class ClanRelationship(ClanRelationshipBase):
    """
    Schema completo para representar um relacionamento entre clãs, incluindo o ID.
    """
    id: int # O ID único deste registro de diplomacia.

    class Config:
        """
        Permite que o schema seja populado a partir de um objeto de banco de dados.
        """
        from_attributes = True
