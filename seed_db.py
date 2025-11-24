# # seed.py

# import sys, os, random
# from sqlalchemy.orm import Session

# # --- Configuração de Path ---
# # Garante que o script possa encontrar e importar módulos da pasta 'app'.
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# # --- Importações da Aplicação ---
# from app.database.database import engine, SessionLocal, Base
# from app.database import models

# # ATUALIZADO: Importa os Enums para garantir a integridade dos dados.
# from app.database.models import (
#     RelationshipTypeEnum,
#     ClanRelationshipTypeEnum,
#     ObjectiveTypeEnum,
# )

# print("Iniciando o Construtor de Cenários AVANÇADO para o Mundo de Orbis...")

# # --- Reset e Criação do Banco de Dados ---
# Base.metadata.drop_all(bind=engine)
# Base.metadata.create_all(bind=engine)

# db: Session = SessionLocal()

# try:
#     # --- 1. MUNDO, ESPÉCIES, RELAÇÕES E RECURSOS (BASE SÓLIDA) ---
#     print("Estabelecendo as fundações do mundo...")
#     world = models.World(name="Mundo Padrão", map_width=1000, map_height=1000)
#     db.add(world)
#     db.flush()

#     species_data = [
#         {"name": "Anão", "base_health": 120, "base_strength": 15},
#         {"name": "Humano", "base_health": 100, "base_strength": 10},
#         {"name": "Elfo", "base_health": 80, "base_strength": 12},
#         {"name": "Fada", "base_health": 60, "base_strength": 8},
#         {"name": "Goblin", "base_health": 70, "base_strength": 7},
#         {"name": "Orc", "base_health": 150, "base_strength": 18},
#         {"name": "Troll", "base_health": 200, "base_strength": 25},
#         {"name": "Zumbi", "base_health": 100, "base_strength": 10},
#     ]
#     species_map = {data["name"]: models.Species(**data) for data in species_data}
#     db.add_all(species_map.values())
#     db.flush()

#     relationships = [
#         ("Anão", "Humano", RelationshipTypeEnum.FRIEND),
#         ("Anão", "Elfo", RelationshipTypeEnum.ENEMY),
#         ("Anão", "Fada", RelationshipTypeEnum.ENEMY),
#         ("Anão", "Orc", RelationshipTypeEnum.ENEMY),
#         ("Anão", "Goblin", RelationshipTypeEnum.ENEMY),
#         ("Anão", "Troll", RelationshipTypeEnum.ENEMY),
#         ("Humano", "Elfo", RelationshipTypeEnum.FRIEND),
#         ("Humano", "Fada", RelationshipTypeEnum.FRIEND),
#         ("Humano", "Orc", RelationshipTypeEnum.ENEMY),
#         ("Humano", "Troll", RelationshipTypeEnum.ENEMY),
#         ("Humano", "Goblin", RelationshipTypeEnum.ENEMY),
#         ("Fada", "Elfo", RelationshipTypeEnum.INDIFFERENT),
#         ("Fada", "Troll", RelationshipTypeEnum.ENEMY),
#         ("Fada", "Orc", RelationshipTypeEnum.ENEMY),
#         ("Fada", "Goblin", RelationshipTypeEnum.ENEMY),
#         ("Elfo", "Orc", RelationshipTypeEnum.ENEMY),
#         ("Elfo", "Troll", RelationshipTypeEnum.ENEMY),
#         ("Elfo", "Goblin", RelationshipTypeEnum.ENEMY),
#         ("Orc", "Troll", RelationshipTypeEnum.FRIEND),
#         ("Orc", "Goblin", RelationshipTypeEnum.FRIEND),
#         ("Goblin", "Troll", RelationshipTypeEnum.FRIEND),
#     ]
#     for r in relationships:
#         db.add(
#             models.SpeciesRelationship(
#                 species_a_id=species_map[r[0]].id,
#                 species_b_id=species_map[r[1]].id,
#                 relationship_type=r[2],
#             )
#         )

#     resource_data = [
#         {"name": "Peixe", "category": "COMIDA", "base_value": 5},
#         {"name": "Baga Silvestre", "category": "COMIDA", "base_value": 3},
#         {"name": "Minério de Ferro", "category": "MATERIAL", "base_value": 10},
#         {"name": "Madeira", "category": "MATERIAL", "base_value": 2},
#         {"name": "Pedra", "category": "MATERIAL", "base_value": 4},
#     ]
#     resource_map = {data["name"]: models.ResourceType(**data) for data in resource_data}
#     db.add_all(resource_map.values())
#     db.flush()

#     # --- 2. TERRITÓRIOS E NÓS DE RECURSOS (MUNDO RICO) ---
#     print("Distribuindo recursos e definindo territórios...")
#     territories_data = [
#         {
#             "name": "Valmor (Capital Humana)",
#             "start_x": 350,
#             "end_x": 650,
#             "start_y": 350,
#             "end_y": 650,
#         },
#         {
#             "name": "Minas de Durvak",
#             "start_x": 0,
#             "end_x": 250,
#             "start_y": 0,
#             "end_y": 250,
#         },
#         {
#             "name": "Floresta de Aetherion",
#             "start_x": 750,
#             "end_x": 1000,
#             "start_y": 650,
#             "end_y": 900,
#         },
#         {
#             "name": "Pântano de Snagûl",
#             "start_x": 0,
#             "end_x": 300,
#             "start_y": 700,
#             "end_y": 1000,
#         },
#         {
#             "name": "Cemitério Assombrado",
#             "start_x": 750,
#             "end_x": 1000,
#             "start_y": 0,
#             "end_y": 250,
#         },
#         {
#             "name": "Lago Elyndor",
#             "start_x": 300,
#             "end_x": 700,
#             "start_y": 0,
#             "end_y": 300,
#         },
#         {
#             "name": "Colinas Rochosas",
#             "start_x": 0,
#             "end_x": 300,
#             "start_y": 300,
#             "end_y": 650,
#         },
#         {
#             "name": "Bosque Antigo",
#             "start_x": 700,
#             "end_x": 1000,
#             "start_y": 300,
#             "end_y": 600,
#         },
#         {
#             "name": "Planícies Centrais",
#             "start_x": 300,
#             "end_x": 700,
#             "start_y": 700,
#             "end_y": 1000,
#         },
#     ]
#     territory_map = {
#         data["name"]: models.Territory(world_id=world.id, **data)
#         for data in territories_data
#     }
#     db.add_all(territory_map.values())
#     db.flush()

#     resource_nodes_to_create = [
#         ("Valmor (Capital Humana)", "Baga Silvestre", 5, 20),
#         ("Valmor (Capital Humana)", "Pedra", 8, 15),
#         ("Minas de Durvak", "Minério de Ferro", 10, 30),
#         ("Minas de Durvak", "Pedra", 15, 20),
#         ("Floresta de Aetherion", "Madeira", 15, 15),
#         ("Floresta de Aetherion", "Baga Silvestre", 8, 20),
#         ("Lago Elyndor", "Peixe", 12, 25),
#         ("Colinas Rochosas", "Baga Silvestre", 10, 15),
#         ("Colinas Rochosas", "Minério de Ferro", 3, 10),
#         ("Bosque Antigo", "Madeira", 20, 10),
#         ("Bosque Antigo", "Baga Silvestre", 5, 15),
#         ("Planícies Centrais", "Baga Silvestre", 15, 10),
#     ]
#     for terr_name, res_name, count, avg_qty in resource_nodes_to_create:
#         territory = territory_map[terr_name]
#         resource = resource_map[res_name]
#         for _ in range(count):
#             db.add(
#                 models.ResourceNode(
#                     world_id=world.id,
#                     resource_type_id=resource.id,
#                     territory_id=territory.id,
#                     position_x=random.uniform(territory.start_x, territory.end_x),
#                     position_y=random.uniform(territory.start_y, territory.end_y),
#                     quantity=random.randint(int(avg_qty * 0.5), int(avg_qty * 1.5)),
#                 )
#             )

#     # --- 3. CLÃS E PERSONAGENS (VIDA INICIAL) ---
#     print("Povoando o mundo com clãs e personagens...")
#     clans_data = [
#         {
#             "name": "Reino de Valmor",
#             "species_name": "Humano",
#             "home_territory_name": "Valmor (Capital Humana)",
#         },
#         {
#             "name": "Clã Martelo de Ferro",
#             "species_name": "Anão",
#             "home_territory_name": "Minas de Durvak",
#         },
#         {
#             "name": "Corte de Aetherion",
#             "species_name": "Elfo",
#             "home_territory_name": "Floresta de Aetherion",
#         },
#         {
#             "name": "Enxame de Elyndor",
#             "species_name": "Fada",
#             "home_territory_name": "Lago Elyndor",
#         },
#         {
#             "name": "Legião Dente Afiado",
#             "species_name": "Orc",
#             "home_territory_name": "Pântano de Snagûl",
#         },
#         {
#             "name": "Clã Esmaga-Ossos",
#             "species_name": "Troll",
#             "home_territory_name": "Pântano de Snagûl",
#         },
#         {
#             "name": "A Horda Rastejante",
#             "species_name": "Zumbi",
#             "home_territory_name": "Cemitério Assombrado",
#         },
#     ]
#     clan_map = {}
#     for data in clans_data:
#         home_territory = territory_map[data["home_territory_name"]]
#         clan = models.Clan(
#             name=data["name"],
#             species_id=species_map[data["species_name"]].id,
#             world_id=world.id,
#         )
#         db.add(clan)
#         db.flush()
#         home_territory.owner_clan_id = clan.id
#         clan_map[data["name"]] = {"obj": clan, "home": home_territory}
#     db.flush()

#     # COMPLETO: Adiciona as relações diplomáticas iniciais entre clãs.
#     print("Forjando alianças e declarando guerras iniciais...")
#     db.add(
#         models.ClanRelationship(
#             clan_a_id=clan_map["Clã Martelo de Ferro"]["obj"].id,
#             clan_b_id=clan_map["Corte de Aetherion"]["obj"].id,
#             relationship_type=ClanRelationshipTypeEnum.WAR,
#         )
#     )
#     db.add(
#         models.ClanRelationship(
#             clan_a_id=clan_map["Legião Dente Afiado"]["obj"].id,
#             clan_b_id=clan_map["Clã Esmaga-Ossos"]["obj"].id,
#             relationship_type=ClanRelationshipTypeEnum.ALLIANCE,
#         )
#     )

#     print("Definindo personalidades únicas e dando vida aos personagens...")
#     names = [
#         "Thorgar",
#         "Elara",
#         "Roric",
#         "Lirael",
#         "Grak",
#         "Sylas",
#         "Faelan",
#         "Borin",
#         "Seraphina",
#         "Zog",
#         "Morg",
#         "Kael",
#     ]
#     for clan_name, data in clan_map.items():
#         clan_obj, home_territory = data["obj"], data["home"]
#         num_chars = 12 if clan_name == "Legião Dente Afiado" else 8
#         for i in range(num_chars):
#             char_name = f"{random.choice(names)} {clan_name.split(' ')[-1]}"
#             species = species_map[clan_obj.species.name]
#             # ATUALIZADO: Cria o personagem com todos os seus atributos fixos e aleatórios.
#             character = models.Character(
#                 name=char_name,
#                 species_id=species.id,
#                 clan_id=clan_obj.id,
#                 world_id=world.id,
#                 current_health=species.base_health,
#                 position_x=random.uniform(home_territory.start_x, home_territory.end_x),
#                 position_y=random.uniform(home_territory.start_y, home_territory.end_y),
#                 # Atributos de estado e personalidade
#                 fome=random.randint(0, 40),
#                 energia=random.randint(80, 100),
#                 bravura=random.randint(25, 75),
#                 cautela=random.randint(25, 75),
#                 sociabilidade=random.randint(25, 75),
#                 ganancia=random.randint(25, 75),
#                 inteligencia=random.randint(25, 75),
#             )
#             db.add(character)
#     # REMOVIDO: A criação de CharacterAttribute não é mais necessária.

#     # --- 4. MISSÕES TEMÁTICAS (NARRATIVA) ---
#     print("Atribuindo Missões temáticas para cada Clã...")
#     db.flush()  # Garante que todos os personagens e clãs tenham IDs antes de criar as missões.

#     mission_dwarf = models.Mission(
#         world_id=world.id,
#         title="A Grande Forja de Durvak",
#         assignee_clan_id=clan_map["Clã Martelo de Ferro"]["obj"].id,
#         status="ATIVA",
#     )
#     db.add(mission_dwarf)
#     db.flush()
#     db.add(
#         models.MissionObjective(
#             mission_id=mission_dwarf.id,
#             objective_type=ObjectiveTypeEnum.GATHER_RESOURCE,
#             target_resource_id=resource_map["Minério de Ferro"].id,
#             target_quantity=50,
#         )
#     )
#     db.add(
#         models.MissionObjective(
#             mission_id=mission_dwarf.id,
#             objective_type=ObjectiveTypeEnum.GATHER_RESOURCE,
#             target_resource_id=resource_map["Madeira"].id,
#             target_quantity=25,
#         )
#     )

#     mission_human = models.Mission(
#         world_id=world.id,
#         title="Erguer a Muralha de Valmor",
#         assignee_clan_id=clan_map["Reino de Valmor"]["obj"].id,
#         status="ATIVA",
#     )
#     db.add(mission_human)
#     db.flush()
#     db.add(
#         models.MissionObjective(
#             mission_id=mission_human.id,
#             objective_type=ObjectiveTypeEnum.GATHER_RESOURCE,
#             target_resource_id=resource_map["Madeira"].id,
#             target_quantity=100,
#         )
#     )
#     db.add(
#         models.MissionObjective(
#             mission_id=mission_human.id,
#             objective_type=ObjectiveTypeEnum.GATHER_RESOURCE,
#             target_resource_id=resource_map["Pedra"].id,
#             target_quantity=80,
#         )
#     )

#     mission_elf = models.Mission(
#         world_id=world.id,
#         title="Sabotagem nas Minas",
#         assignee_clan_id=clan_map["Corte de Aetherion"]["obj"].id,
#         status="ATIVA",
#     )
#     db.add(mission_elf)
#     db.flush()
#     db.add(
#         models.MissionObjective(
#             mission_id=mission_elf.id,
#             objective_type=ObjectiveTypeEnum.CONQUER_TERRITORY,
#             target_territory_id=territory_map["Minas de Durvak"].id,
#         )
#     )

#     mission_orc = models.Mission(
#         world_id=world.id,
#         title="A Grande Caçada",
#         assignee_clan_id=clan_map["Legião Dente Afiado"]["obj"].id,
#         status="ATIVA",
#     )
#     db.add(mission_orc)
#     db.flush()
#     db.add(
#         models.MissionObjective(
#             mission_id=mission_orc.id,
#             objective_type=ObjectiveTypeEnum.CONQUER_TERRITORY,
#             target_territory_id=territory_map["Colinas Rochosas"].id,
#         )
#     )

#     mission_troll = models.Mission(
#         world_id=world.id,
#         title="Esmagar os Pequeninos!",
#         assignee_clan_id=clan_map["Clã Esmaga-Ossos"]["obj"].id,
#         status="ATIVA",
#     )
#     db.add(mission_troll)
#     db.flush()
#     db.add(
#         models.MissionObjective(
#             mission_id=mission_troll.id,
#             objective_type=ObjectiveTypeEnum.DEFEAT_CHARACTER,
#             target_quantity=10,
#         )
#     )

#     db.commit()
#     print("Cenário de Orbis construído com sucesso!")

# except Exception as e:
#     print(f"Erro catastrófico durante o seeding: {e}")
#     db.rollback()
# finally:
#     db.close()
# seed_db.py

import sys
import os
import random
from datetime import datetime, timezone
from bson import ObjectId

# --- Configuração de Path ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# --- Novas Importações ---
from app.database.database import db, client

print("Iniciando o Construtor de Cenários para MongoDB...")

# --- Reset do Banco de Dados ---
# Cuidado: Isso apaga o banco de dados inteiro!
db_name = db.name
print(f"Limpando o banco de dados '{db_name}'...")
client.drop_database(db_name)

try:
    # --- 1. Dados Estáticos (Species, Resources) ---
    print("Criando espécies e tipos de recursos...")

    species_data = [
        {"_id": 1, "name": "Anão", "base_health": 120, "base_strength": 15},
        {"_id": 2, "name": "Humano", "base_health": 100, "base_strength": 10},
        {"_id": 3, "name": "Elfo", "base_health": 80, "base_strength": 12},
        # ... adicione as outras espécies com IDs numéricos
    ]
    db.species.insert_many(species_data)
    species_map = {s["name"]: s["_id"] for s in species_data}

    # As relações agora podem ser um array dentro do documento da espécie
    # (Não faremos isso aqui para manter a simplicidade da migração)

    # --- 2. Criação do Mundo e Territórios ---
    print("Estabelecendo o mundo e seus territórios...")
    world_doc = {
        "_id": 1,
        "name": "Mundo Padrão",
        "map_width": 1000,
        "map_height": 1000,
        "current_tick": 0,
        "global_event": "NONE",
        "created_at": datetime.now(timezone.utc),
    }
    db.worlds.insert_one(world_doc)

    # --- 3. Clãs e Personagens ---
    print("Povoando o mundo com clãs e personagens (character_summaries)...")

    clans_data = [
        {
            "_id": 1,
            "name": "Reino de Valmor",
            "species_id": species_map["Humano"],
            "world_id": 1,
        },
        {
            "_id": 2,
            "name": "Clã Martelo de Ferro",
            "species_id": species_map["Anão"],
            "world_id": 1,
        },
        # ... adicione os outros clãs com IDs
    ]
    db.clans.insert_many(clans_data)
    clan_map = {c["name"]: c["_id"] for c in clans_data}

    # Criando os documentos de "character_summaries"
    all_characters = []
    char_id_counter = 1
    names = ["Thorgar", "Elara", "Roric", "Lirael", "Grak", "Sylas"]  # etc...

    for clan_doc in clans_data:
        species_doc = db.species.find_one({"_id": clan_doc["species_id"]})
        for _ in range(8):  # Criar 8 personagens por clã
            char_doc = {
                "_id": char_id_counter,
                "name": f"{random.choice(names)} {clan_doc['name'].split(' ')[-1]}",
                "species": {"id": species_doc["_id"], "name": species_doc["name"]},
                "world_id": 1,
                "clan": {"id": clan_doc["_id"], "name": clan_doc["name"]},
                "status": "VIVO",
                "current_health": species_doc["base_health"],
                "position": {
                    "x": random.uniform(350, 650),
                    "y": random.uniform(350, 650),
                },
                "stats": {"kills": 0, "deaths": 0, "resourcesCollected": 0},
                "inventory": [],  # Ex: [{"resource_id": 1, "resource_name": "Peixe", "quantity": 5}]
                "notableEvents": [],
                "lastUpdate": datetime.now(timezone.utc),
            }
            all_characters.append(char_doc)
            char_id_counter += 1

    if all_characters:
        db.characters.insert_many(all_characters)

    # --- 4. Criação do Documento Analítico ---
    print("Criando o snapshot inicial do 'world_analytics'...")

    # Exemplo de como gerar a contagem de população inicial
    pipeline = [
        {"$match": {"world_id": 1}},
        {"$group": {"_id": "$species.name", "count": {"$sum": 1}}},
    ]
    population_data = list(db.characters.aggregate(pipeline))
    pop_by_species = {item["_id"]: item["count"] for item in population_data}

    analytics_doc = {
        "_id": 1,  # ID do Mundo
        "worldName": "Mundo Padrão",
        "currentTick": 0,
        "population": {
            "total": db.characters.count_documents({"world_id": 1}),
            "bySpecies": pop_by_species,
        },
        "activeWars": [],  # Será preenchido pela simulação
        "leaderboards": {},
        "lastUpdate": datetime.now(timezone.utc),
    }
    db.world_analytics.insert_one(analytics_doc)

    print("Cenário de Orbis (MongoDB) construído com sucesso!")

except Exception as e:
    print(f"Erro catastrófico durante o seeding: {e}")
finally:
    client.close()
