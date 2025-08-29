from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# --- Schemas para World (Mundo) ---
# Define a estrutura do ambiente onde a simulação ocorre.

class WorldBase(BaseModel):
    """
    Schema base para um Mundo. Contém as propriedades essenciais
    que definem as características de um mundo.
    """
    name: str                   # O nome do mundo (ex: "Eldoria", "Vale Perdido").
    map_width: int              # A largura do mapa do mundo em unidades.
    map_height: int             # A altura do mapa do mundo em unidades.
    
    # --- Atributos de Estado Global ---
    current_time_of_day: str = "Dia" # O período atual do dia (ex: "Dia", "Noite"), que pode afetar o comportamento.
    global_event: Optional[str] = None # Um evento global ativo que pode afetar todo o mundo (ex: "Chuva Ácida", "Superlua"). Opcional.

class WorldCreate(WorldBase):
    """
    Schema para validar os dados ao criar um novo mundo. Herda do Base.
    """
    pass

class WorldUpdate(BaseModel):
    """
    Schema para atualizar o estado de um mundo, geralmente a cada tick da simulação.
    Todos os campos são opcionais, permitindo atualizações parciais (PATCH).
    """
    current_tick: Optional[int] = None      # O número do "passo" ou "turno" atual da simulação.
    current_time_of_day: Optional[str] = None
    global_event: Optional[str] = None

class World(WorldBase):
    """
    Schema completo para representar um mundo, geralmente usado em respostas da API.
    """
    id: int                     # O ID único do mundo no banco de dados.
    current_tick: int           # O "passo" ou "turno" atual da simulação.
    created_at: datetime        # A data e hora em que o mundo foi criado.

    class Config:
        """
        Configuração do Pydantic para habilitar a criação do schema a partir de um modelo ORM.
        """
        from_attributes = True


# --- Schemas para EventsLog (Registro de Eventos) ---
# Define a estrutura para registrar os acontecimentos importantes na simulação.

class EventLogBase(BaseModel):
    """
    Schema base para uma entrada no registro de eventos.
    Captura as informações essenciais sobre um acontecimento.
    """
    event_type: str             # O tipo de evento (ex: "MORTE", "NASCIMENTO", "ATAQUE", "ALIANCA_FORMADA").
    description: str            # Uma descrição textual e legível do que aconteceu.
    
    # --- IDs para Contexto ---
    # Os campos a seguir são opcionais e servem para associar o evento a
    # entidades específicas, fornecendo um contexto detalhado.
    primary_char_id: Optional[int] = None   # ID do personagem principal do evento (ex: quem morreu, quem nasceu).
    secondary_char_id: Optional[int] = None # ID do personagem secundário (ex: quem matou, o pai/mãe).
    clan_a_id: Optional[int] = None         # ID de um clã envolvido (ex: em uma declaração de guerra).
    clan_b_id: Optional[int] = None         # ID do segundo clã envolvido.

class EventLogCreate(EventLogBase):
    """
    Schema para validar os dados ao criar uma nova entrada de log.
    """
    pass

class EventLog(EventLogBase):
    """
    Schema completo para representar uma entrada de log lida do banco de dados.
    """
    id: int                     # O ID único do registro do evento.
    timestamp: datetime         # A data e hora exata em que o evento foi registrado.

    class Config:
        """
        Permite que o schema seja populado a partir de um objeto de banco de dados.
        """
        from_attributes = True
