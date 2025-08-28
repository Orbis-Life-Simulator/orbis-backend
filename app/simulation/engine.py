import math
import random
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from ..database import models

# --- Constantes da Simulação ---
VISION_RANGE = 100.0
MOVE_SPEED = 5.0
ATTACK_RANGE = 10.0
GATHER_RANGE = 15.0
GROUPING_DISTANCE = 50.0

# --- Constantes de Necessidades ---
HUNGER_INCREASE_RATE = 0.5
HUNGER_THRESHOLD = 60
MAX_HUNGER = 100
STARVATION_DAMAGE = 2
HUNGER_REDUCTION_PER_FOOD = 50

# --- Funções Auxiliares de IA ---
def get_effective_relationship(db: Session, char1: models.Character, char2: models.Character) -> str:
    if char1.id == char2.id: return "FRIEND"
    zombie_species = db.query(models.Species).filter_by(name="Zumbi").first()
    if zombie_species:
        is_char1_zombie = char1.species_id == zombie_species.id
        is_char2_zombie = char2.species_id == zombie_species.id
        if is_char1_zombie and is_char2_zombie: return "FRIEND"
        if is_char1_zombie or is_char2_zombie: return "ENEMY"
    if char1.clan_id and char2.clan_id:
        if char1.clan_id == char2.clan_id: return "FRIEND"
        clan_rel = db.query(models.ClanRelationship).filter(or_((models.ClanRelationship.clan_a_id == char1.clan_id) & (models.ClanRelationship.clan_b_id == char2.clan_id),(models.ClanRelationship.clan_a_id == char2.clan_id) & (models.ClanRelationship.clan_b_id == char1.clan_id))).first()
        if clan_rel:
            if clan_rel.relationship_type == "WAR": return "ENEMY"
            if clan_rel.relationship_type == "ALLIANCE": return "FRIEND"
    species_rel = db.query(models.SpeciesRelationship).filter(or_((models.SpeciesRelationship.species_a_id == char1.species_id) & (models.SpeciesRelationship.species_b_id == char2.species_id),(models.SpeciesRelationship.species_a_id == char2.species_id) & (models.SpeciesRelationship.species_b_id == char1.species_id))).first()
    if species_rel: return species_rel.relationship_type
    return "INDIFFERENT"


def find_nearest_character_by_relationship(origin_char: models.Character, all_chars: list[models.Character], relationship_func, target_relationship: str):
    nearest_char, min_dist_sq = None, VISION_RANGE ** 2
    for target_char in all_chars:
        if origin_char.id == target_char.id: continue
        if relationship_func(origin_char, target_char) == target_relationship:
            dist_sq = (target_char.position_x - origin_char.position_x)**2 + (target_char.position_y - origin_char.position_y)**2
            if dist_sq < min_dist_sq:
                min_dist_sq, nearest_char = dist_sq, target_char
    return nearest_char


def find_group_center(origin_char: models.Character, all_chars: list[models.Character], relationship_func):
    friends_positions = []
    for other_char in all_chars:
        if origin_char.id != other_char.id:
            dist_sq = (other_char.position_x - origin_char.position_x)**2 + (other_char.position_y - origin_char.position_y)**2
            if dist_sq < VISION_RANGE ** 2 and relationship_func(origin_char, other_char) == "FRIEND":
                friends_positions.append((other_char.position_x, other_char.position_y))
    if not friends_positions: return None
    avg_x = sum(pos[0] for pos in friends_positions) / len(friends_positions)
    avg_y = sum(pos[1] for pos in friends_positions) / len(friends_positions)
    return (avg_x, avg_y)


def find_nearest_territory_with_resource(db: Session, character: models.Character, resource_category: str = None, resource_id: int = None):
    query = db.query(models.Territory).join(models.TerritoryResource)
    if resource_id:
        query = query.filter(models.TerritoryResource.resource_type_id == resource_id)
    elif resource_category:
        query = query.join(models.ResourceType).filter(models.ResourceType.category == resource_category)
    
    potential_sources = query.all()
    nearest_source, min_dist_sq = None, float('inf')
    for source in potential_sources:
        center_x, center_y = (source.start_x + source.end_x) / 2, (source.start_y + source.end_y) / 2
        dist_sq = (center_x - character.position_x)**2 + (center_y - character.position_y)**2
        if dist_sq < min_dist_sq:
            min_dist_sq, nearest_source = dist_sq, source
    return nearest_source


def move_towards_position(character: models.Character, pos_x: float, pos_y: float, world: models.World, stop_distance: float):
    direction_x, direction_y = pos_x - character.position_x, pos_y - character.position_y
    distance = math.sqrt(direction_x**2 + direction_y**2)
    if distance < stop_distance or distance == 0: return False # Retorna False se não se moveu
    norm_x, norm_y = direction_x / distance, direction_y / distance
    new_x, new_y = character.position_x + norm_x * MOVE_SPEED, character.position_y + norm_y * MOVE_SPEED
    character.position_x, character.position_y = max(0, min(world.map_width, new_x)), max(0, min(world.map_height, new_y))
    return True # Retorna True se se moveu


def move_towards_target(character: models.Character, target: models.Character, world: models.World):
    return move_towards_position(character, target.position_x, target.position_y, world, ATTACK_RANGE)


def consume_food_from_inventory(db: Session, character: models.Character, world: models.World):
    food_item = db.query(models.CharacterInventory).join(models.ResourceType).filter(models.CharacterInventory.character_id == character.id, models.ResourceType.category == 'COMIDA').first()
    if food_item:
        food_item.quantity -= 1
        hunger_attr = db.query(models.CharacterAttribute).filter_by(character_id=character.id, attribute_name="Fome").first()
        if hunger_attr:
            hunger_attr.attribute_value = max(0, hunger_attr.attribute_value - HUNGER_REDUCTION_PER_FOOD)
        if food_item.quantity <= 0: db.delete(food_item)
        return True
    return False


def process_wandering_state(character: models.Character, world: models.World):
    new_dx, new_dy = random.uniform(-MOVE_SPEED, MOVE_SPEED), random.uniform(-MOVE_SPEED, MOVE_SPEED)
    character.position_x = max(0, min(world.map_width, character.position_x + new_dx))
    character.position_y = max(0, min(world.map_height, character.position_y + new_dy))


def update_character_needs(db: Session, character: models.Character, world: models.World) -> bool:
    hunger_attr = db.query(models.CharacterAttribute).filter_by(character_id=character.id, attribute_name="Fome").first()
    if not hunger_attr:
        hunger_attr = models.CharacterAttribute(character_id=character.id, attribute_name="Fome", attribute_value=0); db.add(hunger_attr)
    hunger_attr.attribute_value += HUNGER_INCREASE_RATE
    if hunger_attr.attribute_value >= MAX_HUNGER:
        character.current_health -= STARVATION_DAMAGE
        if character.current_health <= 0:
            db.add(models.EventLog(world_id=world.id, event_type="MORTE_FOME", description=f"'{character.name}' morreu de fome.", primary_char_id=character.id))
            return True
    return False


def process_attacking_state(db: Session, attacker: models.Character, target: models.Character, world: models.World, zombie_species: models.Species | None) -> str:
    if not move_towards_target(attacker, target, world):
        damage = attacker.species.base_strength
        target.current_health -= damage
        db.add(models.EventLog(world_id=world.id, event_type="ATAQUE", description=f"'{attacker.name}' atacou '{target.name}' por {damage} de dano. Vida: {target.current_health}", primary_char_id=attacker.id, secondary_char_id=target.id))
        if target.current_health <= 0:
            attacker.current_state, attacker.target_character_id = "AGRUPANDO", None
            if zombie_species and attacker.species_id == zombie_species.id:
                target.name, target.species_id, target.clan_id, target.current_health, target.current_state = f"Zumbi {target.name}", zombie_species.id, None, zombie_species.base_health, "AGRUPANDO"
                db.add(models.EventLog(world_id=world.id, event_type="TRANSFORMACAO_ZUMBI", description=f"'{target.name}' foi transformado.", primary_char_id=target.id, secondary_char_id=attacker.id))
                return "TRANSFORMED"
            else:
                db.add(models.EventLog(world_id=world.id, event_type="MORTE", description=f"'{target.name}' foi morto por '{attacker.name}'.", primary_char_id=target.id, secondary_char_id=attacker.id))
                return "KILLED"
    return "ALIVE"


def get_clan_active_mission(db: Session, clan_id: int):
    if not clan_id: return None
    return db.query(models.Mission).filter(models.Mission.assignee_clan_id == clan_id, models.Mission.status == "ATIVA").first()


def check_and_update_mission_progress(db: Session, world_id: int):
    active_missions = db.query(models.Mission).filter_by(world_id=world_id, status="ATIVA").all()
    for mission in active_missions:
        all_objectives_complete = True
        for obj in mission.objectives:
            if obj.is_complete: continue
            if obj.objective_type == "GATHER_RESOURCE":
                total = db.query(func.sum(models.CharacterInventory.quantity)).join(models.Character).filter(models.Character.clan_id == mission.assignee_clan_id, models.CharacterInventory.resource_type_id == obj.target_resource_id).scalar() or 0
                if total >= obj.target_quantity: obj.is_complete = True
            elif obj.objective_type == "CONQUER_TERRITORY":
                territory = db.query(models.Territory).get(obj.target_territory_id)
                if territory:
                    members_in_territory = db.query(models.Character).filter(models.Character.clan_id == mission.assignee_clan_id, models.Character.position_x.between(territory.start_x, territory.end_x), models.Character.position_y.between(territory.start_y, territory.end_y)).count()
                    total_members = db.query(models.Character).filter_by(clan_id=mission.assignee_clan_id).count()
                    if total_members > 0 and (members_in_territory / total_members) > 0.5:
                        obj.is_complete, territory.owner_clan_id = True, mission.assignee_clan_id
            if not obj.is_complete: all_objectives_complete = False
        if all_objectives_complete: mission.status = "CONCLUÍDA"


# --- Motor Principal da Simulação ---
def process_tick(db: Session, world_id: int):
    all_characters = db.query(models.Character).filter_by(world_id=world_id).options(db.joinedload(models.Character.species)).all()
    world = db.query(models.World).get(world_id)
    if not world: return

    zombie_species = db.query(models.Species).filter_by(name="Zumbi").first()
    character_map = {char.id: char for char in all_characters}
    characters_to_delete_ids = set()

    def get_rel(char1, char2): return get_effective_relationship(db, char1, char2)

    for char in all_characters:
        if char.id in characters_to_delete_ids: continue
        if update_character_needs(db, char, world):
            characters_to_delete_ids.add(char.id); continue

        # --- LÓGICA DE DECISÃO ---
        valid_targets = [c for c in all_characters if c.id not in characters_to_delete_ids]
        nearest_enemy = find_nearest_character_by_relationship(char, valid_targets, get_rel, "ENEMY")
        if nearest_enemy:
            char.current_state, char.target_character_id = "ATACANDO_INIMIGO", nearest_enemy.id
        else:
            hunger_val = db.query(models.CharacterAttribute.attribute_value).filter_by(character_id=char.id, attribute_name="Fome").scalar() or 0
            if hunger_val > HUNGER_THRESHOLD:
                if not consume_food_from_inventory(db, char, world):
                    char.current_state = "BUSCANDO_COMIDA"
            else:
                mission = get_clan_active_mission(db, char.clan_id)
                if mission and next((obj for obj in mission.objectives if not obj.is_complete), None):
                    char.current_state = "EXECUTANDO_MISSAO"
                else:
                    char.current_state = "AGRUPANDO"
        
        # --- EXECUÇÃO DA AÇÃO ---
        if char.current_state == "ATACANDO_INIMIGO":
            target = character_map.get(char.target_character_id)
            if target and target.id not in characters_to_delete_ids and get_rel(char, target) == "ENEMY":
                result = process_attacking_state(db, char, target, world, zombie_species)
                if result == "KILLED": characters_to_delete_ids.add(target.id)
            else:
                char.current_state, char.target_character_id = "AGRUPANDO", None
        
        elif char.current_state in ["BUSCANDO_COMIDA", "EXECUTANDO_MISSAO"]:
            resource_id, category = None, "COMIDA"
            if char.current_state == "EXECUTANDO_MISSAO":
                mission = get_clan_active_mission(db, char.clan_id)
                objective = next((obj for obj in mission.objectives if not obj.is_complete), None)
                if objective and objective.objective_type == "GATHER_RESOURCE":
                    resource_id, category = objective.target_resource_id, None
                elif objective and objective.objective_type == "CONQUER_TERRITORY":
                    territory = db.query(models.Territory).get(objective.target_territory_id)
                    if territory: move_towards_position(char, (territory.start_x + territory.end_x) / 2, (territory.start_y + territory.end_y) / 2, world, 0)
                    continue # Pula para o próximo personagem após mover
            
            source_territory = find_nearest_territory_with_resource(db, char, category, resource_id)
            if source_territory:
                moved = move_towards_position(char, (source_territory.start_x + source_territory.end_x) / 2, (source_territory.start_y + source_territory.end_y) / 2, world, GATHER_RANGE)
                if not moved: # Chegou ao destino, hora de coletar
                    resource_link = db.query(models.TerritoryResource).filter_by(territory_id=source_territory.id, resource_type_id=(resource_id or db.query(models.ResourceType).filter_by(category=category).first().id)).first()
                    if resource_link:
                        inventory_item = db.query(models.CharacterInventory).filter_by(character_id=char.id, resource_type_id=resource_link.resource_type_id).first()
                        if inventory_item: inventory_item.quantity += 1
                        else: db.add(models.CharacterInventory(character_id=char.id, resource_type_id=resource_link.resource_type_id, quantity=1))
                        char.current_state = "AGRUPANDO"
            else:
                process_wandering_state(char, world)

        elif char.current_state == "AGRUPANDO":
            group_center = find_group_center(char, valid_targets, get_rel)
            if group_center:
                move_towards_position(char, group_center[0], group_center[1], world, GROUPING_DISTANCE)
            else:
                process_wandering_state(char, world)

    if characters_to_delete_ids:
        db.query(models.Character).filter(models.Character.id.in_(characters_to_delete_ids)).delete(synchronize_session=False)
    
    check_and_update_mission_progress(db, world_id)
