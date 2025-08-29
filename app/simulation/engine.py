import math
import random
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from ..database import models

# --- Constantes da Simulação ---
# Define parâmetros globais que controlam as habilidades e interações dos personagens.
VISION_RANGE = 100.0  # A distância máxima que um personagem pode "ver" outros personagens ou objetos.
MOVE_SPEED = 5.0      # A distância que um personagem se move a cada "tick" da simulação.
ATTACK_RANGE = 10.0   # A distância máxima a partir da qual um personagem pode atacar um alvo.
GATHER_RANGE = 15.0   # A distância máxima para coletar um recurso.
GROUPING_DISTANCE = 50.0 # A distância que um personagem tenta manter de seu grupo.

# --- Constantes de Necessidades e Comportamento ---
# Define os parâmetros que governam as necessidades básicas e decisões dos personagens.
HUNGER_INCREASE_RATE = 0.5  # O quanto a fome de um personagem aumenta a cada "tick".
HUNGER_THRESHOLD = 60       # O nível de fome em que um personagem começa a procurar comida.
MAX_HUNGER = 100            # O nível máximo de fome. Ao atingir, o personagem começa a perder vida.
STARVATION_DAMAGE = 2       # A quantidade de dano que um personagem sofre por "tick" quando está morrendo de fome.
HUNGER_REDUCTION_PER_FOOD = 50 # O quanto a fome é reduzida ao consumir uma unidade de comida.
FLEE_HEALTH_PERCENTAGE = 0.25  # A porcentagem de vida abaixo da qual um personagem tentará fugir de uma ameaça.
REPRODUCTION_FOOD_COST = 100   # A quantidade de "comida para reprodução" necessária para gerar um novo personagem.

# --- Funções Auxiliares e de IA ---

def get_effective_relationship(
    db: Session, char1: models.Character, char2: models.Character
) -> str:
    """
    Determina o relacionamento efetivo ('FRIEND', 'ENEMY', 'INDIFFERENT') entre dois personagens.
    A lógica segue uma hierarquia de prioridades:
    1. Zumbis são amigos entre si e inimigos de todos os outros.
    2. Membros do mesmo clã são amigos.
    3. Clãs em guerra são inimigos.
    4. Clãs em aliança são amigos.
    5. A relação padrão entre espécies (ex: predador/presa) é usada se não houver regras de clã.
    6. Se nenhuma das condições acima for atendida, eles são indiferentes.
    """
    # Um personagem é sempre "amigo" de si mesmo.
    if char1.id == char2.id:
        return "FRIEND"

    # Regra especial para Zumbis: eles são amigos entre si e inimigos de todos os outros.
    zombie_species = db.query(models.Species).filter_by(name="Zumbi").first()
    if zombie_species:
        is_char1_zombie = char1.species_id == zombie_species.id
        is_char2_zombie = char2.species_id == zombie_species.id
        if is_char1_zombie and is_char2_zombie:
            return "FRIEND"
        if is_char1_zombie or is_char2_zombie:
            return "ENEMY"

    # Verifica relações baseadas em clãs.
    if char1.clan_id and char2.clan_id:
        # Membros do mesmo clã são amigos.
        if char1.clan_id == char2.clan_id:
            return "FRIEND"
        # Verifica se existe uma relação diplomática (Guerra ou Aliança) definida entre os clãs.
        clan_rel = (
            db.query(models.ClanRelationship)
            .filter(
                or_(
                    (models.ClanRelationship.clan_a_id == char1.clan_id)
                    & (models.ClanRelationship.clan_b_id == char2.clan_id),
                    (models.ClanRelationship.clan_a_id == char2.clan_id)
                    & (models.ClanRelationship.clan_b_id == char1.clan_id),
                )
            )
            .first()
        )
        if clan_rel:
            if clan_rel.relationship_type == "WAR":
                return "ENEMY"
            if clan_rel.relationship_type == "ALLIANCE":
                return "FRIEND"

    # Se não houver relação de clã, verifica a relação padrão entre as espécies.
    species_rel = (
        db.query(models.SpeciesRelationship)
        .filter(
            or_(
                (models.SpeciesRelationship.species_a_id == char1.species_id)
                & (models.SpeciesRelationship.species_b_id == char2.species_id),
                (models.SpeciesRelationship.species_a_id == char2.species_id)
                & (models.SpeciesRelationship.species_b_id == char1.species_id),
            )
        )
        .first()
    )
    if species_rel:
        return species_rel.relationship_type

    # Se nenhuma regra se aplica, o relacionamento é indiferente.
    return "INDIFFERENT"


def get_territory_at_position(db: Session, world_id: int, x: float, y: float):
    """Retorna o território (se houver) em uma determinada coordenada (x, y) do mundo."""
    return (
        db.query(models.Territory)
        .filter(
            models.Territory.world_id == world_id,
            models.Territory.start_x <= x,
            models.Territory.end_x >= x,
            models.Territory.start_y <= y,
            models.Territory.end_y >= y,
        )
        .first()
    )


def find_nearest_character_by_relationship(
    origin_char: models.Character,
    all_chars: list[models.Character],
    relationship_func,
    target_relationship: str,
):
    """
    Encontra o personagem mais próximo de 'origin_char' que tenha um relacionamento específico.
    Usa a distância ao quadrado para otimização (evita calcular a raiz quadrada).
    """
    nearest_char, min_dist_sq = None, VISION_RANGE**2
    for target_char in all_chars:
        # Ignora a verificação do personagem com ele mesmo.
        if origin_char.id == target_char.id:
            continue
        # Verifica se o relacionamento corresponde ao alvo (ex: 'ENEMY').
        if relationship_func(origin_char, target_char) == target_relationship:
            # Calcula a distância ao quadrado.
            dist_sq = (target_char.position_x - origin_char.position_x) ** 2 + (
                target_char.position_y - origin_char.position_y
            ) ** 2
            # Se for o mais próximo encontrado até agora, armazena.
            if dist_sq < min_dist_sq:
                min_dist_sq, nearest_char = dist_sq, target_char
    return nearest_char


def find_group_center(
    origin_char: models.Character, all_chars: list[models.Character], relationship_func
):
    """
    Calcula o ponto central (médio) de todos os personagens "amigos" dentro do alcance de visão.
    Isso serve como um ponto de encontro para o comportamento de agrupamento.
    Retorna uma tupla (x, y) ou None se não houver amigos por perto.
    """
    friends_positions = []
    for other_char in all_chars:
        if origin_char.id != other_char.id:
            dist_sq = (other_char.position_x - origin_char.position_x) ** 2 + (
                other_char.position_y - origin_char.position_y
            ) ** 2
            # Considera apenas amigos dentro do alcance de visão.
            if (
                dist_sq < VISION_RANGE**2
                and relationship_func(origin_char, other_char) == "FRIEND"
            ):
                friends_positions.append((other_char.position_x, other_char.position_y))

    # Se houver amigos, calcula a média das posições x e y.
    if not friends_positions:
        return None
    avg_x = sum(pos[0] for pos in friends_positions) / len(friends_positions)
    avg_y = sum(pos[1] for pos in friends_positions) / len(friends_positions)
    return (avg_x, avg_y)


def find_nearest_resource_node(
    db: Session,
    character: models.Character,
    resource_category: str = None,
    resource_id: int = None,
):
    """
    Encontra o nó de recurso não esgotado mais próximo do personagem.
    Pode filtrar por categoria de recurso (ex: 'COMIDA') ou por um ID de recurso específico.
    """
    # Começa a consulta buscando todos os nós de recursos que não estão esgotados.
    query = db.query(models.ResourceNode).filter(
        models.ResourceNode.is_depleted == False
    )
    # Aplica filtros opcionais.
    if resource_id:
        query = query.filter(models.ResourceNode.resource_type_id == resource_id)
    elif resource_category:
        query = query.join(models.ResourceType).filter(
            models.ResourceType.category == resource_category
        )

    potential_nodes = query.all()
    nearest_node, min_dist_sq = None, float("inf")

    # Itera sobre os nós encontrados para achar o mais próximo.
    for node in potential_nodes:
        dist_sq = (node.position_x - character.position_x) ** 2 + (
            node.position_y - character.position_y
        ) ** 2
        if dist_sq < min_dist_sq:
            min_dist_sq, nearest_node = dist_sq, node
    return nearest_node


def move_towards_position(
    character: models.Character,
    pos_x: float,
    pos_y: float,
    world: models.World,
    stop_distance: float,
):
    """
    Move o personagem em direção a uma coordenada (pos_x, pos_y).
    A função para o movimento quando o personagem está a 'stop_distance' do alvo.
    Retorna True se o personagem se moveu, False se ele já chegou ao destino.
    """
    # Calcula o vetor de direção para o alvo.
    direction_x, direction_y = (
        pos_x - character.position_x,
        pos_y - character.position_y,
    )
    distance = math.sqrt(direction_x**2 + direction_y**2)

    # Se a distância for menor que a distância de parada, considera que chegou.
    if distance < stop_distance or distance == 0:
        return False

    # Normaliza o vetor de direção (transforma em um vetor de comprimento 1).
    norm_x, norm_y = direction_x / distance, direction_y / distance
    # Calcula a nova posição aplicando a velocidade.
    new_x, new_y = (
        character.position_x + norm_x * MOVE_SPEED,
        character.position_y + norm_y * MOVE_SPEED,
    )

    # Garante que a nova posição esteja dentro dos limites do mapa.
    character.position_x, character.position_y = max(
        0, min(world.map_width, new_x)
    ), max(0, min(world.map_height, new_y))
    return True


def move_towards_target(
    character: models.Character, target: models.Character, world: models.World
):
    """Função de conveniência para mover um personagem em direção a outro, parando no alcance de ataque."""
    return move_towards_position(
        character, target.position_x, target.position_y, world, ATTACK_RANGE
    )


def move_away_from_target(
    character: models.Character, target_char: models.Character, world: models.World
):
    """
    Move o personagem na direção oposta a um alvo. Usado para o comportamento de fuga.
    """
    if not target_char:
        return

    # Calcula o vetor de direção, mas invertido (origem - alvo).
    direction_x = character.position_x - target_char.position_x
    direction_y = character.position_y - target_char.position_y
    distance = math.sqrt(direction_x**2 + direction_y**2)

    # Se a distância for zero, escolhe uma direção aleatória para evitar ficar parado.
    if distance == 0:
        direction_x, direction_y, distance = (
            random.uniform(-1, 1),
            random.uniform(-1, 1),
            1,
        )
    # Normaliza e aplica a velocidade para calcular a nova posição.
    norm_x, norm_y = direction_x / distance, direction_y / distance
    new_x = character.position_x + norm_x * MOVE_SPEED
    new_y = character.position_y + norm_y * MOVE_SPEED

    # Garante que o personagem permaneça dentro dos limites do mapa.
    character.position_x = max(0, min(world.map_width, new_x))
    character.position_y = max(0, min(world.map_height, new_y))


def consume_food_from_inventory(
    db: Session, character: models.Character, world: models.World
):
    """
    Procura por um item de 'COMIDA' no inventário do personagem, consome uma unidade,
    reduz a fome e remove o item se a quantidade chegar a zero.
    Retorna True se comeu, False caso contrário.
    """
    # Encontra o primeiro item de comida no inventário.
    food_item = (
        db.query(models.CharacterInventory)
        .join(models.ResourceType)
        .filter(
            models.CharacterInventory.character_id == character.id,
            models.ResourceType.category == "COMIDA",
        )
        .first()
    )
    if food_item:
        food_item.quantity -= 1  # Reduz a quantidade.
        # Encontra o atributo 'Fome' e reduz seu valor.
        hunger_attr = (
            db.query(models.CharacterAttribute)
            .filter_by(character_id=character.id, attribute_name="Fome")
            .first()
        )
        if hunger_attr:
            hunger_attr.attribute_value = max(
                0, hunger_attr.attribute_value - HUNGER_REDUCTION_PER_FOOD
            )
        # Se o item acabar, remove-o do inventário.
        if food_item.quantity <= 0:
            db.delete(food_item)
        return True
    return False


def process_wandering_state(character: models.Character, world: models.World):
    """
    Simula o comportamento de perambular (andar sem rumo).
    Aplica um pequeno vetor de movimento aleatório à posição do personagem.
    """
    new_dx, new_dy = random.uniform(-MOVE_SPEED, MOVE_SPEED), random.uniform(
        -MOVE_SPEED, MOVE_SPEED
    )
    # Atualiza a posição, garantindo que o personagem fique dentro do mapa.
    character.position_x = max(0, min(world.map_width, character.position_x + new_dx))
    character.position_y = max(0, min(world.map_height, character.position_y + new_dy))


def update_character_needs(
    db: Session, character: models.Character, world: models.World
) -> bool:
    """
    Atualiza as necessidades básicas do personagem, como a fome.
    Se a fome atingir o máximo, aplica dano de inanição.
    Retorna True se o personagem morrer, False caso contrário.
    """
    # Encontra ou cria o atributo 'Fome' para o personagem.
    hunger_attr = (
        db.query(models.CharacterAttribute)
        .filter_by(character_id=character.id, attribute_name="Fome")
        .first()
    )
    if not hunger_attr:
        hunger_attr = models.CharacterAttribute(
            character_id=character.id, attribute_name="Fome", attribute_value=0
        )
        db.add(hunger_attr)

    # Aumenta a fome com o tempo.
    hunger_attr.attribute_value += HUNGER_INCREASE_RATE

    # Se a fome atingir o máximo, o personagem sofre dano.
    if hunger_attr.attribute_value >= MAX_HUNGER:
        character.current_health -= STARVATION_DAMAGE
        # Verifica se o personagem morreu de fome.
        if character.current_health <= 0:
            db.add(
                models.EventLog(
                    world_id=world.id,
                    event_type="MORTE_FOME",
                    description=f"'{character.name}' morreu de fome.",
                    primary_char_id=character.id,
                )
            )
            return True # Morreu.
    return False # Sobreviveu.


def process_attacking_state(
    db: Session,
    attacker: models.Character,
    target: models.Character,
    world: models.World,
    zombie_species: models.Species | None,
) -> str:
    """
    Processa a lógica de um ataque.
    1. Move o atacante em direção ao alvo.
    2. Se estiver no alcance, causa dano.
    3. Verifica se o alvo morreu.
    4. Se o atacante for um zumbi, a vítima pode se transformar em zumbi.
    Retorna o status do alvo: 'ALIVE', 'KILLED', ou 'TRANSFORMED'.
    """
    # Tenta se mover em direção ao alvo. Se `move_towards_target` retornar False, significa que já está no alcance.
    if not move_towards_target(attacker, target, world):
        # Causa dano baseado na força da espécie do atacante.
        damage = attacker.species.base_strength
        target.current_health -= damage
        db.add(
            models.EventLog(
                world_id=world.id,
                event_type="ATAQUE",
                description=f"'{attacker.name}' atacou '{target.name}' por {damage} de dano. Vida: {target.current_health}",
                primary_char_id=attacker.id,
                secondary_char_id=target.id,
            )
        )
        # Verifica se o alvo morreu.
        if target.current_health <= 0:
            attacker.current_state, attacker.target_character_id = "AGRUPANDO", None
            # Regra de transformação de zumbi.
            if zombie_species and attacker.species_id == zombie_species.id:
                (
                    target.name,
                    target.species_id,
                    target.clan_id,
                    target.current_health,
                    target.current_state,
                ) = (
                    f"Zumbi {target.name}",
                    zombie_species.id,
                    None,
                    zombie_species.base_health,
                    "AGRUPANDO",
                )
                db.add(
                    models.EventLog(
                        world_id=world.id,
                        event_type="TRANSFORMACAO_ZUMBI",
                        description=f"'{target.name}' foi transformado.",
                        primary_char_id=target.id,
                        secondary_char_id=attacker.id,
                    )
                )
                return "TRANSFORMED"
            else:
                # Morte normal.
                db.add(
                    models.EventLog(
                        world_id=world.id,
                        event_type="MORTE",
                        description=f"'{target.name}' foi morto por '{attacker.name}'.",
                        primary_char_id=target.id,
                        secondary_char_id=attacker.id,
                    )
                )
                return "KILLED"
    return "ALIVE"


def get_clan_active_mission(db: Session, clan_id: int):
    """Busca e retorna a missão ativa de um determinado clã, se houver."""
    if not clan_id:
        return None
    return (
        db.query(models.Mission)
        .filter(
            models.Mission.assignee_clan_id == clan_id, models.Mission.status == "ATIVA"
        )
        .first()
    )


def check_and_update_mission_progress(db: Session, world_id: int):
    """
    Verifica o progresso de todas as missões ativas no mundo.
    Atualiza o status dos objetivos e das missões se as condições forem atendidas.
    """
    active_missions = (
        db.query(models.Mission).filter_by(world_id=world_id, status="ATIVA").all()
    )
    for mission in active_missions:
        all_objectives_complete = True
        for obj in mission.objectives:
            if obj.is_complete:
                continue

            # Lógica para objetivo de coletar recursos.
            if obj.objective_type == "GATHER_RESOURCE":
                # Soma a quantidade do recurso alvo no inventário de todos os membros do clã.
                total = (
                    db.query(func.sum(models.CharacterInventory.quantity))
                    .join(models.Character)
                    .filter(
                        models.Character.clan_id == mission.assignee_clan_id,
                        models.CharacterInventory.resource_type_id
                        == obj.target_resource_id,
                    )
                    .scalar()
                    or 0
                )
                if total >= obj.target_quantity:
                    obj.is_complete = True
            # Lógica para objetivo de conquistar território.
            elif obj.objective_type == "CONQUER_TERRITORY":
                territory = db.query(models.Territory).get(obj.target_territory_id)
                if territory:
                    # Conta quantos membros do clã estão dentro do território alvo.
                    members_in_territory = (
                        db.query(models.Character)
                        .filter(
                            models.Character.clan_id == mission.assignee_clan_id,
                            models.Character.position_x.between(
                                territory.start_x, territory.end_x
                            ),
                            models.Character.position_y.between(
                                territory.start_y, territory.end_y
                            ),
                        )
                        .count()
                    )
                    total_members = (
                        db.query(models.Character)
                        .filter_by(clan_id=mission.assignee_clan_id)
                        .count()
                    )
                    # Se mais de 50% dos membros do clã estiverem no território, ele é conquistado.
                    if (
                        total_members > 0
                        and (members_in_territory / total_members) > 0.5
                    ):
                        obj.is_complete, territory.owner_clan_id = (
                            True,
                            mission.assignee_clan_id,
                        )
            if not obj.is_complete:
                all_objectives_complete = False
        # Se todos os objetivos foram concluídos, a missão é marcada como 'CONCLUÍDA'.
        if all_objectives_complete:
            mission.status = "CONCLÍDA"


def process_reproduction(db: Session, character: models.Character, world: models.World):
    """
    Processa a lógica de reprodução para um personagem.
    Se o personagem acumulou comida suficiente para reprodução, cria um novo personagem (filho).
    Retorna True se um novo personagem nasceu, False caso contrário.
    """
    # Zumbis não se reproduzem.
    if character.species.name == "Zumbi":
        return False

    # Verifica se o personagem tem o atributo 'ComidaParaReproducao' e se atingiu o custo.
    food_attr = (
        db.query(models.CharacterAttribute)
        .filter_by(character_id=character.id, attribute_name="ComidaParaReproducao")
        .first()
    )
    if food_attr and food_attr.attribute_value >= REPRODUCTION_FOOD_COST:
        food_attr.attribute_value -= REPRODUCTION_FOOD_COST # Deduz o custo.
        new_name = (
            f"{random.choice(['Cria de', 'Filho de'])} {character.name.split(' ')[0]}"
        )
        # Cria o novo personagem.
        new_char = models.Character(
            name=new_name,
            species_id=character.species_id,
            clan_id=character.clan_id,
            world_id=world.id,
            current_health=character.species.base_health,
            position_x=character.position_x + random.uniform(-5, 5), # Nasce perto do pai/mãe.
            position_y=character.position_y + random.uniform(-5, 5),
            current_state="AGRUPANDO",
        )
        db.add(new_char)
        db.flush() # Garante que o new_char.id seja gerado para usar abaixo.
        # Adiciona os atributos iniciais para o novo personagem.
        db.add(
            models.CharacterAttribute(
                character_id=new_char.id, attribute_name="Fome", attribute_value=0
            )
        )
        db.add(
            models.CharacterAttribute(
                character_id=new_char.id,
                attribute_name="ComidaParaReproducao",
                attribute_value=0,
            )
        )
        db.add(
            models.EventLog(
                world_id=world.id,
                event_type="NASCIMENTO",
                description=f"Um(a) novo(a) {character.species.name}, '{new_name}', nasceu no clã {character.clan.name}.",
                primary_char_id=new_char.id,
                secondary_char_id=character.id,
            )
        )
        return True
    return False


def get_clan_goal_position(db: Session, clan_id: int):
    """
    Determina o ponto de interesse atual de um clã.
    A prioridade é:
    1. O centro de um território que precisa ser conquistado para uma missão.
    2. O centro do território natal do clã.
    Retorna uma tupla (x, y) ou None se não houver um objetivo claro.
    """
    mission = get_clan_active_mission(db, clan_id)
    objective = mission and next(
        (obj for obj in mission.objectives if not obj.is_complete), None
    )

    if objective:
        # Se o objetivo for conquistar um território, o alvo é o centro desse território.
        if objective.objective_type == "CONQUER_TERRITORY":
            territory = db.query(models.Territory).get(objective.target_territory_id)
            if territory:
                return (
                    (territory.start_x + territory.end_x) / 2,
                    (territory.start_y + territory.end_y) / 2,
                )
        # Se o objetivo for coletar recursos, não há um ponto de encontro fixo para o clã.
        elif objective.objective_type == "GATHER_RESOURCE":
            return None

    # Se não houver missão, o objetivo é o território natal do clã.
    home_territory = db.query(models.Territory).filter_by(owner_clan_id=clan_id).first()
    if home_territory:
        return (
            (home_territory.start_x + home_territory.end_x) / 2,
            (home_territory.start_y + home_territory.end_y) / 2,
        )

    return None


# --- Motor Principal da Simulação ---
def process_tick(db: Session, world_id: int):
    """
    Executa um único passo (tick) da simulação para todos os personagens.
    Este é o coração da IA, onde cada personagem percebe o ambiente, toma uma decisão e age.
    """
    # Carrega todos os personagens do mundo de uma vez para otimização.
    all_characters = (
        db.query(models.Character)
        .filter_by(world_id=world_id)
        .options(
            joinedload(models.Character.species), joinedload(models.Character.clan)
        )
        .all()
    )
    world = db.query(models.World).get(world_id)
    if not world:
        return

    # Mapeia IDs de personagens para objetos para acesso rápido.
    character_map = {char.id: char for char in all_characters}
    characters_to_delete_ids = set()
    # Pré-calcula os objetivos de cada clã para evitar consultas repetidas no loop.
    clan_goals = {
        clan.id: get_clan_goal_position(db, clan.id)
        for clan in db.query(models.Clan).filter_by(world_id=world_id).all()
    }

    # Função auxiliar para simplificar a chamada da função de relacionamento.
    def get_rel(char1, char2):
        return get_effective_relationship(db, char1, char2)

    # Loop principal: processa cada personagem.
    for char in all_characters:
        if char.id in characters_to_delete_ids:
            continue
        # 1. ATUALIZAÇÃO DE NECESSIDADES BÁSICAS
        # A fome aumenta e pode causar morte.
        if update_character_needs(db, char, world):
            characters_to_delete_ids.add(char.id)
            db.expunge(char) # Remove da sessão para evitar processamento adicional.
            continue

        valid_targets = [
            c for c in all_characters if c.id not in characters_to_delete_ids
        ]

        # 2. PERCEPÇÃO
        # O personagem "olha" ao redor em busca do inimigo mais próximo.
        nearest_enemy = find_nearest_character_by_relationship(
            char, valid_targets, get_rel, "ENEMY"
        )
        is_under_threat = False
        # Ameaça é definida como um inimigo que está dentro do território do clã do personagem.
        if nearest_enemy:
            enemy_territory = get_territory_at_position(
                db, world_id, nearest_enemy.position_x, nearest_enemy.position_y
            )
            if (
                enemy_territory
                and char.clan_id
                and enemy_territory.owner_clan_id == char.clan_id
            ):
                is_under_threat = True

        # 3. DECISÃO (HIERARQUIA DE PRIORIDADES)
        # O personagem decide o que fazer com base na situação. A ordem aqui é importante.
        life_percentage = char.current_health / char.species.base_health
        # PRIORIDADE 1: Sobrevivência. Se estiver ameaçado e com pouca vida, fuja.
        if is_under_threat and life_percentage < FLEE_HEALTH_PERCENTAGE:
            char.current_state = "FUGINDO"
            char.target_character_id = nearest_enemy.id
        # PRIORIDADE 2: Combate. Se estiver ameaçado mas com vida suficiente, ataque.
        elif is_under_threat:
            char.current_state = "ATACANDO_INIMIGO"
            char.target_character_id = nearest_enemy.id
        # PRIORIDADE 3: Necessidades. Se não houver ameaça, verifique a fome.
        else:
            hunger_val = (
                db.query(models.CharacterAttribute.attribute_value)
                .filter_by(character_id=char.id, attribute_name="Fome")
                .scalar()
                or 0
            )
            # Se a fome passar do limite, procure comida.
            if hunger_val > HUNGER_THRESHOLD:
                # Tenta comer do inventário primeiro.
                if consume_food_from_inventory(db, char, world):
                    # Se comer, acumula recurso para reprodução.
                    food_attr = (
                        db.query(models.CharacterAttribute)
                        .filter_by(
                            character_id=char.id, attribute_name="ComidaParaReproducao"
                        )
                        .first()
                    )
                    if food_attr:
                        food_attr.attribute_value += HUNGER_REDUCTION_PER_FOOD
                    # Tenta se reproduzir. Se não, volta a agrupar.
                    if not process_reproduction(db, char, world):
                        char.current_state = "AGRUPANDO"
                else:
                    # Se não tem comida no inventário, entra no estado de busca.
                    char.current_state = "BUSCANDO_COMIDA"
            else:
                # PRIORIDADE 4: Padrão. Se não há ameaça e não está com fome, agrupe-se com amigos ou vá para o objetivo do clã.
                char.current_state = "AGRUPANDO"

        # 4. EXECUÇÃO DA AÇÃO
        # Com base no estado decidido, executa a ação correspondente.
        if char.current_state == "FUGINDO":
            target = character_map.get(char.target_character_id)
            if target:
                move_away_from_target(char, target, world)
            else:
                char.current_state = "AGRUPANDO" # Se o alvo sumiu, para de fugir.

        elif char.current_state == "ATACANDO_INIMIGO":
            target = character_map.get(char.target_character_id)
            if (
                target
                and target.id not in characters_to_delete_ids
                and get_rel(char, target) == "ENEMY"
            ):
                result = process_attacking_state(
                    db,
                    char,
                    target,
                    world,
                    db.query(models.Species).filter_by(name="Zumbi").first(),
                )
                if result == "KILLED":
                    characters_to_delete_ids.add(target.id)
                    db.expunge(target)
            else:
                char.current_state = "AGRUPANDO" # Se o alvo morreu ou não é mais inimigo, para de atacar.

        elif char.current_state == "BUSCANDO_COMIDA":
            target_node = find_nearest_resource_node(
                db, char, resource_category="COMIDA"
            )
            if target_node:
                # Move-se em direção ao nó de comida.
                moved = move_towards_position(
                    char,
                    target_node.position_x,
                    target_node.position_y,
                    world,
                    GATHER_RANGE,
                )
                # Se não se moveu, significa que já está no alcance para coletar.
                if not moved:
                    inventory_item = (
                        db.query(models.CharacterInventory)
                        .filter_by(
                            character_id=char.id,
                            resource_type_id=target_node.resource_type_id,
                        )
                        .first()
                    )
                    # Adiciona o recurso ao inventário.
                    if inventory_item:
                        inventory_item.quantity += 1
                    else:
                        db.add(
                            models.CharacterInventory(
                                character_id=char.id,
                                resource_type_id=target_node.resource_type_id,
                                quantity=1,
                            )
                        )
                    target_node.quantity -= 1
                    if target_node.quantity <= 0:
                        target_node.is_depleted = True
                    char.current_state = "AGRUPANDO" # Após coletar, volta ao estado de agrupamento.
            else:
                # Se não encontrar comida, perambula.
                process_wandering_state(char, world)

        elif char.current_state == "AGRUPANDO":
            group_center = find_group_center(char, valid_targets, get_rel)
            clan_goal = clan_goals.get(char.clan_id)

            # Verifica se há uma missão de coleta ativa.
            mission = get_clan_active_mission(db, char.clan_id)
            objective = mission and next(
                (obj for obj in mission.objectives if not obj.is_complete), None
            )
            # Se a missão for de coleta, o objetivo do clã se torna o recurso mais próximo.
            if objective and objective.objective_type == "GATHER_RESOURCE":
                gather_node = find_nearest_resource_node(
                    db, char, resource_id=objective.target_resource_id
                )
                if gather_node:
                    clan_goal = (gather_node.position_x, gather_node.position_y)

            # O personagem se move para o centro do grupo, se houver um. Caso contrário, para o objetivo do clã.
            target_pos = group_center if group_center else clan_goal

            if target_pos:
                move_towards_position(
                    char,
                    target_pos[0],
                    target_pos[1],
                    world,
                    GROUPING_DISTANCE if group_center else GATHER_RANGE,
                )
            else:
                # Se não tiver amigos por perto nem objetivo de clã, perambula.
                process_wandering_state(char, world)

    # 5. LIMPEZA
    # Remove todos os personagens marcados para deleção do banco de dados.
    if characters_to_delete_ids:
        db.query(models.Character).filter(
            models.Character.id.in_(characters_to_delete_ids)
        ).delete(synchronize_session=False)

    # Verifica se alguma missão foi concluída neste tick.
    check_and_update_mission_progress(db, world_id)
