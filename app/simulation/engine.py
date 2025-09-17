import math
import random
from collections import defaultdict
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from ..database import models

VISION_RANGE = 100.0
MOVE_SPEED = 5.0
ATTACK_RANGE = 10.0
GATHER_RANGE = 15.0
GROUPING_DISTANCE = 50.0
HUNGER_INCREASE_RATE = 0.5
STARVATION_DAMAGE = 2
ENERGY_REGEN_RATE = 1
REPRODUCTION_FOOD_COST = 100


def get_effective_relationship(
    char1: models.Character,
    char2: models.Character,
    zombie_species_id: int | None,
    clan_rels: dict,
    species_rels: dict,
) -> str:
    if char1.id == char2.id:
        return "FRIEND"
    if zombie_species_id:
        if (char1.species_id == zombie_species_id) and (
            char2.species_id == zombie_species_id
        ):
            return "FRIEND"
        if (char1.species_id == zombie_species_id) or (
            char2.species_id == zombie_species_id
        ):
            return "ENEMY"
    if char1.clan_id and char2.clan_id:
        if char1.clan_id == char2.clan_id:
            return "FRIEND"
        rel_key = tuple(sorted((char1.clan_id, char2.clan_id)))
        clan_rel_type = clan_rels.get(rel_key)
        if clan_rel_type == "WAR":
            return "ENEMY"
        if clan_rel_type == "ALLIANCE":
            return "FRIEND"
    rel_key = tuple(sorted((char1.species_id, char2.species_id)))
    species_rel_type = species_rels.get(rel_key)
    if species_rel_type:
        return species_rel_type
    return "INDIFFERENT"


def get_territory_at_position(
    all_territories: list[models.Territory], x: float, y: float
):
    for territory in all_territories:
        if (
            territory.start_x <= x <= territory.end_x
            and territory.start_y <= y <= territory.end_y
        ):
            return territory
    return None


def find_nearest_character_by_relationship(
    origin_char: models.Character,
    all_chars: list[models.Character],
    relationship_func,
    target_relationship: str,
):
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
    friends_positions = []
    for other_char in all_chars:
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


def find_nearest_resource_node(
    character: models.Character,
    all_nodes: list[models.ResourceNode],
    resource_category: str = None,
    resource_id: int = None,
):
    nearest_node, min_dist_sq = None, float("inf")
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
    direction_x, direction_y = (
        character.position_x - target_char.position_x,
        character.position_y - target_char.position_y,
    )
    distance = math.sqrt(direction_x**2 + direction_y**2)
    if distance == 0:
        direction_x, direction_y, distance = (
            random.uniform(-1, 1),
            random.uniform(-1, 1),
            1,
        )
    norm_x, norm_y = direction_x / distance, direction_y / distance
    new_x, new_y = (
        character.position_x + norm_x * MOVE_SPEED,
        character.position_y + norm_y * MOVE_SPEED,
    )
    character.position_x, character.position_y = max(
        0, min(world.map_width, new_x)
    ), max(0, min(world.map_height, new_y))


def consume_food_from_inventory(
    character: models.Character, inventory_map: dict, food_resource_type_ids: set
) -> tuple[bool, models.CharacterInventory | None]:
    char_inventory = inventory_map.get(character.id, {})
    food_item = None
    for item in char_inventory.values():
        if item.resource_type_id in food_resource_type_ids:
            food_item = item
            break
    if food_item:
        food_item.quantity -= 1
        item_to_delete = None
        if food_item.quantity <= 0:
            del inventory_map[character.id][food_item.resource_type_id]
            item_to_delete = food_item
        return True, item_to_delete
    return False, None


def process_wandering_state(character: models.Character, world: models.World):
    new_dx, new_dy = random.uniform(-MOVE_SPEED, MOVE_SPEED), random.uniform(
        -MOVE_SPEED, MOVE_SPEED
    )
    character.position_x = max(0, min(world.map_width, character.position_x + new_dx))
    character.position_y = max(0, min(world.map_height, character.position_y + new_dy))


def get_clan_goal_position(db: Session, clan_id: int):
    if not clan_id:
        return None
    mission = (
        db.query(models.Mission)
        .filter(
            models.Mission.assignee_clan_id == clan_id, models.Mission.status == "ATIVA"
        )
        .options(joinedload(models.Mission.objectives))
        .first()
    )
    if mission:
        objective = next(
            (obj for obj in mission.objectives if not obj.is_complete), None
        )
        if objective and objective.objective_type == "CONQUER_TERRITORY":
            territory = db.query(models.Territory).get(objective.target_territory_id)
            if territory:
                return (
                    (territory.start_x + territory.end_x) / 2,
                    (territory.start_y + territory.end_y) / 2,
                )
    home_territory = db.query(models.Territory).filter_by(owner_clan_id=clan_id).first()
    if home_territory:
        return (
            (home_territory.start_x + home_territory.end_x) / 2,
            (home_territory.start_y + home_territory.end_y) / 2,
        )
    return None


def check_and_update_mission_progress(db: Session, world_id: int):
    active_missions = (
        db.query(models.Mission)
        .filter_by(world_id=world_id, status="ATIVA")
        .options(joinedload(models.Mission.objectives))
        .all()
    )
    for mission in active_missions:
        all_objectives_complete = True
        for obj in mission.objectives:
            if obj.is_complete:
                continue
            is_objective_now_complete = False
            if obj.objective_type == "GATHER_RESOURCE":
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
            elif obj.objective_type == "CONQUER_TERRITORY":
                territory = db.query(models.Territory).get(obj.target_territory_id)
                if territory and territory.owner_clan_id == mission.assignee_clan_id:
                    is_objective_now_complete = True
            if is_objective_now_complete:
                obj.is_complete = True
            if not obj.is_complete:
                all_objectives_complete = False
        if all_objectives_complete:
            mission.status = "CONCLUÍDA"


def process_tick(db: Session, world_id: int):
    from .behavior_tree import build_character_ai_tree

    world = db.query(models.World).get(world_id)
    if not world:
        return

    all_characters = (
        db.query(models.Character)
        .filter_by(world_id=world_id)
        .options(
            joinedload(models.Character.species), joinedload(models.Character.clan)
        )
        .all()
    )
    character_ids = [c.id for c in all_characters]

    all_inventory = (
        db.query(models.CharacterInventory)
        .filter(models.CharacterInventory.character_id.in_(character_ids))
        .all()
    )
    inventory_map = defaultdict(dict)
    for item in all_inventory:
        inventory_map[item.character_id][item.resource_type_id] = item

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
    food_resource_types = (
        db.query(models.ResourceType).filter_by(category="COMIDA").all()
    )
    food_resource_type_ids = {rt.id for rt in food_resource_types}
    clan_goals = {
        clan.id: get_clan_goal_position(db, clan.id)
        for clan in db.query(models.Clan).filter_by(world_id=world_id).all()
    }

    def get_rel(char1, char2):
        return get_effective_relationship(
            char1, char2, zombie_species_id, clan_rels, species_rels
        )

    world_state = {
        "world": world,
        "all_characters": all_characters,
        "inventory_map": inventory_map,
        "all_nodes": all_nodes,
        "all_territories": all_territories,
        "food_resource_type_ids": food_resource_type_ids,
        "clan_goals": clan_goals,
        "get_rel": get_rel,
    }

    commands = {
        "objects_to_add": [],
        "objects_to_delete": [],
        "characters_to_delete_ids": set(),
    }
    ai_tree = build_character_ai_tree()
    world.current_tick += 1

    for char in all_characters:
        if char.id in commands["characters_to_delete_ids"]:
            continue

        char.idade += 1
        char.fome = int(min(100, char.fome + HUNGER_INCREASE_RATE))

        if char.fome >= 100:
            char.current_health -= STARVATION_DAMAGE
            if char.current_health <= 0:
                commands["objects_to_add"].append(
                    models.EventLog(
                        world_id=world.id,
                        event_type="MORTE_FOME",
                        description=f"'{char.name}' morreu de fome.",
                        primary_char_id=char.id,
                    )
                )
                commands["characters_to_delete_ids"].add(char.id)
                continue

        blackboard = {}

        ai_tree.tick(char, world_state, blackboard, commands)

        if not blackboard.get("enemies_in_range"):
            char.energia = min(100, char.energia + ENERGY_REGEN_RATE)

        char.energia = max(0, char.energia)

    try:
        if commands["objects_to_add"]:
            db.add_all(commands["objects_to_add"])
        for obj in commands["objects_to_delete"]:
            if db.object_session(obj):
                db.delete(obj)
        if commands["characters_to_delete_ids"]:
            db.query(models.Character).filter(
                models.Character.id.in_(commands["characters_to_delete_ids"])
            ).delete(synchronize_session=False)
        check_and_update_mission_progress(db, world_id)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Erro durante o commit do tick: {e}")
        raise
