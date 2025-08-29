import sys, os, random
from sqlalchemy.orm import Session

# --- Configuração de Path ---
# Esta é uma manobra comum em Python para garantir que o script, mesmo quando
# executado da raiz do projeto, possa encontrar e importar módulos da pasta 'app'.
# Ele adiciona o diretório atual ao caminho de busca de módulos do Python.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# --- Importações da Aplicação ---
# Importa os componentes necessários do banco de dados e os modelos SQLAlchemy.
from app.database.database import engine, SessionLocal, Base
from app.database import models

print("Iniciando o Construtor de Cenários AVANÇADO para o Mundo de Orbis...")

# --- Reset e Criação do Banco de Dados ---
# ATENÇÃO: 'drop_all' apaga TODAS as tabelas existentes.
# Isso garante que cada execução do script comece com um banco de dados limpo.
Base.metadata.drop_all(bind=engine)
# 'create_all' cria todas as tabelas definidas nos seus modelos que herdam de 'Base'.
Base.metadata.create_all(bind=engine)

# Cria uma nova sessão com o banco de dados para esta operação de seeding.
db: Session = SessionLocal()

# O bloco try...finally garante que a sessão do banco de dados seja sempre fechada,
# mesmo que ocorra um erro durante o processo de seeding.
try:
    # --- 1. MUNDO, ESPÉCIES, RELAÇÕES E RECURSOS (BASE SÓLIDA) ---
    # Esta seção cria as regras e os "tijolos" fundamentais do mundo.
    # São os elementos que raramente mudam e definem a física e a biologia da simulação.
    print("Estabelecendo as fundações do mundo...")

    # Cria a instância principal do mundo, o contêiner para toda a simulação.
    world = models.World(name="Mundo Padrão", map_width=1000, map_height=1000)
    db.add(world)
    db.flush()  # Envia as mudanças para o DB para que 'world.id' seja gerado e possa ser usado.

    # Define os "blueprints" de todas as espécies que podem existir.
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
    # Usa um dicionário ('map') para acesso rápido aos objetos Species pelo nome.
    species_map = {data["name"]: models.Species(**data) for data in species_data}
    [db.add(s) for s in species_map.values()]
    db.flush()

    # Define as relações padrão e inatas entre as espécies.
    relationships = [
        ("Anão", "Humano", "FRIEND"),
        ("Anão", "Elfo", "ENEMY"),
        ("Anão", "Fada", "ENEMY"),
        ("Anão", "Orc", "ENEMY"),
        ("Anão", "Goblin", "ENEMY"),
        ("Anão", "Troll", "ENEMY"),
        ("Humano", "Elfo", "FRIEND"),
        ("Humano", "Fada", "FRIEND"),
        ("Humano", "Orc", "ENEMY"),
        ("Humano", "Troll", "ENEMY"),
        ("Humano", "Goblin", "ENEMY"),
        ("Fada", "Elfo", "INDIFFERENT"),
        ("Fada", "Troll", "ENEMY"),
        ("Fada", "Orc", "ENEMY"),
        ("Fada", "Goblin", "ENEMY"),
        ("Elfo", "Orc", "ENEMY"),
        ("Elfo", "Troll", "ENEMY"),
        ("Elfo", "Goblin", "ENEMY"),
        ("Orc", "Troll", "FRIEND"),
        ("Orc", "Goblin", "FRIEND"),
        ("Goblin", "Troll", "FRIEND"),
    ]
    for r in relationships:
        db.add(
            models.SpeciesRelationship(
                species_a_id=species_map[r[0]].id,
                species_b_id=species_map[r[1]].id,
                relationship_type=r[2],
            )
        )

    # Define os tipos de recursos que podem ser encontrados no mundo.
    resource_data = [
        {"name": "Peixe", "category": "COMIDA", "base_value": 5},
        {"name": "Baga Silvestre", "category": "COMIDA", "base_value": 3},
        {"name": "Minério de Ferro", "category": "MATERIAL", "base_value": 10},
        {"name": "Madeira", "category": "MATERIAL", "base_value": 2},
        {"name": "Pedra", "category": "MATERIAL", "base_value": 4},
    ]
    resource_map = {data["name"]: models.ResourceType(**data) for data in resource_data}
    [db.add(r) for r in resource_map.values()]
    db.flush()

    # --- 2. TERRITÓRIOS E NÓS DE RECURSOS (MUNDO RICO) ---
    # Esta seção dá forma ao mapa, criando regiões geográficas e distribuindo
    # os recursos definidos anteriormente pelo mundo.
    print("Distribuindo recursos e definindo territórios...")

    # Define as áreas nomeadas do mapa com suas coordenadas.
    territories_data = [
        {
            "name": "Valmor (Capital Humana)",
            "start_x": 350,
            "end_x": 650,
            "start_y": 350,
            "end_y": 650,
        },
        {
            "name": "Minas de Durvak",
            "start_x": 0,
            "end_x": 250,
            "start_y": 0,
            "end_y": 250,
        },
        {
            "name": "Floresta de Aetherion",
            "start_x": 750,
            "end_x": 1000,
            "start_y": 650,
            "end_y": 900,
        },
        {
            "name": "Pântano de Snagûl",
            "start_x": 0,
            "end_x": 300,
            "start_y": 700,
            "end_y": 1000,
        },
        {
            "name": "Cemitério Assombrado",
            "start_x": 750,
            "end_x": 1000,
            "start_y": 0,
            "end_y": 250,
        },
        {
            "name": "Lago Elyndor",
            "start_x": 300,
            "end_x": 700,
            "start_y": 0,
            "end_y": 300,
        },
        {
            "name": "Colinas Rochosas",
            "start_x": 0,
            "end_x": 300,
            "start_y": 300,
            "end_y": 650,
        },
        {
            "name": "Bosque Antigo",
            "start_x": 700,
            "end_x": 1000,
            "start_y": 300,
            "end_y": 600,
        },
        {
            "name": "Planícies Centrais",
            "start_x": 300,
            "end_x": 700,
            "start_y": 700,
            "end_y": 1000,
        },
    ]
    territory_map = {
        data["name"]: models.Territory(world_id=world.id, **data)
        for data in territories_data
    }
    [db.add(t) for t in territory_map.values()]
    db.flush()

    # Espalha os "nós" de recursos (árvores, minas, etc.) dentro dos territórios.
    resource_nodes_to_create = [
        ("Valmor (Capital Humana)", "Baga Silvestre", 5, 20),
        ("Valmor (Capital Humana)", "Pedra", 8, 15),
        ("Minas de Durvak", "Minério de Ferro", 10, 30),
        ("Minas de Durvak", "Pedra", 15, 20),
        ("Floresta de Aetherion", "Madeira", 15, 15),
        ("Floresta de Aetherion", "Baga Silvestre", 8, 20),
        ("Lago Elyndor", "Peixe", 12, 25),
        ("Colinas Rochosas", "Baga Silvestre", 10, 15),
        ("Colinas Rochosas", "Minério de Ferro", 3, 10),
        ("Bosque Antigo", "Madeira", 20, 10),
        ("Bosque Antigo", "Baga Silvestre", 5, 15),
        ("Planícies Centrais", "Baga Silvestre", 15, 10),
    ]
    for terr_name, res_name, count, avg_qty in resource_nodes_to_create:
        territory = territory_map[terr_name]
        resource = resource_map[res_name]
        for _ in range(count):
            db.add(
                models.ResourceNode(
                    world_id=world.id,  # Associando o nó ao mundo
                    resource_type_id=resource.id,
                    position_x=random.uniform(territory.start_x, territory.end_x),
                    position_y=random.uniform(territory.start_y, territory.end_y),
                    quantity=random.randint(int(avg_qty * 0.5), int(avg_qty * 1.5)),
                )
            )

    # --- 3. CLÃS E PERSONAGENS (VIDA INICIAL) ---
    # Esta seção dá vida ao mundo, criando as facções (clãs) e os indivíduos
    # (personagens) que irão interagir e evoluir na simulação.
    print("Povoando o mundo com clãs e personagens...")

    # Define os clãs, suas espécies principais e seus territórios natais.
    clans_data = [
        {
            "name": "Reino de Valmor",
            "species_name": "Humano",
            "home_territory_name": "Valmor (Capital Humana)",
        },
        {
            "name": "Clã Martelo de Ferro",
            "species_name": "Anão",
            "home_territory_name": "Minas de Durvak",
        },
        {
            "name": "Corte de Aetherion",
            "species_name": "Elfo",
            "home_territory_name": "Floresta de Aetherion",
        },
        {
            "name": "Enxame de Elyndor",
            "species_name": "Fada",
            "home_territory_name": "Lago Elyndor",
        },
        {
            "name": "Legião Dente Afiado",
            "species_name": "Orc",
            "home_territory_name": "Pântano de Snagûl",
        },
        {
            "name": "Clã Esmaga-Ossos",
            "species_name": "Troll",
            "home_territory_name": "Pântano de Snagûl",
        },
        {
            "name": "A Horda Rastejante",
            "species_name": "Zumbi",
            "home_territory_name": "Cemitério Assombrado",
        },
    ]
    clan_map = {}
    for data in clans_data:
        home_territory = territory_map[data["home_territory_name"]]
        clan = models.Clan(
            name=data["name"],
            species_id=species_map[data["species_name"]].id,
            world_id=world.id,
        )
        db.add(clan)
        db.flush()
        home_territory.owner_clan_id = (
            clan.id
        )  # Define o clã como dono de seu território natal.
        clan_map[data["name"]] = {"obj": clan, "home": home_territory}
    db.flush()

    # Cria os personagens iniciais para cada clã.
    names = [
        "Thorgar",
        "Elara",
        "Roric",
        "Lirael",
        "Grak",
        "Sylas",
        "Faelan",
        "Borin",
        "Seraphina",
        "Zog",
        "Morg",
        "Kael",
    ]
    for clan_name, data in clan_map.items():
        clan_obj, home_territory = data["obj"], data["home"]
        num_chars = (
            12 if clan_name == "Legião Dente Afiado" else 8
        )  # Dá mais personagens para um clã específico.
        for i in range(num_chars):
            char_name = f"{random.choice(names)} {clan_name.split(' ')[-1]}"
            species = species_map[clan_obj.species.name]
            character = models.Character(
                name=char_name,
                species_id=species.id,
                clan_id=clan_obj.id,
                world_id=world.id,
                current_health=species.base_health,
                # Posiciona o personagem aleatoriamente dentro de seu território natal.
                position_x=random.uniform(home_territory.start_x, home_territory.end_x),
                position_y=random.uniform(home_territory.start_y, home_territory.end_y),
                current_state="AGRUPANDO",  # Estado inicial da IA.
            )
            db.add(character)
            db.flush()
            # Adiciona os atributos iniciais, como Fome e o contador para reprodução.
            db.add(
                models.CharacterAttribute(
                    character_id=character.id,
                    attribute_name="Fome",
                    attribute_value=random.randint(0, 40),
                )
            )
            db.add(
                models.CharacterAttribute(
                    character_id=character.id,
                    attribute_name="ComidaParaReproducao",
                    attribute_value=0,
                )
            )

    # --- 4. MISSÕES TEMÁTICAS (NARRATIVA) ---
    # Esta seção cria os objetivos iniciais para os clãs, dando-lhes um propósito
    # e impulsionando a narrativa e a jogabilidade emergente.
    print("Atribuindo Missões temáticas para cada Clã...")

    # Missão dos Anões: focada em coleta de recursos industriais.
    mission_dwarf = models.Mission(
        world_id=world.id,
        title="A Grande Forja de Durvak",
        assignee_clan_id=clan_map["Clã Martelo de Ferro"]["obj"].id,
        status="ATIVA",
    )
    db.add(mission_dwarf)
    db.flush()
    db.add(
        models.MissionObjective(
            mission_id=mission_dwarf.id,
            objective_type="GATHER_RESOURCE",
            target_resource_id=resource_map["Minério de Ferro"].id,
            target_quantity=50,
        )
    )
    db.add(
        models.MissionObjective(
            mission_id=mission_dwarf.id,
            objective_type="GATHER_RESOURCE",
            target_resource_id=resource_map["Madeira"].id,
            target_quantity=25,
        )
    )

    # Missão dos Humanos: focada em construção e defesa.
    mission_human = models.Mission(
        world_id=world.id,
        title="Erguer a Muralha de Valmor",
        assignee_clan_id=clan_map["Reino de Valmor"]["obj"].id,
        status="ATIVA",
    )
    db.add(mission_human)
    db.flush()
    db.add(
        models.MissionObjective(
            mission_id=mission_human.id,
            objective_type="GATHER_RESOURCE",
            target_resource_id=resource_map["Madeira"].id,
            target_quantity=100,
        )
    )
    db.add(
        models.MissionObjective(
            mission_id=mission_human.id,
            objective_type="GATHER_RESOURCE",
            target_resource_id=resource_map["Pedra"].id,
            target_quantity=80,
        )
    )

    # Missão dos Elfos: focada em conflito e conquista, refletindo sua inimizade com os Anões.
    mission_elf = models.Mission(
        world_id=world.id,
        title="Sabotagem nas Minas",
        assignee_clan_id=clan_map["Corte de Aetherion"]["obj"].id,
        status="ATIVA",
    )
    db.add(mission_elf)
    db.flush()
    db.add(
        models.MissionObjective(
            mission_id=mission_elf.id,
            objective_type="CONQUER_TERRITORY",
            target_territory_id=territory_map["Minas de Durvak"].id,
        )
    )

    # Missão dos Orcs: focada em expansão territorial.
    mission_orc = models.Mission(
        world_id=world.id,
        title="A Grande Caçada",
        assignee_clan_id=clan_map["Legião Dente Afiado"]["obj"].id,
        status="ATIVA",
    )
    db.add(mission_orc)
    db.flush()
    db.add(
        models.MissionObjective(
            mission_id=mission_orc.id,
            objective_type="CONQUER_TERRITORY",
            target_territory_id=territory_map["Colinas Rochosas"].id,
        )
    )

    # Missão dos Trolls: focada em combate genérico.
    mission_troll = models.Mission(
        world_id=world.id,
        title="Esmagar os Pequeninos!",
        assignee_clan_id=clan_map["Clã Esmaga-Ossos"]["obj"].id,
        status="ATIVA",
    )
    db.add(mission_troll)
    db.flush()
    db.add(
        models.MissionObjective(
            mission_id=mission_troll.id,
            objective_type="DEFEAT_CHARACTER",
            target_quantity=10,
        )
    )

    # Confirma todas as transações feitas até agora, salvando permanentemente os dados.
    db.commit()
    print("Cenário de Orbis construído com sucesso!")

except Exception as e:
    # Se qualquer erro ocorrer, imprime a mensagem e desfaz todas as alterações
    # feitas nesta sessão para manter a integridade do banco de dados.
    print(f"Erro catastrófico durante o seeding: {e}")
    db.rollback()
finally:
    # Garante que a conexão com o banco de dados seja fechada ao final do script.
    db.close()
