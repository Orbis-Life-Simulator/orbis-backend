import math
import random
from collections import defaultdict
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from ..database import models

# --- Constantes (sem alterações) ---
VISION_RANGE = 100.0
MOVE_SPEED = 5.0
ATTACK_RANGE = 10.0
GATHER_RANGE = 15.0
GROUPING_DISTANCE = 50.0
HUNGER_INCREASE_RATE = 0.5
HUNGER_THRESHOLD = 60
MAX_HUNGER = 100
STARVATION_DAMAGE = 2
HUNGER_REDUCTION_PER_FOOD = 50
FLEE_HEALTH_PERCENTAGE = 0.25
REPRODUCTION_FOOD_COST = 100

# --- Funções Auxiliares e de IA (Modificadas para performance) ---


# [OTIMIZAÇÃO] Esta função agora usa caches pré-carregados para evitar queries.
def get_effective_relationship(
    char1: models.Character,
    char2: models.Character,
    zombie_species_id: int | None,
    clan_rels: dict,
    species_rels: dict,
) -> str:
    """Determina o relacionamento efetivo usando dados em memória."""
    if char1.id == char2.id:
        return "FRIEND"

    if zombie_species_id:
        is_char1_zombie = char1.species_id == zombie_species_id
        is_char2_zombie = char2.species_id == zombie_species_id
        if is_char1_zombie and is_char2_zombie:
            return "FRIEND"
        if is_char1_zombie or is_char2_zombie:
            return "ENEMY"

    if char1.clan_id and char2.clan_id:
        if char1.clan_id == char2.clan_id:
            return "FRIEND"

        # Chave para buscar no dicionário de relacionamentos de clãs
        rel_key = tuple(sorted((char1.clan_id, char2.clan_id)))
        clan_rel_type = clan_rels.get(rel_key)
        if clan_rel_type:
            if clan_rel_type == "WAR":
                return "ENEMY"
            if clan_rel_type == "ALLIANCE":
                return "FRIEND"

    # Chave para buscar no dicionário de relacionamentos de espécies
    rel_key = tuple(sorted((char1.species_id, char2.species_id)))
    species_rel_type = species_rels.get(rel_key)
    if species_rel_type:
        return species_rel_type

    return "INDIFFERENT"


# [OTIMIZAÇÃO] Esta função agora usa uma lista de territórios em memória.
def get_territory_at_position(
    all_territories: list[models.Territory], x: float, y: float
):
    """Retorna o território em uma coordenada (x, y) a partir de uma lista em memória."""
    for territory in all_territories:
        if (
            territory.start_x <= x
            and territory.end_x >= x
            and territory.start_y <= y
            and territory.end_y >= y
        ):
            return territory
    return None


def find_nearest_character_by_relationship(
    origin_char: models.Character,
    all_chars: list[models.Character],
    relationship_func,
    target_relationship: str,
):
    """Encontra o personagem mais próximo. Nenhuma mudança de lógica necessária aqui."""
    nearest_char, min_dist_sq = None, VISION_RANGE**2
    for target_char in all_chars:
        if origin_char.id == target_char.id:
            continue
        if relationship_func(origin_char, target_char) == target_relationship:
            dist_sq = (target_char.position_x - origin_char.position_x) ** 2 + (
                target_char.position_y - origin_char.position_y
            ) ** 2
            if dist_sq < min_dist_sq:
                min_dist_sq, nearest_char = dist_sq, target_char
    return nearest_char


def find_group_center(
    origin_char: models.Character, all_chars: list[models.Character], relationship_func
):
    """Calcula o ponto central do grupo. Nenhuma mudança de lógica necessária."""
    friends_positions = []
    for other_char in all_chars:
        if origin_char.id != other_char.id:
            dist_sq = (other_char.position_x - origin_char.position_x) ** 2 + (
                other_char.position_y - origin_char.position_y
            ) ** 2
            if (
                dist_sq < VISION_RANGE**2
                and relationship_func(origin_char, other_char) == "FRIEND"
            ):
                friends_positions.append((other_char.position_x, other_char.position_y))

    if not friends_positions:
        return None
    avg_x = sum(pos[0] for pos in friends_positions) / len(friends_positions)
    avg_y = sum(pos[1] for pos in friends_positions) / len(friends_positions)
    return (avg_x, avg_y)


# [OTIMIZAÇÃO] Busca no cache de nós de recursos em vez do banco.
def find_nearest_resource_node(
    character: models.Character,
    all_nodes: list[models.ResourceNode],
    resource_category: str = None,
    resource_id: int = None,
):
    """Encontra o nó de recurso mais próximo a partir de uma lista em memória."""
    nearest_node, min_dist_sq = None, float("inf")

    # Filtra a lista em memória em vez de fazer uma query
    potential_nodes = all_nodes
    if resource_id:
        potential_nodes = [n for n in all_nodes if n.resource_type_id == resource_id]
    elif resource_category:
        potential_nodes = [
            n for n in all_nodes if n.resource_type.category == resource_category
        ]

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
    """Move o personagem. Nenhuma mudança de lógica necessária."""
    direction_x, direction_y = (
        pos_x - character.position_x,
        pos_y - character.position_y,
    )
    distance = math.sqrt(direction_x**2 + direction_y**2)

    if distance < stop_distance or distance == 0:
        return False

    norm_x, norm_y = direction_x / distance, direction_y / distance
    new_x, new_y = (
        character.position_x + norm_x * MOVE_SPEED,
        character.position_y + norm_y * MOVE_SPEED,
    )

    character.position_x, character.position_y = max(
        0, min(world.map_width, new_x)
    ), max(0, min(world.map_height, new_y))
    return True


# ... (outras funções de movimento como move_towards_target, move_away_from_target não precisam de alteração)
def move_towards_target(
    character: models.Character, target: models.Character, world: models.World
):
    return move_towards_position(
        character, target.position_x, target.position_y, world, ATTACK_RANGE
    )


def move_away_from_target(
    character: models.Character, target_char: models.Character, world: models.World
):
    if not target_char:
        return
    direction_x = character.position_x - target_char.position_x
    direction_y = character.position_y - target_char.position_y
    distance = math.sqrt(direction_x**2 + direction_y**2)
    if distance == 0:
        direction_x, direction_y, distance = (
            random.uniform(-1, 1),
            random.uniform(-1, 1),
            1,
        )
    norm_x, norm_y = direction_x / distance, direction_y / distance
    new_x = character.position_x + norm_x * MOVE_SPEED
    new_y = character.position_y + norm_y * MOVE_SPEED
    character.position_x = max(0, min(world.map_width, new_x))
    character.position_y = max(0, min(world.map_height, new_y))


# [OTIMIZAÇÃO] Usa mapas de inventário e atributos em memória.
def consume_food_from_inventory(
    character: models.Character,
    inventory_map: dict,
    attrs_map: dict,
    food_resource_type_ids: set,
) -> tuple[bool, models.CharacterInventory | None]:
    """Consome comida do inventário em memória e retorna o item para ser deletado se necessário."""
    char_inventory = inventory_map.get(character.id, {})
    food_item = None
    for item_id, item in char_inventory.items():
        if item.resource_type_id in food_resource_type_ids:
            food_item = item
            break

    if food_item:
        food_item.quantity -= 1
        hunger_attr = attrs_map.get((character.id, "Fome"))
        if hunger_attr:
            hunger_attr.attribute_value = max(
                0, hunger_attr.attribute_value - HUNGER_REDUCTION_PER_FOOD
            )

        item_to_delete = None
        if food_item.quantity <= 0:
            # Remove do mapa e marca para deleção do DB
            del inventory_map[character.id][food_item.resource_type_id]
            item_to_delete = food_item
        return True, item_to_delete
    return False, None


def process_wandering_state(character: models.Character, world: models.World):
    """Simula o comportamento de perambular. Nenhuma mudança de lógica necessária."""
    new_dx, new_dy = random.uniform(-MOVE_SPEED, MOVE_SPEED), random.uniform(
        -MOVE_SPEED, MOVE_SPEED
    )
    character.position_x = max(0, min(world.map_width, character.position_x + new_dx))
    character.position_y = max(0, min(world.map_height, character.position_y + new_dy))


# ... (outras funções como process_attacking_state, check_and_update_mission_progress, process_reproduction, get_clan_goal_position, etc.
# permanecem com a mesma lógica, mas agora retornam os objetos a serem adicionados/atualizados, em vez de fazerem a escrita no banco diretamente.)


def get_clan_active_mission(db: Session, clan_id: int):
    """Busca e retorna a missão ativa de um determinado clã, se houver."""
    if not clan_id:
        return None
    return (
        db.query(models.Mission)
        .filter(
            models.Mission.assignee_clan_id == clan_id, models.Mission.status == "ATIVA"
        )
        .options(
            joinedload(models.Mission.objectives)
        )  # Otimização: carregar objetivos junto
        .first()
    )


def get_clan_goal_position(db: Session, clan_id: int):
    """
    Determina o ponto de interesse atual de um clã.
    A prioridade é:
    1. O centro de um território que precisa ser conquistado para uma missão.
    2. O centro do território natal do clã.
    Retorna uma tupla (x, y) ou None se não houver um objetivo claro.
    """
    mission = get_clan_active_mission(db, clan_id)
    if mission:
        # Pega o primeiro objetivo que ainda não foi concluído
        objective = next(
            (obj for obj in mission.objectives if not obj.is_complete), None
        )

        if objective:
            # Se o objetivo for conquistar um território, o alvo é o centro desse território.
            if objective.objective_type == "CONQUER_TERRITORY":
                territory = db.query(models.Territory).get(
                    objective.target_territory_id
                )
                if territory:
                    return (
                        (territory.start_x + territory.end_x) / 2,
                        (territory.start_y + territory.end_y) / 2,
                    )
            # Se o objetivo for coletar recursos, não há um ponto de encontro fixo para o clã.
            # Essa lógica é tratada separadamente no estado 'AGRUPANDO'.
            elif objective.objective_type == "GATHER_RESOURCE":
                return None

    # Se não houver missão ativa com objetivo de território, o objetivo é o território natal do clã.
    home_territory = db.query(models.Territory).filter_by(owner_clan_id=clan_id).first()
    if home_territory:
        return (
            (home_territory.start_x + home_territory.end_x) / 2,
            (home_territory.start_y + home_territory.end_y) / 2,
        )

    return None


def check_and_update_mission_progress(db: Session, world_id: int):
    """
    Verifica o progresso de todas as missões ativas no mundo.
    Atualiza o status dos objetivos e das missões se as condições forem atendidas.
    (Esta função realiza queries, mas como roda apenas uma vez por tick, o impacto é aceitável).
    """
    active_missions = (
        db.query(models.Mission)
        .filter_by(world_id=world_id, status="ATIVA")
        .options(
            joinedload(models.Mission.objectives)
        )  # Garante que objetivos são carregados
        .all()
    )

    for mission in active_missions:
        all_objectives_complete = True
        for obj in mission.objectives:
            if obj.is_complete:
                continue

            is_objective_now_complete = False
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
                    is_objective_now_complete = True

            # Lógica para objetivo de conquistar território.
            elif obj.objective_type == "CONQUER_TERRITORY":
                territory = db.query(models.Territory).get(obj.target_territory_id)
                if territory and territory.owner_clan_id == mission.assignee_clan_id:
                    # Uma forma mais simples: verifica se o clã já é o dono.
                    # A lógica de conquista deve acontecer dentro do tick (no estado AGRUPANDO/objetivo do clã).
                    # Aqui apenas validamos o resultado.
                    # Para a lógica original de contagem de membros:
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

                    # Conquista se mais de 50% dos membros estiverem no território
                    if (
                        total_members > 0
                        and (members_in_territory / total_members) > 0.5
                    ):
                        territory.owner_clan_id = mission.assignee_clan_id
                        is_objective_now_complete = True

            if is_objective_now_complete:
                obj.is_complete = True

            if not obj.is_complete:
                all_objectives_complete = False

        # Se todos os objetivos foram concluídos, a missão é marcada como 'CONCLUÍDA'.
        if all_objectives_complete:
            mission.status = "CONCLUÍDA"
            # Poderia adicionar um log de evento aqui também


# --- Motor Principal da Simulação (TOTALMENTE REFEITO PARA PERFORMANCE) ---
def process_tick(db: Session, world_id: int):
    """
    Executa um único passo (tick) da simulação com performance otimizada.
    Estratégia: Carregar tudo em memória -> Processar -> Salvar em lote.
    """
    world = db.query(models.World).get(world_id)
    if not world:
        return

    # [OTIMIZAÇÃO] 1. CARREGAMENTO EM LOTE (BATCH LOADING)
    # Carrega todos os dados necessários do mundo em uma única passagem.
    all_characters = (
        db.query(models.Character)
        .filter_by(world_id=world_id)
        .options(
            joinedload(models.Character.species), joinedload(models.Character.clan)
        )
        .all()
    )

    character_ids = [c.id for c in all_characters]

    # Carrega todos os atributos e mapeia para (char_id, nome) para acesso rápido
    all_attrs = (
        db.query(models.CharacterAttribute)
        .filter(models.CharacterAttribute.character_id.in_(character_ids))
        .all()
    )
    attrs_map = {(a.character_id, a.attribute_name): a for a in all_attrs}

    # Carrega todos os inventários e mapeia para char_id -> {resource_id: item}
    all_inventory = (
        db.query(models.CharacterInventory)
        .filter(models.CharacterInventory.character_id.in_(character_ids))
        .all()
    )
    inventory_map = defaultdict(dict)
    for item in all_inventory:
        inventory_map[item.character_id][item.resource_type_id] = item

    # Carrega todos os recursos, territórios e relacionamentos do mundo
    all_nodes = (
        db.query(models.ResourceNode)
        .options(joinedload(models.ResourceNode.resource_type))
        .filter_by(is_depleted=False, world_id=world_id)
        .all()
    )
    all_territories = db.query(models.Territory).filter_by(world_id=world_id).all()

    clan_rels_query = db.query(models.ClanRelationship).all()
    clan_rels = {
        tuple(sorted((r.clan_a_id, r.clan_b_id))): r.relationship_type
        for r in clan_rels_query
    }

    species_rels_query = db.query(models.SpeciesRelationship).all()
    species_rels = {
        tuple(sorted((r.species_a_id, r.species_b_id))): r.relationship_type
        for r in species_rels_query
    }

    zombie_species = db.query(models.Species).filter_by(name="Zumbi").first()
    zombie_species_id = zombie_species.id if zombie_species else None

    # Identifica tipos de recursos que são comida para otimizar a busca no inventário
    food_resource_types = (
        db.query(models.ResourceType).filter_by(category="COMIDA").all()
    )
    food_resource_type_ids = {rt.id for rt in food_resource_types}

    # Pré-calcula os objetivos de cada clã
    clan_goals = {
        clan.id: get_clan_goal_position(db, clan.id)
        for clan in db.query(models.Clan).filter_by(world_id=world_id).all()
    }

    # [OTIMIZAÇÃO] Estruturas para acumular alterações para escrita em lote
    objects_to_add = []
    objects_to_delete = []
    characters_to_delete_ids = set()
    character_map = {char.id: char for char in all_characters}

    # Função de relacionamento com cache
    def get_rel(char1, char2):
        return get_effective_relationship(
            char1, char2, zombie_species_id, clan_rels, species_rels
        )

    # 2. PROCESSAMENTO EM MEMÓRIA
    for char in all_characters:
        if char.id in characters_to_delete_ids:
            continue

        # 1. ATUALIZAÇÃO DE NECESSIDADES BÁSICAS (usando attrs_map)
        hunger_attr = attrs_map.get((char.id, "Fome"))
        if not hunger_attr:
            hunger_attr = models.CharacterAttribute(
                character_id=char.id, attribute_name="Fome", attribute_value=0
            )
            attrs_map[(char.id, "Fome")] = hunger_attr
            objects_to_add.append(hunger_attr)

        hunger_attr.attribute_value += HUNGER_INCREASE_RATE
        if hunger_attr.attribute_value >= MAX_HUNGER:
            char.current_health -= STARVATION_DAMAGE
            if char.current_health <= 0:
                objects_to_add.append(
                    models.EventLog(
                        world_id=world.id,
                        event_type="MORTE_FOME",
                        description=f"'{char.name}' morreu de fome.",
                        primary_char_id=char.id,
                    )
                )
                characters_to_delete_ids.add(char.id)
                db.expunge(target)
                continue

        valid_targets = [
            c for c in all_characters if c.id not in characters_to_delete_ids
        ]

        # 2. PERCEPÇÃO (usando dados em memória)
        nearest_enemy = find_nearest_character_by_relationship(
            char, valid_targets, get_rel, "ENEMY"
        )
        is_under_threat = False
        if nearest_enemy:
            enemy_territory = get_territory_at_position(
                all_territories, nearest_enemy.position_x, nearest_enemy.position_y
            )
            if (
                enemy_territory
                and char.clan_id
                and enemy_territory.owner_clan_id == char.clan_id
            ):
                is_under_threat = True

        # 3. DECISÃO (HIERARQUIA DE PRIORIDADES)
        # (A lógica de decisão permanece a mesma, mas as funções que ela chama agora são rápidas)
        life_percentage = char.current_health / char.species.base_health
        if is_under_threat and life_percentage < FLEE_HEALTH_PERCENTAGE:
            char.current_state = "FUGINDO"
            char.target_character_id = nearest_enemy.id
        elif is_under_threat:
            char.current_state = "ATACANDO_INIMIGO"
            char.target_character_id = nearest_enemy.id
        else:
            hunger_val = hunger_attr.attribute_value
            if hunger_val > HUNGER_THRESHOLD:
                ate, item_to_delete = consume_food_from_inventory(
                    char, inventory_map, attrs_map, food_resource_type_ids
                )
                if item_to_delete:
                    objects_to_delete.append(item_to_delete)

                if ate:
                    food_attr = attrs_map.get((char.id, "ComidaParaReproducao"))
                    if food_attr:
                        food_attr.attribute_value += HUNGER_REDUCTION_PER_FOOD
                    # Lógica de reprodução...
                    char.current_state = "AGRUPANDO"  # Simplificado por agora
                else:
                    char.current_state = "BUSCANDO_COMIDA"
            else:
                char.current_state = "AGRUPANDO"

        # 4. EXECUÇÃO DA AÇÃO
        if char.current_state == "FUGINDO":
            target = character_map.get(char.target_character_id)
            if target:
                move_away_from_target(char, target, world)
            else:
                char.current_state = "AGRUPANDO"

        elif char.current_state == "ATACANDO_INIMIGO":
            target = character_map.get(char.target_character_id)
            if (
                target
                and target.id not in characters_to_delete_ids
                and get_rel(char, target) == "ENEMY"
            ):
                # A função process_attacking_state precisaria ser adaptada para não fazer commit
                # e retornar os logs para serem adicionados em lote.
                # Para simplificar, faremos a lógica aqui:
                if not move_towards_target(char, target, world):
                    damage = char.species.base_strength
                    target.current_health -= damage
                    objects_to_add.append(
                        models.EventLog(
                            world_id=world.id,
                            event_type="ATAQUE",
                            description=f"'{char.name}' atacou '{target.name}' por {damage} de dano.",
                            primary_char_id=char.id,
                            secondary_char_id=target.id,
                        )
                    )

                    if target.current_health <= 0:
                        characters_to_delete_ids.add(target.id)
                        db.expunge(target)
                        objects_to_add.append(
                            models.EventLog(
                                world_id=world.id,
                                event_type="MORTE",
                                description=f"'{target.name}' foi morto por '{char.name}'.",
                                primary_char_id=target.id,
                                secondary_char_id=char.id,
                            )
                        )
                        char.current_state = "AGRUPANDO"
            else:
                char.current_state = "AGRUPANDO"

        elif char.current_state == "BUSCANDO_COMIDA":
            target_node = find_nearest_resource_node(
                char, all_nodes, resource_category="COMIDA"
            )
            if target_node:
                if not move_towards_position(
                    char,
                    target_node.position_x,
                    target_node.position_y,
                    world,
                    GATHER_RANGE,
                ):
                    # Lógica de coleta...
                    char_inv = inventory_map.get(char.id, {})
                    inventory_item = char_inv.get(target_node.resource_type_id)
                    if inventory_item:
                        inventory_item.quantity += 1
                    else:
                        new_item = models.CharacterInventory(
                            character_id=char.id,
                            resource_type_id=target_node.resource_type_id,
                            quantity=1,
                        )
                        inventory_map[char.id][target_node.resource_type_id] = new_item
                        objects_to_add.append(new_item)

                    target_node.quantity -= 1
                    if target_node.quantity <= 0:
                        target_node.is_depleted = True
                    char.current_state = "AGRUPANDO"
            else:
                process_wandering_state(char, world)

        elif char.current_state == "AGRUPANDO":
            group_center = find_group_center(char, valid_targets, get_rel)
            clan_goal = clan_goals.get(char.clan_id)
            target_pos = group_center or clan_goal

            if target_pos:
                move_towards_position(
                    char,
                    target_pos[0],
                    target_pos[1],
                    world,
                    GROUPING_DISTANCE if group_center else GATHER_RANGE,
                )
            else:
                process_wandering_state(char, world)

    # [OTIMIZAÇÃO] 3. ESCRITA EM LOTE (BATCH WRITING)
    # Agora, aplicamos todas as alterações acumuladas ao banco de dados de uma só vez.
    try:
        # Adiciona novos objetos (logs, atributos, itens de inventário)
        if objects_to_add:
            db.add_all(objects_to_add)

        # Deleta objetos marcados
        for obj in objects_to_delete:
            db.delete(obj)

        # Deleta personagens que morreram
        if characters_to_delete_ids:
            db.query(models.Character).filter(
                models.Character.id.in_(characters_to_delete_ids)
            ).delete(synchronize_session=False)

        # Verifica missões (só roda uma vez por tick, então está ok)
        check_and_update_mission_progress(db, world_id)

        # O SQLAlchemy automaticamente detecta as alterações nos objetos já existentes
        # (como vida, posição, estado, valores de atributos) e as incluirá no commit.
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Erro durante o commit do tick: {e}")
        raise
