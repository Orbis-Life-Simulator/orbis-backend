from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Float, Text, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Tabela 9: World (Mundo/Simulação) - Adicionada como a base de tudo
class World(Base):
    __tablename__ = "worlds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    map_width = Column(Integer, default=1000)
    map_height = Column(Integer, default=1000)
    current_tick = Column(Integer, default=0)
    current_time_of_day = Column(String, default="DAY")
    global_event = Column(String, default="NONE")
    created_at = Column(DateTime, nullable=False)

    # Relacionamentos: um mundo contém múltiplos clãs, personagens, territórios, etc.
    clans = relationship("Clan", back_populates="world")
    characters = relationship("Character", back_populates="world")
    territories = relationship("Territory", back_populates="world")
    missions = relationship("Mission", back_populates="world")

# Tabela 1: Species (Espécies)
class Species(Base):
    __tablename__ = "species"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    base_health = Column(Integer, nullable=False)
    base_strength = Column(Integer, nullable=False)

    characters = relationship("Character", back_populates="species")

# Tabela 2: Clans (Clãs)
class Clan(Base):
    __tablename__ = "clans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    species_id = Column(Integer, ForeignKey("species.id"), nullable=False)
    
    # MODIFICAÇÃO: Adicionada a referência ao mundo
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False)

    world = relationship("World", back_populates="clans")
    species = relationship("Species")
    characters = relationship("Character", back_populates="clan")

# Tabela 3: Characters (Personagens)
class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    species_id = Column(Integer, ForeignKey("species.id"), nullable=False)
    clan_id = Column(Integer, ForeignKey("clans.id"), nullable=True)
    
    # MODIFICAÇÃO: Adicionada a referência ao mundo
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False)

    current_health = Column(Integer, nullable=False)
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)
    current_state = Column(String, default="VAGANDO")

    world = relationship("World", back_populates="characters")
    species = relationship("Species", back_populates="characters")
    clan = relationship("Clan", back_populates="characters")
    
    # Relacionamentos para tabelas de atributos, inventário e relações
    attributes = relationship("CharacterAttribute", back_populates="character", cascade="all, delete-orphan")
    inventory = relationship("CharacterInventory", back_populates="character", cascade="all, delete-orphan")
    relationships_as_a = relationship("CharacterRelationship", foreign_keys="[CharacterRelationship.character_a_id]", back_populates="character_a")
    relationships_as_b = relationship("CharacterRelationship", foreign_keys="[CharacterRelationship.character_b_id]", back_populates="character_b")

# Tabela 4: SpeciesRelationships (Relações entre Espécies)
class SpeciesRelationship(Base):
    __tablename__ = "species_relationships"

    id = Column(Integer, primary_key=True, index=True)
    species_a_id = Column(Integer, ForeignKey("species.id"), nullable=False)
    species_b_id = Column(Integer, ForeignKey("species.id"), nullable=False)
    relationship = Column(String, nullable=False)  # FRIEND, ENEMY, INDIFFERENT

    species_a = relationship("Species", foreign_keys=[species_a_id])
    species_b = relationship("Species", foreign_keys=[species_b_id])

# Tabela 5: ClanRelationships (Relações entre Clãs)
class ClanRelationship(Base):
    __tablename__ = "clan_relationships"

    id = Column(Integer, primary_key=True, index=True)
    clan_a_id = Column(Integer, ForeignKey("clans.id"), nullable=False)
    clan_b_id = Column(Integer, ForeignKey("clans.id"), nullable=False)
    relationship = Column(String, nullable=False)  # WAR, ALLIANCE, NEUTRAL

    clan_a = relationship("Clan", foreign_keys=[clan_a_id])
    clan_b = relationship("Clan", foreign_keys=[clan_b_id])

# Tabela 6: EventsLog (Log de Eventos)
class EventLog(Base):
    __tablename__ = "events_log"

    id = Column(Integer, primary_key=True, index=True)
    # MODIFICAÇÃO: Adicionada a referência ao mundo
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String, nullable=False)
    description = Column(Text)
    primary_char_id = Column(Integer, ForeignKey("characters.id"), nullable=True)
    secondary_char_id = Column(Integer, ForeignKey("characters.id"), nullable=True)
    clan_a_id = Column(Integer, ForeignKey("clans.id"), nullable=True)
    clan_b_id = Column(Integer, ForeignKey("clans.id"), nullable=True)

# Tabela 7: CharacterRelationships (Relações entre Personagens)
class CharacterRelationship(Base):
    __tablename__ = "character_relationships"

    id = Column(Integer, primary_key=True, index=True)
    character_a_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    character_b_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    relationship_score = Column(Float, default=0.0)
    last_interaction = Column(DateTime)

    character_a = relationship("Character", foreign_keys=[character_a_id], back_populates="relationships_as_a")
    character_b = relationship("Character", foreign_keys=[character_b_id], back_populates="relationships_as_b")

# Tabela 8: CharacterAttributes (Atributos de Personagem)
class CharacterAttribute(Base):
    __tablename__ = "character_attributes"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    attribute_name = Column(String, nullable=False)
    attribute_value = Column(Integer, default=0)

    character = relationship("Character", back_populates="attributes")

# Tabela 10: ResourceTypes (Tipos de Recurso) - NOVO
class ResourceType(Base):
    __tablename__ = "resource_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)
    base_value = Column(Integer, default=1)

# Tabela 11: CharacterInventory (Inventário de Personagem) - NOVO
class CharacterInventory(Base):
    __tablename__ = "character_inventory"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    resource_type_id = Column(Integer, ForeignKey("resource_types.id"), nullable=False)
    quantity = Column(Integer, default=0)

    character = relationship("Character", back_populates="inventory")
    resource_type = relationship("ResourceType")

# Tabela 12: Territories (Territórios) - NOVO
class Territory(Base):
    __tablename__ = "territories"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False)
    name = Column(String, nullable=False)
    owner_clan_id = Column(Integer, ForeignKey("clans.id"), nullable=True)
    
    # CORREÇÃO: Coordenadas divididas em 4 colunas
    start_x = Column(Float, nullable=False)
    end_x = Column(Float, nullable=False)
    start_y = Column(Float, nullable=False)
    end_y = Column(Float, nullable=False)

    world = relationship("World", back_populates="territories")
    owner_clan = relationship("Clan")
    resources = relationship("TerritoryResource", back_populates="territory")

# Tabela 13: TerritoryResources (Recursos de Território) - NOVO
class TerritoryResource(Base):
    __tablename__ = "territory_resources"
    
    id = Column(Integer, primary_key=True, index=True)
    territory_id = Column(Integer, ForeignKey("territories.id"), nullable=False)
    resource_type_id = Column(Integer, ForeignKey("resource_types.id"), nullable=False)
    abundance = Column(Float, default=1.0)

    territory = relationship("Territory", back_populates="resources")
    resource_type = relationship("ResourceType")

# Tabela 14: Missions (Missões) - NOVO
class Mission(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False)
    title = Column(String, nullable=False)
    assignee_clan_id = Column(Integer, ForeignKey("clans.id"), nullable=True)
    status = Column(String, default="ATIVA") # ATIVA, CONCLUÍDA, FALHOU
    created_at = Column(DateTime, nullable=False)

    world = relationship("World", back_populates="missions")
    assignee_clan = relationship("Clan")
    objectives = relationship("MissionObjective", back_populates="mission", cascade="all, delete-orphan")

# Tabela 15: MissionObjectives (Objetivos de Missão) - NOVO
class MissionObjective(Base):
    __tablename__ = "mission_objectives"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False)
    objective_type = Column(String, nullable=False) # GATHER_RESOURCE, CONQUER_TERRITORY, DEFEAT_CHARACTER
    target_resource_id = Column(Integer, ForeignKey("resource_types.id"), nullable=True)
    target_territory_id = Column(Integer, ForeignKey("territories.id"), nullable=True)
    target_quantity = Column(Integer, default=1)
    is_complete = Column(Boolean, default=False)
    
    mission = relationship("Mission", back_populates="objectives")