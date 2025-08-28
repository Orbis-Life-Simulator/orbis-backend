import sys
import os
import random
from sqlalchemy.orm import Session

# Adiciona o diretório 'app' ao path do Python para que possamos importar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.database.database import engine, SessionLocal, Base
from app.database import models

print("Iniciando o script de seeding para o banco de dados Orbis...")

# Recria completamente o banco de dados do zero
print("Apagando e recriando todas as tabelas...")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db: Session = SessionLocal()

try:
    # --- 1. Criar o Mundo ---
    print("Criando o mundo de Orbis...")
    world = models.World(
        name="Mundo Padrão",
        map_width=1000,
        map_height=1000,
    )
    db.add(world)
    db.flush() # Usa flush para obter o ID do mundo para as próximas inserções

    # --- 2. Criar Espécies ---
    print("Criando as espécies...")
    species_data = [
        {"name": "Anão", "base_health": 120, "base_strength": 15},
        {"name": "Humano", "base_health": 100, "base_strength": 10},
        {"name": "Elfo", "base_health": 80, "base_strength": 12},
        {"name": "Fada", "base_health": 60, "base_strength": 8},
        {"name": "Goblin", "base_health": 70, "base_strength": 7},
        {"name": "Orc", "base_health": 150, "base_strength": 18},
        {"name": "Troll", "base_health": 200, "base_strength": 25},
        {"name": "Zumbi", "base_health": 100, "base_strength": 10},
    ]
    species_map = {}
    for data in species_data:
        species = models.Species(**data)
        db.add(species)
        species_map[data["name"]] = species
    
    db.flush() # Garante que as espécies tenham IDs

    # --- 3. Definir Relações entre Espécies ---
    print("Definindo as regras de relacionamento entre espécies...")
    relationships = [
        # Anões
        (species_map["Anão"], species_map["Humano"], "FRIEND"),
        (species_map["Anão"], species_map["Elfo"], "ENEMY"),
        (species_map["Anão"], species_map["Fada"], "ENEMY"),
        # Humanos
        (species_map["Humano"], species_map["Elfo"], "FRIEND"),
        (species_map["Humano"], species_map["Fada"], "FRIEND"),
        (species_map["Humano"], species_map["Orc"], "ENEMY"),
        (species_map["Humano"], species_map["Troll"], "ENEMY"),
        (species_map["Humano"], species_map["Goblin"], "ENEMY"),
        # Fadas
        (species_map["Fada"], species_map["Elfo"], "INDIFFERENT"),
        (species_map["Fada"], species_map["Troll"], "ENEMY"),
        (species_map["Fada"], species_map["Orc"], "ENEMY"),
        (species_map["Fada"], species_map["Goblin"], "ENEMY"),
        # Elfos
        (species_map["Elfo"], species_map["Orc"], "ENEMY"),
        (species_map["Elfo"], species_map["Troll"], "ENEMY"),
        (species_map["Elfo"], species_map["Goblin"], "ENEMY"),
        # Orcs, Goblins, Trolls
        (species_map["Orc"], species_map["Troll"], "FRIEND"),
        (species_map["Orc"], species_map["Goblin"], "FRIEND"),
        (species_map["Goblin"], species_map["Troll"], "FRIEND"),
    ]
    for rel in relationships:
        db.add(models.SpeciesRelationship(species_a_id=rel[0].id, species_b_id=rel[1].id, relationship_type=rel[2]))

    # --- 4. Criar Tipos de Recursos ---
    print("Criando tipos de recursos...")
    resource_types_data = [
        {"name": "Peixe", "category": "COMIDA", "base_value": 5},
        {"name": "Baga Silvestre", "category": "COMIDA", "base_value": 3},
        {"name": "Minério de Ferro", "category": "MATERIAL", "base_value": 10},
        {"name": "Madeira", "category": "MATERIAL", "base_value": 2},
    ]
    resource_map = {}
    for data in resource_types_data:
        resource = models.ResourceType(**data)
        db.add(resource)
        resource_map[data["name"]] = resource
    
    db.flush()

    # --- 5. Criar Territórios e Alocar Recursos ---
    print("Criando territórios e alocando recursos...")
    territories_data = [
        {"name": "Valmor (Capital Humana)", "start_x": 400, "end_x": 600, "start_y": 400, "end_y": 600},
        {"name": "Minas de Durvak", "start_x": 50, "end_x": 250, "start_y": 50, "end_y": 250},
        {"name": "Floresta de Aetherion", "start_x": 700, "end_x": 950, "start_y": 600, "end_y": 850},
        {"name": "Pântano de Snagûl", "start_x": 50, "end_x": 300, "start_y": 700, "end_y": 950},
        {"name": "Cemitério Assombrado", "start_x": 750, "end_x": 950, "start_y": 50, "end_y": 250},
    ]
    territory_map = {}
    for data in territories_data:
        territory = models.Territory(world_id=world.id, **data)
        db.add(territory)
        territory_map[data["name"]] = territory
    
    db.flush()

    db.add(models.TerritoryResource(territory_id=territory_map["Valmor (Capital Humana)"].id, resource_type_id=resource_map["Peixe"].id, abundance=0.8))
    db.add(models.TerritoryResource(territory_id=territory_map["Minas de Durvak"].id, resource_type_id=resource_map["Minério de Ferro"].id, abundance=1.0))
    db.add(models.TerritoryResource(territory_id=territory_map["Floresta de Aetherion"].id, resource_type_id=resource_map["Madeira"].id, abundance=0.9))
    db.add(models.TerritoryResource(territory_id=territory_map["Floresta de Aetherion"].id, resource_type_id=resource_map["Baga Silvestre"].id, abundance=0.7))

    # --- 6. Criar Clãs ---
    print("Criando clãs...")
    clans_data = [
        {"name": "Guardiões de Valmor", "species_id": species_map["Humano"].id, "home_territory": territory_map["Valmor (Capital Humana)"]},
        {"name": "Clã Martelo de Ferro", "species_id": species_map["Anão"].id, "home_territory": territory_map["Minas de Durvak"]},
        {"name": "Legião Dente Afiado", "species_id": species_map["Orc"].id, "home_territory": territory_map["Pântano de Snagûl"]},
        {"name": "A Horda Rastejante", "species_id": species_map["Zumbi"].id, "home_territory": territory_map["Cemitério Assombrado"]},
    ]
    clan_map = {}
    for data in clans_data:
        home_territory = data.pop("home_territory")
        clan = models.Clan(world_id=world.id, **data)
        db.add(clan)
        clan_map[data["name"]] = (clan, home_territory)
    
    db.flush()

    # --- 7. Criar Personagens ---
    print("Povoando o mundo com personagens...")
    character_names = ["Thorgar", "Elara", "Roric", "Lirael", "Grak", "Sylas", "Faelan", "Borin", "Seraphina", "Zog", "Morg", "Kael"]
    
    for clan_name, (clan_obj, home_territory) in clan_map.items():
        for i in range(5): # Criar 5 membros por clã
            char_name = f"{random.choice(character_names)} {clan_name.split(' ')[-1]}"
            species = db.query(models.Species).get(clan_obj.species_id)

            character = models.Character(
                name=char_name,
                species_id=species.id,
                clan_id=clan_obj.id,
                world_id=world.id,
                current_health=species.base_health,
                position_x=random.uniform(home_territory.start_x, home_territory.end_x),
                position_y=random.uniform(home_territory.start_y, home_territory.end_y),
                current_state="AGRUPANDO", # Começam tentando se agrupar
            )
            db.add(character)
            db.flush() # Flush para obter o ID do personagem para o atributo
            
            # Adiciona o atributo de Fome para cada personagem
            hunger_attr = models.CharacterAttribute(
                character_id=character.id,
                attribute_name="Fome",
                attribute_value=random.randint(0, 40) # Começam com um pouco de fome
            )
            db.add(hunger_attr)

    # --- Finalizar ---
    print("Salvando todos os dados no banco de dados...")
    db.commit()
    print("Seeding concluído com sucesso!")

except Exception as e:
    print(f"Ocorreu um erro durante o seeding: {e}")
    db.rollback()
finally:
    db.close()
    print("Conexão com o banco de dados fechada.")
