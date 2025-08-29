from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Pydantic Schemas (também conhecidos como "modelos") são usados para definir a estrutura
# dos dados da sua API. Eles garantem:
# 1. Validação: Os dados recebidos correspondem ao tipo e formato esperados.
# 2. Serialização: Converte objetos complexos (como modelos do SQLAlchemy) em JSON.
# 3. Documentação: FastAPI usa esses schemas para gerar automaticamente a documentação
#    interativa da API (ex: Swagger UI / OpenAPI).

# O padrão comum é ter três tipos de schemas para cada entidade:
# - Base: Contém os campos comuns, compartilhados entre criação e leitura.
# - Create: Usado especificamente para validar os dados de entrada ao criar um novo item.
# - "Model" (principal): Usado para formatar os dados de saída ao ler um item do banco de dados.

# --- Schemas para CharacterRelationship (Relacionamento entre Personagens) ---

class CharacterRelationshipBase(BaseModel):
    """
    Schema base para um relacionamento. Define os campos essenciais que
    sempre estarão presentes, seja na criação ou na leitura.
    """
    character_a_id: int     # ID do primeiro personagem no relacionamento.
    character_b_id: int     # ID do segundo personagem.
    relationship_score: float # Um valor numérico que quantifica o relacionamento (ex: -100 para inimigos, 100 para amigos).

class CharacterRelationshipCreate(CharacterRelationshipBase):
    """
    Schema para criar um novo relacionamento. Herda todos os campos do Base.
    Neste caso, não há campos adicionais necessários para a criação, então
    usamos 'pass'. Manter essa classe separada é uma boa prática para futuras extensões.
    """
    pass

class CharacterRelationship(CharacterRelationshipBase):
    """
    Schema completo para representar um relacionamento, geralmente ao ser retornado pela API.
    Ele inclui os campos que são gerados pelo banco de dados.
    """
    id: int                     # ID único do registro de relacionamento no banco de dados.
    last_interaction: datetime  # Data e hora da última interação significativa, gerenciado pelo sistema.

    class Config:
        """
        Configurações internas do modelo Pydantic.
        """
        # 'from_attributes = True' (anteriormente 'orm_mode') permite que o modelo Pydantic seja criado
        # diretamente a partir de um objeto de modelo do SQLAlchemy (ou outro ORM).
        # Ele instrui o Pydantic a ler os valores dos atributos do objeto (ex: rel.id)
        # em vez de esperar um dicionário (ex: rel['id']).
        from_attributes = True

# --- Schemas para CharacterAttributes (Atributos de Personagem) ---

class CharacterAttributeBase(BaseModel):
    """
    Schema base para um atributo de personagem, como "Fome", "Força", etc.
    """
    character_id: int   # ID do personagem ao qual este atributo pertence.
    attribute_name: str # Nome do atributo (ex: "Fome").
    attribute_value: int# Valor atual do atributo.

class CharacterAttributeCreate(CharacterAttributeBase):
    """
    Schema para criar um novo atributo. Herda do Base.
    """
    pass

class CharacterAttribute(CharacterAttributeBase):
    """
    Schema completo para representar um atributo ao ser lido do banco de dados.
    """
    id: int # ID único do registro do atributo.

    class Config:
        from_attributes = True

# --- Schemas para CharacterInventory (Inventário de Personagem) ---

class CharacterInventoryBase(BaseModel):
    """

    Schema base para um item no inventário de um personagem.
    """
    character_id: int     # ID do personagem dono do inventário.
    resource_type_id: int # ID do tipo de recurso (ex: ID para "Madeira", "Comida").
    quantity: int         # Quantidade desse recurso que o personagem possui.

class CharacterInventoryCreate(CharacterInventoryBase):
    """
    Schema para adicionar um novo item/recurso ao inventário de um personagem.
    """
    pass

class CharacterInventory(CharacterInventoryBase):
    """
    Schema completo para representar um item de inventário lido do banco de dados.
    """
    id: int # ID único da entrada do inventário no banco de dados.

    class Config:
        from_attributes = True
