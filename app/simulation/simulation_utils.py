import math
import random
import uuid
from datetime import datetime, timezone
from pymongo.database import Database
import asyncio

from .constants import *


def get_effective_relationship(
    char1_doc: dict,
    char2_doc: dict,
    zombie_species_id: int | None,
    clan_rels: dict,
    species_rels: dict,
    personal_rels: dict,
) -> str:
    """
    Determina a relação efetiva entre dois personagens, operando com documentos MongoDB.
    A lógica de prioridade (pessoal > zumbi > clã > espécie) é preservada.
    """
    if char1_doc["_id"] == char2_doc["_id"]:
        return "FRIEND"

    personal_rel_key = tuple(sorted((char1_doc["_id"], char2_doc["_id"])))
    personal_relationship = personal_rels.get(personal_rel_key)
    if personal_relationship:
        score = personal_relationship.get("relationship_score", 0)
        if score > 50:
            return "FRIEND"
        if score < -50:
            return "ENEMY"

    char1_species_id = char1_doc["species"]["id"]
    char2_species_id = char2_doc["species"]["id"]
    if zombie_species_id:
        if (
            char1_species_id == zombie_species_id
            and char2_species_id == zombie_species_id
        ):
            return "FRIEND"
        if (
            char1_species_id == zombie_species_id
            or char2_species_id == zombie_species_id
        ):
            return "ENEMY"

    char1_clan = char1_doc.get("clan")
    char2_clan = char2_doc.get("clan")
    if char1_clan and char2_clan:
        if char1_clan["id"] == char2_clan["id"]:
            return "FRIEND"

        clan_rel_key = tuple(sorted((char1_clan["id"], char2_clan["id"])))
        clan_rel_type = clan_rels.get(clan_rel_key)
        if clan_rel_type == "WAR":
            return "ENEMY"
        if clan_rel_type == "ALLIANCE":
            return "FRIEND"

    species_rel_key = tuple(sorted((char1_species_id, char2_species_id)))
    species_rel_type = species_rels.get(species_rel_key)
    if species_rel_type:
        return species_rel_type

    return "INDIFFERENT"


def find_nearest_resource_node(
    character_pos: dict, all_nodes_docs: list[dict], resource_category: str = None
) -> dict | None:
    """
    Encontra o nó de recurso mais próximo da posição de um personagem,
    com a opção de filtrar por categoria. Opera com documentos MongoDB.
    """
    nearest_node_doc = None
    min_dist_sq = float("inf")

    potential_nodes = all_nodes_docs
    if resource_category:
        potential_nodes = [
            node for node in all_nodes_docs if node.get("category") == resource_category
        ]

    for node_doc in potential_nodes:
        node_pos = node_doc["position"]
        dist_sq = (node_pos["x"] - character_pos["x"]) ** 2 + (
            node_pos["y"] - character_pos["y"]
        ) ** 2

        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            nearest_node_doc = node_doc

    return nearest_node_doc


def get_territory_at_position(
    all_territories_docs: list[dict], x: float, y: float
) -> dict | None:
    """
    Verifica em qual território uma determinada coordenada (x, y) se encontra.
    Opera sobre uma lista de documentos de território do MongoDB.
    """
    for territory_doc in all_territories_docs:
        if (
            territory_doc["start_x"] <= x <= territory_doc["end_x"]
            and territory_doc["start_y"] <= y <= territory_doc["end_y"]
        ):
            return territory_doc
    return None


def find_nearest_character_by_relationship(
    origin_char_doc: dict,
    all_chars_docs: list[dict],
    relationship_func,
    target_relationship: str,
) -> dict | None:
    """
    Encontra o personagem mais próximo com base em um tipo de relação,
    operando com documentos do MongoDB.
    """
    nearest_char_doc = None
    min_dist_sq = VISION_RANGE**2

    origin_pos = origin_char_doc["position"]

    for target_char_doc in all_chars_docs:
        if origin_char_doc["_id"] == target_char_doc["_id"]:
            continue

        if relationship_func(origin_char_doc, target_char_doc) == target_relationship:

            target_pos = target_char_doc["position"]

            dist_sq = (target_pos["x"] - origin_pos["x"]) ** 2 + (
                target_pos["y"] - origin_pos["y"]
            ) ** 2

            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                nearest_char_doc = target_char_doc

    return nearest_char_doc


def move_towards_position(
    character_pos: dict, target_pos: dict, world_doc: dict, stop_distance: float
) -> tuple[bool, dict]:
    """
    Calcula a nova posição para se mover em direção a um alvo.
    Retorna (moved: bool, new_pos: dict).
    Evita overshoot: move no máximo MOVE_SPEED, mas para quando atingir stop_distance.
    """
    direction_x = target_pos["x"] - character_pos["x"]
    direction_y = target_pos["y"] - character_pos["y"]

    distance = math.hypot(direction_x, direction_y)

    if distance <= stop_distance or distance == 0:
        return False, character_pos

    remain = distance - stop_distance
    step = min(MOVE_SPEED, remain)

    norm_x = direction_x / distance
    norm_y = direction_y / distance

    new_x = character_pos["x"] + norm_x * step
    new_y = character_pos["y"] + norm_y * step

    new_pos = {
        "x": max(0, min(world_doc["map_width"], new_x)),
        "y": max(0, min(world_doc["map_height"], new_y)),
    }

    return True, new_pos


def find_group_center(
    origin_char_doc: dict, allies_docs: list[dict], relationship_func
) -> tuple[float, float] | None:
    """
    Calcula o centro de massa (ponto médio) de um grupo de aliados próximos
    ao personagem de origem. Opera com documentos MongoDB.
    """
    friends_positions = []
    origin_pos = origin_char_doc["position"]

    friends_positions.append((origin_pos["x"], origin_pos["y"]))

    for ally_doc in allies_docs:
        ally_pos = ally_doc["position"]
        friends_positions.append((ally_pos["x"], ally_pos["y"]))

    if len(friends_positions) <= 1:
        return None

    avg_x = sum(pos[0] for pos in friends_positions) / len(friends_positions)
    avg_y = sum(pos[1] for pos in friends_positions) / len(friends_positions)

    return (avg_x, avg_y)


def move_away_from_target(
    character_pos: dict, target_pos: dict, world_doc: dict
) -> dict:
    """
    Move para longe do alvo: usa MOVE_SPEED como passo máximo e mantém nos limites do mapa.
    """
    direction_x = character_pos["x"] - target_pos["x"]
    direction_y = character_pos["y"] - target_pos["y"]

    distance = math.hypot(direction_x, direction_y)

    if distance == 0:
        direction_x = random.uniform(-1, 1)
        direction_y = random.uniform(-1, 1)
        distance = math.hypot(direction_x, direction_y)
        if distance == 0:
            return character_pos

    norm_x = direction_x / distance
    norm_y = direction_y / distance

    step = MOVE_SPEED
    new_x = character_pos["x"] + norm_x * step
    new_y = character_pos["y"] + norm_y * step

    return {
        "x": max(0, min(world_doc["map_width"], new_x)),
        "y": max(0, min(world_doc["map_height"], new_y)),
    }


def process_wandering_state(character_pos: dict, world_doc: dict) -> dict:
    """
    Movimento aleatório controlado: randomiza passo até MOVE_SPEED/2 para movimentos mais suaves.
    """
    max_step = MOVE_SPEED / 2.0 if MOVE_SPEED > 0 else 0.5
    random_dx = random.uniform(-max_step, max_step)
    random_dy = random.uniform(-max_step, max_step)

    new_x = character_pos["x"] + random_dx
    new_y = character_pos["y"] + random_dy

    return {
        "x": max(0, min(world_doc["map_width"], new_x)),
        "y": max(0, min(world_doc["map_height"], new_y)),
    }


async def get_clan_goal_position(
    db: Database, clan_id: int
) -> tuple[float, float] | None:
    """
    Determina a coordenada do objetivo atual de um clã, consultando o MongoDB.
    Primeiro, procura uma missão de conquista ativa. Se não encontrar,
    usa o centro do território natal do clã.
    """
    if not clan_id:
        return None

    mission_doc = await db.missions.find_one(
        {"assignee_clan_id": clan_id, "status": "ATIVA"}
    )

    if mission_doc:
        for objective in mission_doc.get("objectives", []):
            if (
                not objective.get("is_complete")
                and objective.get("objective_type") == "CONQUER_TERRITORY"
            ):

                target_territory_id = objective.get("target_territory_id")
                if not target_territory_id:
                    continue

                territory_doc = await db.territories.find_one(
                    {"_id": target_territory_id}
                )

                if territory_doc:
                    center_x = (territory_doc["start_x"] + territory_doc["end_x"]) / 2
                    center_y = (territory_doc["start_y"] + territory_doc["end_y"]) / 2
                    return (center_x, center_y)

    home_territory_doc = await db.territories.find_one({"owner_clan_id": clan_id})

    if home_territory_doc:
        center_x = (home_territory_doc["start_x"] + home_territory_doc["end_x"]) / 2
        center_y = (home_territory_doc["start_y"] + home_territory_doc["end_y"]) / 2
        return (center_x, center_y)

    return None


async def check_and_update_mission_progress(
    db: Database, world_id: int
):  # MUDANÇA: async def
    """
    Verifica e atualiza o progresso de todas as missões ativas de forma assíncrona.
    """
    active_missions = await db.missions.find(
        {"world_id": world_id, "status": "ATIVA"}
    ).to_list(length=None)

    for mission_doc in active_missions:
        all_objectives_complete = True

        objectives = mission_doc.get("objectives", [])

        update_tasks = []

        for i, objective in enumerate(objectives):
            if objective.get("is_complete"):
                continue

            is_objective_now_complete = False

            if objective.get("objective_type") == "GATHER_RESOURCE":
                target_resource_id = objective.get("target_resource_id")

                pipeline = [
                    {"$match": {"clan.id": mission_doc["assignee_clan_id"]}},
                    {"$unwind": "$inventory"},
                    {"$match": {"inventory.resource_id": target_resource_id}},
                    {"$group": {"_id": None, "total": {"$sum": "$inventory.quantity"}}},
                ]

                aggregation_result = await db.characters.aggregate(pipeline).to_list(
                    length=1
                )

                total_gathered = (
                    aggregation_result[0].get("total", 0) if aggregation_result else 0
                )

                update_tasks.append(
                    db.missions.update_one(
                        {"_id": mission_doc["_id"]},
                        {"$set": {f"objectives.{i}.current_progress": total_gathered}},
                    )
                )

                if total_gathered >= objective.get("target_quantity", float("inf")):
                    is_objective_now_complete = True

            elif objective.get("objective_type") == "CONQUER_TERRITORY":
                target_territory_id = objective.get("target_territory_id")

                territory_doc = await db.territories.find_one(
                    {
                        "_id": target_territory_id,
                        "owner_clan_id": mission_doc["assignee_clan_id"],
                    }
                )

                if territory_doc:
                    is_objective_now_complete = True

            if is_objective_now_complete:
                update_tasks.append(
                    db.missions.update_one(
                        {"_id": mission_doc["_id"]},
                        {"$set": {f"objectives.{i}.is_complete": True}},
                    )
                )
                objective["is_complete"] = True

            if not objective.get("is_complete"):
                all_objectives_complete = False

        if all_objectives_complete:
            update_tasks.append(
                db.missions.update_one(
                    {"_id": mission_doc["_id"]}, {"$set": {"status": "CONCLUÍDA"}}
                )
            )
            print(f"Missão '{mission_doc['title']}' foi concluída!")

        if update_tasks:
            await asyncio.gather(*update_tasks)


def create_event(world_id: int, event_type: str, payload: dict) -> dict:
    """
    Cria um documento de evento padronizado, conforme especificado no relatório de Big Data.
    Esta função substitui a antiga 'log_event'. Ela não modifica listas,
    apenas cria e retorna um novo dicionário de evento.
    """
    return {
        "eventId": str(uuid.uuid4()),
        "worldId": world_id,
        "timestamp": datetime.now(timezone.utc),
        "eventType": event_type,
        "payload": payload,
    }


def create_relationship_update_operation(
    char_a_id: int, char_b_id: int, score_change: float
) -> dict:
    """
    Cria uma operação 'updateOne' do MongoDB para atualizar (ou criar) uma relação pessoal.
    Utiliza a flag 'upsert' para criar a relação se ela não existir.
    Utiliza o operador '$inc' para uma atualização atômica e segura.
    """
    if char_a_id == char_b_id:
        return {}

    char_ids = sorted((char_a_id, char_b_id))

    update_operation = {
        "updateOne": {
            "filter": {
                "character_a_id": char_ids[0],
                "character_b_id": char_ids[1],
            },
            "update": {
                "$inc": {"relationship_score": score_change},
                "$setOnInsert": {
                    "character_a_id": char_ids[0],
                    "character_b_id": char_ids[1],
                    "created_at": datetime.now(timezone.utc),
                },
                "$currentDate": {"last_interaction": True},
            },
            "upsert": True,
        }
    }
    return update_operation


def create_new_character_document(db: Database, world_id, parent_a_doc, parent_b_doc):
    """
    Cria o documento completo para um novo personagem nascido na simulação.
    """
    last_char = db.characters.find_one(sort=[("_id", -1)])
    new_id = (last_char["_id"] + 1) if last_char else 1

    species_doc = parent_a_doc["species"]

    new_char_doc = {
        "_id": new_id,
        "name": f"{species_doc['name']} {new_id}",
        "world_id": world_id,
        "gender": random.choice(["masculino", "feminino"]),
        "status": "VIVO",
        "species": species_doc,
        "clan": parent_a_doc.get("clan"),
        "current_health": species_doc["base_health"],
        "position": parent_a_doc["position"],
        "vitals": {"fome": 0, "energia": 100, "idade": 0},
        "personality": {
            "bravura": 50,
            "cautela": 50,
            "sociabilidade": 50,
            "ganancia": 50,
            "inteligencia": 50,
        },
        "stats": {"kills": 0, "deaths": 0, "damageDealt": 0, "resourcesCollected": 0},
        "inventory": [],
        "notableEvents": [],
        "lastUpdate": datetime.now(timezone.utc),
    }
    return new_char_doc
