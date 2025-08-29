from pydantic import BaseModel
from typing import Optional

# Estes schemas definem a estrutura de dados para a entidade 'Character' (Personagem).
# Eles são usados pelo FastAPI para validar dados de entrada em requisições (POST, PUT, PATCH),
# formatar dados de saída em respostas (GET) e gerar a documentação automática da API.

class CharacterBase(BaseModel):
    """
    Schema base para um Personagem. Contém todos os campos comuns que são
    necessários tanto para criar um novo personagem quanto para exibi-lo.
    """
    # --- Atributos Fundamentais ---
    name: str                   # O nome do personagem.
    species_id: int             # Chave estrangeira para a espécie do personagem (ex: Humano, Zumbi).
    clan_id: Optional[int] = None # Chave estrangeira para o clã ao qual o personagem pertence. Opcional, pois um personagem pode não ter clã.

    # --- Atributos de Estado da Simulação ---
    current_health: int         # A quantidade de vida atual do personagem.
    position_x: float           # A coordenada X da posição atual do personagem no mapa.
    position_y: float           # A coordenada Y da posição atual do personagem no mapa.
    
    # --- Atributos de Comportamento (IA) ---
    current_state: str          # O estado atual da máquina de estados da IA (ex: "VAGUEANDO", "ATACANDO", "COLETANDO").
    target_character_id: Optional[int] = None # O ID do personagem alvo, se houver (ex: o inimigo que está sendo atacado). Opcional.

class CharacterCreate(CharacterBase):
    """
    Schema usado especificamente para criar um novo personagem (ex: em uma requisição POST).
    Ele herda todos os campos do 'CharacterBase'. Manter esta classe separada, mesmo
    que vazia, é uma boa prática para permitir futuras customizações no processo de criação.
    """
    pass

class CharacterUpdate(BaseModel):
    """
    Schema para atualizar um personagem existente (ex: em uma requisição PATCH).
    Todos os campos são definidos como 'Optional'. Isso é crucial porque permite
    que o cliente da API envie apenas os campos que deseja alterar, sem precisar
    fornecer o objeto de personagem inteiro.
    """
    name: Optional[str] = None
    clan_id: Optional[int] = None
    current_health: Optional[int] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    current_state: Optional[str] = None
    target_character_id: Optional[int] = None

class Character(CharacterBase):
    """
    Schema completo para representar um personagem, tipicamente para ser retornado
    em respostas da API (ex: em uma requisição GET).
    Ele herda os campos do 'CharacterBase' e adiciona campos que são gerados
    automaticamente pelo banco de dados, como o 'id'.
    """
    id: int # O ID único do personagem, gerado pelo banco de dados.

    class Config:
        """
        Configurações internas do modelo Pydantic.
        """
        # 'from_attributes = True' permite que este modelo Pydantic seja preenchido
        # diretamente a partir de um objeto de modelo SQLAlchemy. Ele mapeia os
        # atributos do objeto ORM para os campos deste schema, facilitando a
        # conversão de dados do banco de dados para uma resposta de API.
        from_attributes = True
