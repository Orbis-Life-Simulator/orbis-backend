import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as EnumSQL,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class RelationshipTypeEnum(enum.Enum):
    ENEMY = "ENEMY"
    FRIEND = "FRIEND"
    INDIFFERENT = "INDIFFERENT"


class ClanRelationshipTypeEnum(enum.Enum):
    WAR = "WAR"
    ALLIANCE = "ALLIANCE"
    NEUTRAL = "NEUTRAL"


class ObjectiveTypeEnum(enum.Enum):
    GATHER_RESOURCE = "GATHER_RESOURCE"
    CONQUER_TERRITORY = "CONQUER_TERRITORY"
    DEFEAT_CHARACTER = "DEFEAT_CHARACTER"


class World(Base):
    __tablename__ = "worlds"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    map_width = Column(Integer, default=1000)
    map_height = Column(Integer, default=1000)
    current_tick = Column(Integer, default=0)
    current_time_of_day = Column(String, default="DAY")
    global_event = Column(String, default="NONE")
    created_at = Column(DateTime, server_default=func.now())
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


class Species(Base):
    __tablename__ = "species"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    base_health = Column(Integer, nullable=False)
    base_strength = Column(Integer, nullable=False)
    characters = relationship("Character", back_populates="species")
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


class Clan(Base):
    __tablename__ = "clans"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    species_id = Column(Integer, ForeignKey("species.id"), nullable=False, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    world = relationship("World", back_populates="clans")
    species = relationship("Species")
    characters = relationship("Character", back_populates="clan")
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


class Character(Base):
    __tablename__ = "characters"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    species_id = Column(Integer, ForeignKey("species.id"), nullable=False, index=True)
    clan_id = Column(Integer, ForeignKey("clans.id"), nullable=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    current_health = Column(Integer, nullable=False)
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)
    fome = Column(Integer, default=0, nullable=False)
    energia = Column(Integer, default=100, nullable=False)
    idade = Column(Integer, default=0, nullable=False)
    reproduction_progress = Column(Integer, default=0, nullable=False)
    bravura = Column(Integer, default=50, nullable=False)
    cautela = Column(Integer, default=50, nullable=False)
    sociabilidade = Column(Integer, default=50, nullable=False)
    ganancia = Column(Integer, default=50, nullable=False)
    inteligencia = Column(Integer, default=50, nullable=False)
    world = relationship("World", back_populates="characters")
    species = relationship("Species", back_populates="characters")
    clan = relationship("Clan", back_populates="characters")
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


class SpeciesRelationship(Base):
    __tablename__ = "species_relationships"
    id = Column(Integer, primary_key=True, index=True)
    species_a_id = Column(Integer, ForeignKey("species.id"), nullable=False)
    species_b_id = Column(Integer, ForeignKey("species.id"), nullable=False)

    relationship_type = Column(EnumSQL(RelationshipTypeEnum), nullable=False)
    species_a = relationship(
        "Species", foreign_keys=[species_a_id], back_populates="relationships_as_a"
    )
    species_b = relationship(
        "Species", foreign_keys=[species_b_id], back_populates="relationships_as_b"
    )


class ClanRelationship(Base):
    __tablename__ = "clan_relationships"
    id = Column(Integer, primary_key=True, index=True)
    clan_a_id = Column(Integer, ForeignKey("clans.id"), nullable=False)
    clan_b_id = Column(Integer, ForeignKey("clans.id"), nullable=False)

    relationship_type = Column(EnumSQL(ClanRelationshipTypeEnum), nullable=False)
    clan_a = relationship(
        "Clan", foreign_keys=[clan_a_id], back_populates="relationships_as_a"
    )
    clan_b = relationship(
        "Clan", foreign_keys=[clan_b_id], back_populates="relationships_as_b"
    )


class EventLog(Base):
    __tablename__ = "events_log"
    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    timestamp = Column(DateTime, server_default=func.now())
    event_type = Column(String, nullable=False)
    description = Column(Text)
    primary_char_id = Column(Integer, ForeignKey("characters.id"), nullable=True)
    secondary_char_id = Column(Integer, ForeignKey("characters.id"), nullable=True)
    clan_a_id = Column(Integer, ForeignKey("clans.id"), nullable=True)
    clan_b_id = Column(Integer, ForeignKey("clans.id"), nullable=True)
    world = relationship("World", back_populates="events")


class CharacterRelationship(Base):
    __tablename__ = "character_relationships"
    id = Column(Integer, primary_key=True, index=True)
    character_a_id = Column(
        Integer, ForeignKey("characters.id"), nullable=False, index=True
    )
    character_b_id = Column(
        Integer, ForeignKey("characters.id"), nullable=False, index=True
    )
    relationship_score = Column(Float, default=0.0)
    last_interaction = Column(DateTime, server_default=func.now(), onupdate=func.now())
    character_a = relationship(
        "Character", foreign_keys=[character_a_id], back_populates="relationships_as_a"
    )
    character_b = relationship(
        "Character", foreign_keys=[character_b_id], back_populates="relationships_as_b"
    )


class ResourceType(Base):
    __tablename__ = "resource_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)
    base_value = Column(Integer, default=1)


class CharacterInventory(Base):
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


class Territory(Base):
    __tablename__ = "territories"
    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    owner_clan_id = Column(Integer, ForeignKey("clans.id"), nullable=True, index=True)
    start_x = Column(Float, nullable=False)
    end_x = Column(Float, nullable=False)
    start_y = Column(Float, nullable=False)
    end_y = Column(Float, nullable=False)
    world = relationship("World", back_populates="territories")
    owner_clan = relationship("Clan")
    resource_nodes = relationship(
        "ResourceNode", back_populates="territory", cascade="all, delete-orphan"
    )


class ResourceNode(Base):
    __tablename__ = "resource_nodes"
    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    resource_type_id = Column(
        Integer, ForeignKey("resource_types.id"), nullable=False, index=True
    )
    territory_id = Column(Integer, ForeignKey("territories.id"), nullable=True)
    position_x = Column(Float, nullable=False)
    position_y = Column(Float, nullable=False)
    quantity = Column(Integer, default=10)
    is_depleted = Column(Boolean, default=False)
    world = relationship("World")
    resource_type = relationship("ResourceType")
    territory = relationship("Territory", back_populates="resource_nodes")


class Mission(Base):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    assignee_clan_id = Column(
        Integer, ForeignKey("clans.id"), nullable=True, index=True
    )
    status = Column(String, default="ATIVA")
    created_at = Column(DateTime, server_default=func.now())
    world = relationship("World", back_populates="missions")
    assignee_clan = relationship("Clan")
    objectives = relationship(
        "MissionObjective", back_populates="mission", cascade="all, delete-orphan"
    )


class MissionObjective(Base):
    __tablename__ = "mission_objectives"
    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False, index=True)
    objective_type = Column(EnumSQL(ObjectiveTypeEnum), nullable=False)
    target_resource_id = Column(Integer, ForeignKey("resource_types.id"), nullable=True)
    target_territory_id = Column(Integer, ForeignKey("territories.id"), nullable=True)
    target_quantity = Column(Integer, default=1)
    is_complete = Column(Boolean, default=False)
    mission = relationship("Mission", back_populates="objectives")
