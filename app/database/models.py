# Importa 'func' para usar funções SQL como NOW() que são executadas pelo servidor do banco de dados.
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base  # Base declarativa que nossos modelos herdarão.


# Tabela 9: World (Mundo/Simulação)
class World(Base):
    """
    Representa a instância principal de uma simulação, o "palco" onde tudo acontece.
    Contém o estado global e serve como o contêiner para todos os outros elementos.
    """

    __tablename__ = "worlds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)  # Nome único para cada mundo.
    map_width = Column(Integer, default=1000)  # Largura do mapa em unidades.
    map_height = Column(Integer, default=1000)  # Altura do mapa em unidades.
    current_tick = Column(
        Integer, default=0
    )  # O "turno" ou "passo" atual da simulação.
    current_time_of_day = Column(String, default="DAY")  # Estado do ciclo dia/noite.
    global_event = Column(
        String, default="NONE"
    )  # Evento global ativo que pode afetar a simulação.
    created_at = Column(
        DateTime, server_default=func.now()
    )  # Timestamp de quando o mundo foi criado.

    # Relacionamentos One-to-Many: Um mundo tem muitos clãs, personagens, etc.
    # 'cascade="all, delete-orphan"' significa que quando um World é deletado,
    # todos os seus clãs, personagens, etc., associados também são deletados.
    clans = relationship("Clan", back_populates="world", cascade="all, delete-orphan")
    characters = relationship(
        "Character", back_populates="world", cascade="all, delete-orphan"
    )
    territories = relationship(
        "Territory", back_populates="world", cascade="all, delete-orphan"
    )
    missions = relationship(
        "Mission", back_populates="world", cascade="all, delete-orphan"
    )
    events = relationship(
        "EventLog", back_populates="world", cascade="all, delete-orphan"
    )


# Tabela 1: Species (Espécies)
class Species(Base):
    """
    Define um "template" ou "blueprint" para os personagens (ex: Humano, Orc, Elfo).
    Contém os atributos base que todos os membros de uma espécie compartilham.
    """

    __tablename__ = "species"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    base_health = Column(Integer, nullable=False)  # Pontos de vida iniciais.
    base_strength = Column(Integer, nullable=False)  # Força de ataque base.

    # Relacionamentos
    characters = relationship("Character", back_populates="species")

    # Relacionamentos de uma espécie com outras. Como uma espécie pode estar em
    # qualquer um dos lados da relação, precisamos de dois 'relationships' para
    # capturar todos os casos e evitar ambiguidades no SQLAlchemy.
    relationships_as_a = relationship(
        "SpeciesRelationship",
        foreign_keys="[SpeciesRelationship.species_a_id]",
        back_populates="species_a",
    )
    relationships_as_b = relationship(
        "SpeciesRelationship",
        foreign_keys="[SpeciesRelationship.species_b_id]",
        back_populates="species_b",
    )


# Tabela 2: Clans (Clãs)
class Clan(Base):
    """
    Representa uma facção, tribo ou grupo social de personagens.
    """

    __tablename__ = "clans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    species_id = Column(
        Integer, ForeignKey("species.id"), nullable=False, index=True
    )  # Espécie dominante do clã.
    world_id = Column(
        Integer, ForeignKey("worlds.id"), nullable=False, index=True
    )  # Mundo ao qual o clã pertence.

    # Relacionamentos Many-to-One
    world = relationship("World", back_populates="clans")
    species = relationship("Species")

    # Relacionamento One-to-Many
    characters = relationship("Character", back_populates="clan")

    # Semelhante a Species, define as relações diplomáticas com outros clãs.
    relationships_as_a = relationship(
        "ClanRelationship",
        foreign_keys="[ClanRelationship.clan_a_id]",
        back_populates="clan_a",
    )
    relationships_as_b = relationship(
        "ClanRelationship",
        foreign_keys="[ClanRelationship.clan_b_id]",
        back_populates="clan_b",
    )


# Tabela 3: Characters (Personagens)
class Character(Base):
    """
    A principal entidade "agente" da simulação. Um indivíduo que age no mundo.
    """

    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    species_id = Column(Integer, ForeignKey("species.id"), nullable=False, index=True)
    clan_id = Column(
        Integer, ForeignKey("clans.id"), nullable=True, index=True
    )  # Pode não ter um clã.
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    current_health = Column(Integer, nullable=False)  # Vida atual.
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)
    current_state = Column(
        String, default="VAGANDO"
    )  # Estado atual da IA (ex: ATACANDO, FUGINDO).
    target_character_id = Column(
        Integer, ForeignKey("characters.id"), nullable=True
    )  # Alvo atual (auto-referência).

    # Relacionamentos
    world = relationship("World", back_populates="characters")
    species = relationship("Species", back_populates="characters")
    clan = relationship("Clan", back_populates="characters")
    attributes = relationship(
        "CharacterAttribute", back_populates="character", cascade="all, delete-orphan"
    )
    inventory = relationship(
        "CharacterInventory", back_populates="character", cascade="all, delete-orphan"
    )
    relationships_as_a = relationship(
        "CharacterRelationship",
        foreign_keys="CharacterRelationship.character_a_id",
        back_populates="character_a",
    )
    relationships_as_b = relationship(
        "CharacterRelationship",
        foreign_keys="CharacterRelationship.character_b_id",
        back_populates="character_b",
    )


# Tabela 4: SpeciesRelationships (Tabela de Junção)
class SpeciesRelationship(Base):
    """
    Define a relação padrão (inata) entre duas espécies. (Ex: Predador/Presa, Amigável).
    """

    __tablename__ = "species_relationships"

    id = Column(Integer, primary_key=True, index=True)
    species_a_id = Column(Integer, ForeignKey("species.id"), nullable=False)
    species_b_id = Column(Integer, ForeignKey("species.id"), nullable=False)
    relationship_type = Column(
        String, nullable=False
    )  # Ex: "ENEMY", "FRIEND", "INDIFFERENT"

    # Links de volta para os objetos Species
    species_a = relationship(
        "Species", foreign_keys=[species_a_id], back_populates="relationships_as_a"
    )
    species_b = relationship(
        "Species", foreign_keys=[species_b_id], back_populates="relationships_as_b"
    )


# Tabela 5: ClanRelationships (Tabela de Junção)
class ClanRelationship(Base):
    """
    Define a relação diplomática entre dois clãs (Ex: Guerra, Aliança).
    Esta relação sobrepõe a relação de espécie.
    """

    __tablename__ = "clan_relationships"

    id = Column(Integer, primary_key=True, index=True)
    clan_a_id = Column(Integer, ForeignKey("clans.id"), nullable=False)
    clan_b_id = Column(Integer, ForeignKey("clans.id"), nullable=False)
    relationship_type = Column(
        String, nullable=False
    )  # Ex: "WAR", "ALLIANCE", "NEUTRAL"

    clan_a = relationship(
        "Clan", foreign_keys=[clan_a_id], back_populates="relationships_as_a"
    )
    clan_b = relationship(
        "Clan", foreign_keys=[clan_b_id], back_populates="relationships_as_b"
    )


# Tabela 6: EventsLog
class EventLog(Base):
    """
    Registra eventos significativos que ocorrem na simulação, formando a "história" do mundo.
    """

    __tablename__ = "events_log"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    timestamp = Column(DateTime, server_default=func.now())  # Quando o evento ocorreu.
    event_type = Column(String, nullable=False)  # Ex: "MORTE", "NASCIMENTO", "ATAQUE".
    description = Column(Text)  # Descrição legível do evento.

    # IDs opcionais para dar contexto ao evento.
    primary_char_id = Column(
        Integer, ForeignKey("characters.id"), nullable=True
    )  # Personagem principal do evento.
    secondary_char_id = Column(
        Integer, ForeignKey("characters.id"), nullable=True
    )  # Personagem secundário.
    clan_a_id = Column(Integer, ForeignKey("clans.id"), nullable=True)
    clan_b_id = Column(Integer, ForeignKey("clans.id"), nullable=True)

    world = relationship("World", back_populates="events")


# Tabela 7: CharacterRelationships (Tabela de Junção)
class CharacterRelationship(Base):
    """
    Define uma relação pessoal entre dois personagens específicos, que evolui com interações.
    """

    __tablename__ = "character_relationships"

    id = Column(Integer, primary_key=True, index=True)
    character_a_id = Column(
        Integer, ForeignKey("characters.id"), nullable=False, index=True
    )
    character_b_id = Column(
        Integer, ForeignKey("characters.id"), nullable=False, index=True
    )
    relationship_score = Column(
        Float, default=0.0
    )  # Pontuação que mede a relação (ex: -100 a 100).
    last_interaction = Column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )  # Atualiza a cada interação.

    character_a = relationship(
        "Character", foreign_keys=[character_a_id], back_populates="relationships_as_a"
    )
    character_b = relationship(
        "Character", foreign_keys=[character_b_id], back_populates="relationships_as_b"
    )


# Tabela 8: CharacterAttributes
class CharacterAttribute(Base):
    """
    Armazena atributos dinâmicos de um personagem (Ex: "Fome", "Energia") no formato chave-valor.
    """

    __tablename__ = "character_attributes"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(
        Integer, ForeignKey("characters.id"), nullable=False, index=True
    )
    attribute_name = Column(String, nullable=False)  # Ex: "Fome".
    attribute_value = Column(Integer, default=0)  # Valor do atributo.
    character = relationship("Character", back_populates="attributes")


# Tabela 10: ResourceTypes
class ResourceType(Base):
    """
    Define um "template" para um tipo de recurso (Ex: Madeira, Pedra, Fruta).
    """

    __tablename__ = "resource_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)  # Ex: "COMIDA", "MATERIAL_CONSTRUCAO".
    base_value = Column(Integer, default=1)  # Valor para comércio ou pontuação.


# Tabela 11: CharacterInventory
class CharacterInventory(Base):
    """
    Tabela de junção que representa o inventário de um personagem.
    """

    __tablename__ = "character_inventory"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(
        Integer, ForeignKey("characters.id"), nullable=False, index=True
    )
    resource_type_id = Column(
        Integer, ForeignKey("resource_types.id"), nullable=False, index=True
    )
    quantity = Column(Integer, default=0)
    character = relationship("Character", back_populates="inventory")
    resource_type = relationship("ResourceType")


# Tabela 12: Territories
class Territory(Base):
    """
    Define uma área geográfica nomeada no mapa, que pode ser controlada por clãs.
    """

    __tablename__ = "territories"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    owner_clan_id = Column(
        Integer, ForeignKey("clans.id"), nullable=True, index=True
    )  # Clã que controla o território.
    # Coordenadas que definem a área retangular do território.
    start_x = Column(Float, nullable=False)
    end_x = Column(Float, nullable=False)
    start_y = Column(Float, nullable=False)
    end_y = Column(Float, nullable=False)

    world = relationship("World", back_populates="territories")
    owner_clan = relationship("Clan")
    resource_nodes = relationship(
        "ResourceNode", back_populates="territory", cascade="all, delete-orphan"
    )


# Tabela 13: ResourceNode
class ResourceNode(Base):
    """
    Representa uma instância física e coletável de um recurso no mapa (ex: uma árvore, uma mina).
    """

    __tablename__ = "resource_nodes"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    resource_type_id = Column(
        Integer, ForeignKey("resource_types.id"), nullable=False, index=True
    )
    position_x = Column(Float, nullable=False)
    position_y = Column(Float, nullable=False)
    quantity = Column(
        Integer, default=10
    )  # Quantidade de recurso que pode ser coletada antes de esgotar.
    is_depleted = Column(
        Boolean, default=False
    )  # Flag que indica se o nó foi esgotado.

    world = relationship("World")
    resource_type = relationship("ResourceType")


# Tabela 14: Missions
class Mission(Base):
    """
    Define uma missão ou objetivo de alto nível para um clã.
    """

    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    assignee_clan_id = Column(
        Integer, ForeignKey("clans.id"), nullable=True, index=True
    )  # Clã que recebeu a missão.
    status = Column(String, default="ATIVA")  # Ex: "ATIVA", "CONCLUÍDA", "FALHOU".
    created_at = Column(DateTime, server_default=func.now())

    world = relationship("World", back_populates="missions")
    assignee_clan = relationship("Clan")
    objectives = relationship(
        "MissionObjective", back_populates="mission", cascade="all, delete-orphan"
    )


# Tabela 15: MissionObjectives
class MissionObjective(Base):
    """
    Define uma tarefa ou passo específico que precisa ser completado para uma missão.
    """

    __tablename__ = "mission_objectives"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False, index=True)
    objective_type = Column(
        String, nullable=False
    )  # Ex: "GATHER_RESOURCE", "CONQUER_TERRITORY".

    # Apenas um dos campos 'target' será preenchido, dependendo do 'objective_type'.
    target_resource_id = Column(Integer, ForeignKey("resource_types.id"), nullable=True)
    target_territory_id = Column(Integer, ForeignKey("territories.id"), nullable=True)
    target_quantity = Column(Integer, default=1)

    is_complete = Column(Boolean, default=False)
    mission = relationship("Mission", back_populates="objectives")
