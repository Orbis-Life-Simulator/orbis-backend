from enum import Enum
from pymongo import UpdateOne

from app.simulation.simulation_utils import (
    create_event,
    create_relationship_update_operation,
    find_nearest_resource_node,
    get_territory_at_position,
    move_away_from_target,
    move_towards_position,
    process_wandering_state,
    find_group_center,
)

from .constants import *


class NodeStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"


class Node:
    """
    Classe base para todos os nós da Árvore de Comportamento.
    Define a interface do método `tick`.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:
        """
        Executa a lógica do nó para um único tick.

        Args:
            character_doc (dict): O documento de resumo do personagem do MongoDB.
            world_state (dict): Um dicionário com o snapshot do estado do mundo.
            blackboard (dict): Um dicionário para memória de curto prazo (contexto) do tick.
            events_to_create (list): Uma lista que os nós de ação devem preencher com novos documentos de evento.
            bulk_updates (list): Uma lista de objetos UpdateOne que serão aplicados pelo engine via bulk_write.

        Returns:
            NodeStatus: O resultado da execução do nó (SUCCESS, FAILURE, ou RUNNING).
        """
        raise NotImplementedError


class Selector(Node):
    """
    Executa seus filhos em ordem até que um deles retorne SUCCESS ou RUNNING.
    Se todos retornarem FAILURE, ele também retorna FAILURE.
    Conhecido como um "nó de fallback".
    """

    def __init__(self, children: list[Node]):
        self.children = children

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:
        """
        Itera sobre os nós filhos e para no primeiro que não falha.
        """
        for child in self.children:
            status = child.tick(
                character_doc,
                world_state,
                blackboard,
                events_to_create,
                bulk_updates,
            )
            if status != NodeStatus.FAILURE:
                return status

        return NodeStatus.FAILURE


class Sequence(Node):
    """
    Executa seus filhos em ordem até que todos retornem SUCCESS.
    Se qualquer filho retornar FAILURE ou RUNNING, a sequência para e
    retorna esse mesmo status.
    """

    def __init__(self, children: list[Node]):
        self.children = children

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:
        """
        Itera sobre os nós filhos e para no primeiro que falha ou está em andamento.
        """
        for child in self.children:
            status = child.tick(
                character_doc,
                world_state,
                blackboard,
                events_to_create,
                bulk_updates,
            )

            if status != NodeStatus.SUCCESS:
                return status

        return NodeStatus.SUCCESS


class Consideration:
    """
    Classe base para todas as "considerações" do sistema de Utilidade.
    Cada consideração avalia o estado do mundo e retorna uma pontuação numérica
    que representa o quão "desejável" é executar a ação associada.
    """

    def __init__(self, behavior_tree: Node):
        """
        Associa esta consideração a uma sub-árvore de comportamento.
        Se esta consideração for a escolhida, a `behavior_tree` será executada.
        """
        self.behavior_tree = behavior_tree

    def calculate_utility(
        self, character_doc: dict, world_state: dict, blackboard: dict
    ) -> float:
        """
        Calcula a pontuação de utilidade. Este método deve ser implementado
        pelas classes filhas (ex: FleeConsideration, AttackConsideration).

        Args:
            character_doc (dict): O documento de resumo do personagem do MongoDB.
            world_state (dict): Um dicionário com o snapshot do estado do mundo.
            blackboard (dict): Um dicionário para memória de curto prazo (contexto) do tick.

        Returns:
            float: A pontuação de utilidade calculada. Um valor maior indica maior prioridade.
        """
        raise NotImplementedError


class UtilitySelector(Node):
    """
    O cérebro da IA. Avalia múltiplas "Considerações" e escolhe a que tiver
    a maior pontuação de utilidade para executar.
    Também é responsável por preparar o 'blackboard' com informações contextuais.
    """

    def __init__(self, considerations: list[Consideration], default_behavior: Node):
        self.considerations = considerations
        self.default_behavior = default_behavior

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:
        blackboard.clear()

        enemies_in_range = []
        allies_in_range = []
        char_pos = character_doc["position"]

        for other_doc in world_state["all_characters"]:
            if other_doc["_id"] == character_doc["_id"]:
                continue

            other_pos = other_doc["position"]
            dist_sq = (other_pos["x"] - char_pos["x"]) ** 2 + (
                other_pos["y"] - char_pos["y"]
            ) ** 2

            if dist_sq < VISION_RANGE**2:
                relation = world_state["get_rel"](character_doc, other_doc)
                if relation == "ENEMY":
                    enemies_in_range.append(other_doc)
                elif relation == "FRIEND":
                    allies_in_range.append(other_doc)

        blackboard["enemies_in_range"] = enemies_in_range
        blackboard["allies_in_range"] = allies_in_range
        blackboard["numerical_advantage"] = len(allies_in_range) - len(enemies_in_range)

        scores_info = {}
        best_consideration = None
        highest_score = -1.0

        for consideration in self.considerations:
            score = consideration.calculate_utility(
                character_doc, world_state, blackboard
            )
            scores_info[consideration.__class__.__name__] = round(score, 2)
            if score > highest_score:
                highest_score = score
                best_consideration = consideration

        UTILITY_THRESHOLD = 10.0
        chosen_behavior_name = "Wander (Default)"

        if best_consideration and highest_score > UTILITY_THRESHOLD:
            chosen_behavior_name = best_consideration.__class__.__name__.replace(
                "Consideration", ""
            )

        decision_payload = {
            "character": {"id": character_doc["_id"], "name": character_doc["name"]},
            "chosen_behavior": chosen_behavior_name,
            "highest_score": round(highest_score, 2),
            "all_scores": scores_info,
            "context": {
                "health": character_doc["current_health"],
                "enemies_near": len(enemies_in_range),
                "allies_near": len(allies_in_range),
            },
        }
        events_to_create.append(
            create_event(world_state["world"]["_id"], "AI_DECISION", decision_payload)
        )

        if best_consideration and highest_score > UTILITY_THRESHOLD:
            status = best_consideration.behavior_tree.tick(
                character_doc,
                world_state,
                blackboard,
                events_to_create,
                bulk_updates,
            )
            if status == NodeStatus.FAILURE:
                return self.default_behavior.tick(
                    character_doc,
                    world_state,
                    blackboard,
                    events_to_create,
                    bulk_updates,
                )
            return status

        return self.default_behavior.tick(
            character_doc,
            world_state,
            blackboard,
            events_to_create,
            bulk_updates,
        )


class IsEnemyNear(Node):
    """
    Nó de condição que verifica se há inimigos no campo de visão (preenchido no blackboard).
    Se houver, ele identifica o inimigo mais próximo e o define como 'target_enemy'
    no blackboard para que outros nós de ação possam usá-lo.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:

        enemies_in_range = blackboard.get("enemies_in_range")
        if enemies_in_range:
            char_pos = character_doc["position"]

            closest_enemy = min(
                enemies_in_range,
                key=lambda enemy_doc: (enemy_doc["position"]["x"] - char_pos["x"]) ** 2
                + (enemy_doc["position"]["y"] - char_pos["y"]) ** 2,
            )

            blackboard["target_enemy"] = closest_enemy

            return NodeStatus.SUCCESS

        return NodeStatus.FAILURE


class HasFoodInInventory(Node):
    """
    Nó de condição que verifica se o inventário embutido do personagem
    contém algum item da categoria "COMIDA".
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:

        inventory = character_doc.get("inventory", [])

        for item in inventory:
            if item.get("category") == "COMIDA" and item.get("quantity", 0) > 0:
                blackboard["food_in_inventory"] = item
                return NodeStatus.SUCCESS

        return NodeStatus.FAILURE


class Flee(Node):
    """
    Nó de ação que faz o personagem se mover para longe do 'target_enemy'
    definido no blackboard.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:

        target_doc = blackboard.get("target_enemy")
        if not target_doc:
            return NodeStatus.FAILURE

        new_pos = move_away_from_target(
            character_doc["position"], target_doc["position"], world_state["world"]
        )

        flee_payload = {
            "character": {"id": character_doc["_id"], "name": character_doc["name"]},
            "fleeing_from": {"id": target_doc["_id"], "name": target_doc["name"]},
            "from_pos": character_doc["position"],
            "to_pos": new_pos,
        }
        events_to_create.append(
            create_event(world_state["world"]["_id"], "CHARACTER_FLEE", flee_payload)
        )

        update_operation = UpdateOne(
            {"_id": character_doc["_id"]}, {"$set": {"position": new_pos}}
        )
        bulk_updates.append(update_operation)

        return NodeStatus.RUNNING


class Attack(Node):
    """
    Nó de ação que faz o personagem se mover em direção ao 'target_enemy'
    e atacá-lo quando estiver no alcance.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:

        target_doc = blackboard.get("target_enemy")
        if not target_doc or target_doc.get("status") != "VIVO":
            return NodeStatus.FAILURE

        char_id = character_doc["_id"]
        target_id = target_doc["_id"]

        is_moving, new_pos = move_towards_position(
            character_doc["position"],
            target_doc["position"],
            world_state["world"],
            ATTACK_RANGE,
        )

        if is_moving:
            move_payload = {
                "character": {"id": char_id, "name": character_doc["name"]},
                "target": {"id": target_id, "name": target_doc["name"]},
                "from_pos": character_doc["position"],
                "to_pos": new_pos,
            }
            events_to_create.append(
                create_event(
                    world_state["world"]["_id"], "CHARACTER_MOVE_ATTACK", move_payload
                )
            )

            bulk_updates.append(
                UpdateOne({"_id": char_id}, {"$set": {"position": new_pos}})
            )
            return NodeStatus.RUNNING

        else:
            damage = character_doc["species"].get("base_strength", 10)

            combat_payload = {
                "attacker": {
                    "id": char_id,
                    "name": character_doc["name"],
                    "species": character_doc["species"]["name"],
                },
                "defender": {
                    "id": target_id,
                    "name": target_doc["name"],
                    "species": target_doc["species"]["name"],
                },
                "damageDealt": damage,
                "defenderHealthAfter": target_doc["current_health"] - damage,
            }
            events_to_create.append(
                create_event(
                    world_state["world"]["_id"], "COMBAT_ACTION", combat_payload
                )
            )

            bulk_updates.append(
                UpdateOne({"_id": target_id}, {"$inc": {"current_health": -damage}})
            )

            bulk_updates.append(
                UpdateOne({"_id": char_id}, {"$inc": {"stats.damageDealt": damage}})
            )

            if (target_doc["current_health"] - damage) <= 0:
                death_payload = {
                    "character": {"id": target_id, "name": target_doc["name"]},
                    "reason": "Morto em combate",
                    "killed_by": {"id": char_id, "name": character_doc["name"]},
                }
                events_to_create.append(
                    create_event(
                        world_state["world"]["_id"], "CHARACTER_DEATH", death_payload
                    )
                )

                bulk_updates.append(
                    UpdateOne({"_id": target_id}, {"$set": {"status": "MORTO"}})
                )

                bulk_updates.append(
                    UpdateOne({"_id": char_id}, {"$inc": {"stats.kills": 1}})
                )

            return NodeStatus.SUCCESS


class HelpAllyBehavior(Node):
    """
    Nó de ação que executa a lógica de ataque em nome de um aliado.
    Ele define o inimigo do aliado como seu próprio alvo e, em seguida,
    delega a execução para o nó de ação 'Attack'.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:

        threat_to_ally = blackboard.get("threat_to_ally")
        ally_in_danger = blackboard.get("ally_in_danger")

        if not threat_to_ally or not ally_in_danger:
            return NodeStatus.FAILURE

        relationship_update_op = create_relationship_update_operation(
            character_doc["_id"], ally_in_danger["_id"], score_change=2.5
        )

        if "relationship_updates" in world_state:
            world_state["relationship_updates"].append(relationship_update_op)

        help_payload = {
            "helper": {"id": character_doc["_id"], "name": character_doc["name"]},
            "ally_in_danger": {
                "id": ally_in_danger["_id"],
                "name": ally_in_danger["name"],
            },
            "threat": {"id": threat_to_ally["_id"], "name": threat_to_ally["name"]},
        }
        events_to_create.append(
            create_event(
                world_state["world"]["_id"], "CHARACTER_HELP_ALLY", help_payload
            )
        )

        blackboard["target_enemy"] = threat_to_ally

        return Attack().tick(
            character_doc, world_state, blackboard, events_to_create, bulk_updates
        )


class HelpAllyConsideration(Consideration):
    """
    Consideração que avalia a "urgência" de ajudar um aliado próximo que está sob ataque.
    A pontuação de utilidade é maior se o aliado for um bom amigo (relação pessoal alta)
    e se ele estiver com a vida baixa.
    """

    def calculate_utility(
        self, character_doc: dict, world_state: dict, blackboard: dict
    ) -> float:

        allies = blackboard.get("allies_in_range", [])
        enemies = blackboard.get("enemies_in_range", [])
        if not allies or not enemies:
            return 0.0

        personal_rels = world_state.get("personal_rels_map", {})
        best_ally_to_help = None
        highest_urgency = 0.0

        for ally_doc in allies:
            closest_enemy_to_ally = None
            min_dist_sq = float("inf")
            ally_pos = ally_doc["position"]

            for enemy_doc in enemies:
                enemy_pos = enemy_doc["position"]
                dist_sq = (ally_pos["x"] - enemy_pos["x"]) ** 2 + (
                    ally_pos["y"] - enemy_pos["y"]
                ) ** 2
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    closest_enemy_to_ally = enemy_doc

            DANGER_RADIUS_SQ = ATTACK_RANGE**2

            if closest_enemy_to_ally and min_dist_sq < DANGER_RADIUS_SQ:
                rel_key = tuple(sorted((character_doc["_id"], ally_doc["_id"])))
                relationship = personal_rels.get(rel_key)

                if relationship and relationship.get("relationship_score", 0) > 0:

                    ally_life_percentage = (
                        ally_doc["current_health"] / ally_doc["species"]["base_health"]
                    )
                    ally_life_multiplier = 1.0 - ally_life_percentage

                    urgency = relationship["relationship_score"] * (
                        1 + ally_life_multiplier
                    )

                    if urgency > highest_urgency:
                        highest_urgency = urgency
                        best_ally_to_help = (ally_doc, closest_enemy_to_ally)

        if best_ally_to_help:
            ally_in_danger, threat = best_ally_to_help
            blackboard["ally_in_danger"] = ally_in_danger
            blackboard["threat_to_ally"] = threat

            return highest_urgency

        return 0.0


class EatFromInventory(Node):
    """
    Nó de ação que faz o personagem consumir um item de comida de seu inventário.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:

        food_item_doc = blackboard.get("food_in_inventory")
        if not food_item_doc:
            return NodeStatus.FAILURE

        food_restoration_value = 50

        eat_payload = {
            "character": {"id": character_doc["_id"], "name": character_doc["name"]},
            "item_consumed": {
                "id": food_item_doc["resource_id"],
                "name": food_item_doc["name"],
            },
            "fome_before": character_doc.get("vitals", {}).get("fome", 0),
            "fome_after": max(
                0,
                character_doc.get("vitals", {}).get("fome", 0) - food_restoration_value,
            ),
        }
        events_to_create.append(
            create_event(world_state["world"]["_id"], "CHARACTER_EAT", eat_payload)
        )

        update_operation = UpdateOne(
            {
                "_id": character_doc["_id"],
                "inventory.resource_id": food_item_doc["resource_id"],
            },
            {
                "$inc": {
                    "inventory.$.quantity": -1,
                    "vitals.fome": -food_restoration_value,
                }
            },
        )
        bulk_updates.append(update_operation)

        return NodeStatus.SUCCESS


class FindFoodResource(Node):
    """
    Nó de condição que procura pelo nó de recurso da categoria "COMIDA"
    mais próximo do personagem. Se encontrar, armazena-o no blackboard
    para o nó 'MoveToAndGatherResource' usar.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:

        nearest_food_node = find_nearest_resource_node(
            character_doc["position"],
            world_state.get("all_resource_nodes", []),
            resource_category="COMIDA",
        )

        if nearest_food_node:
            blackboard["target_node"] = nearest_food_node
            return NodeStatus.SUCCESS

        return NodeStatus.FAILURE


class MoveToAndGatherResource(Node):
    """
    Nó de ação que faz o personagem se mover em direção a um 'target_node'
    e coletar o recurso quando estiver no alcance.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:

        target_node = blackboard.get("target_node")
        if not target_node or target_node.get("is_depleted"):
            return NodeStatus.FAILURE

        is_moving, new_pos = move_towards_position(
            character_doc["position"],
            target_node["position"],
            world_state["world"],
            GATHER_RANGE,
        )

        char_id = character_doc["_id"]

        if is_moving:
            move_payload = {
                "character": {"id": char_id, "name": character_doc["name"]},
                "resource_node": {
                    "id": target_node["_id"],
                    "type_id": target_node["resource_type_id"],
                },
                "from_pos": character_doc["position"],
                "to_pos": new_pos,
            }
            events_to_create.append(
                create_event(
                    world_state["world"]["_id"], "CHARACTER_MOVE_GATHER", move_payload
                )
            )
            bulk_updates.append(
                UpdateOne({"_id": char_id}, {"$set": {"position": new_pos}})
            )
            return NodeStatus.RUNNING

        else:
            gather_payload = {
                "character": {"id": char_id, "name": character_doc["name"]},
                "resource_node": {
                    "id": target_node["_id"],
                    "type_id": target_node["resource_type_id"],
                },
                "quantity": 1,
            }
            events_to_create.append(
                create_event(
                    world_state["world"]["_id"], "GATHER_RESOURCE", gather_payload
                )
            )

            item_exists = any(
                item["resource_id"] == target_node["resource_type_id"]
                for item in character_doc.get("inventory", [])
            )

            if item_exists:
                update_op = UpdateOne(
                    {
                        "_id": char_id,
                        "inventory.resource_id": target_node["resource_type_id"],
                    },
                    {
                        "$inc": {
                            "inventory.$.quantity": 1,
                            "stats.resourcesCollected": 1,
                        }
                    },
                )
            else:
                new_item_doc = {
                    "resource_id": target_node["resource_type_id"],
                    "name": "Nome do Recurso",
                    "category": "COMIDA",  # Exemplo
                    "quantity": 1,
                }
                update_op = UpdateOne(
                    {"_id": char_id},
                    {
                        "$push": {"inventory": new_item_doc},
                        "$inc": {"stats.resourcesCollected": 1},
                    },
                )
            bulk_updates.append(update_op)

            bulk_updates.append(
                UpdateOne({"_id": target_node["_id"]}, {"$inc": {"quantity": -1}})
            )

            return NodeStatus.SUCCESS


class GroupOrFollowObjective(Node):
    def tick(
        self, character_doc, world_state, blackboard, events_to_create, bulk_updates
    ):
        target_pos, move_type = None, "UNKNOWN"
        clan_id = character_doc.get("clan", {}).get("id")
        clan_goals = world_state.get("clan_goals", {})

        if clan_id and clan_id in clan_goals and clan_goals[clan_id]:
            goal_coords = clan_goals[clan_id]
            target_pos, move_type = {
                "x": goal_coords[0],
                "y": goal_coords[1],
            }, "OBJECTIVE"

        if not target_pos:
            from .simulation_utils import find_group_center

            group_center_coords = find_group_center(
                character_doc,
                blackboard.get("allies_in_range", []),
                world_state["get_rel"],
            )
            if group_center_coords:
                target_pos, move_type = {
                    "x": group_center_coords[0],
                    "y": group_center_coords[1],
                }, "GROUPING"

        if target_pos:
            stop_distance = (
                GATHER_RANGE if move_type == "OBJECTIVE" else GROUPING_DISTANCE
            )
            is_moving, new_pos = move_towards_position(
                character_doc["position"],
                target_pos,
                world_state["world"],
                stop_distance,
            )

            if is_moving:
                update_pos_op = UpdateOne(
                    {"_id": character_doc["_id"]}, {"$set": {"position": new_pos}}
                )
                update_energy_op = UpdateOne(
                    {"_id": character_doc["_id"]}, {"$inc": {"vitals.energia": -1}}
                )
                bulk_updates.extend([update_pos_op, update_energy_op])
                return NodeStatus.RUNNING
            else:
                return NodeStatus.SUCCESS

        return NodeStatus.FAILURE


class Wander(Node):
    """
    Nó de ação padrão que faz o personagem se mover para uma posição aleatória próxima.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:

        new_pos = process_wandering_state(
            character_doc["position"], world_state["world"]
        )

        move_payload = {
            "character": {"id": character_doc["_id"], "name": character_doc["name"]},
            "from_pos": character_doc["position"],
            "to_pos": new_pos,
        }
        events_to_create.append(
            create_event(
                world_state["world"]["_id"], "CHARACTER_MOVE_WANDER", move_payload
            )
        )

        update_pos_op = UpdateOne(
            {"_id": character_doc["_id"]}, {"$set": {"position": new_pos}}
        )
        update_energy_op = UpdateOne(
            {"_id": character_doc["_id"]}, {"$inc": {"vitals.energia": -1}}
        )

        bulk_updates.append(update_pos_op)
        bulk_updates.append(update_energy_op)

        return NodeStatus.SUCCESS


class Rest(Node):
    """
    Nó de ação que representa a decisão do personagem de ficar parado para descansar.
    A regeneração de energia em si é tratada pelo 'engine', mas este nó registra
    a intenção de descansar como um evento.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:

        rest_payload = {
            "character": {"id": character_doc["_id"], "name": character_doc["name"]},
            "location": character_doc["position"],
        }
        events_to_create.append(
            create_event(
                world_state["world"]["_id"], "CHARACTER_ACTION_REST", rest_payload
            )
        )

        return NodeStatus.SUCCESS


class FleeConsideration(Consideration):
    """
    Calcula a utilidade de fugir de um combate.
    A pontuação é alta se a vida do personagem estiver baixa, se ele for
    covarde (baixa bravura) ou se estiver em desvantagem numérica.
    """

    def calculate_utility(
        self, character_doc: dict, world_state: dict, blackboard: dict
    ) -> float:

        if not blackboard.get("enemies_in_range"):
            return 0.0

        life_percentage = (
            character_doc["current_health"] / character_doc["species"]["base_health"]
        )
        base_flee_desire = ((1.0 - life_percentage) ** 2) * 150

        bravura = character_doc.get("personality", {}).get("bravura", 50)
        bravery_modifier = 1.0 - ((bravura - 50) / 100.0)
        numerical_disadvantage = blackboard.get("numerical_advantage", 0)
        disadvantage_modifier = 1.0 - min(0, numerical_disadvantage) * 0.2
        return base_flee_desire * bravery_modifier * disadvantage_modifier


class AttackConsideration(Consideration):
    """
    Calcula a utilidade de atacar um inimigo.
    A pontuação é influenciada pela vida e energia do personagem,
    comparação de força, vantagem numérica, personalidade (bravura)
    e relações pessoais (rivalidades).
    """

    def calculate_utility(
        self, character_doc: dict, world_state: dict, blackboard: dict
    ) -> float:

        enemies_in_range = blackboard.get("enemies_in_range")
        energia = character_doc.get("vitals", {}).get("energia", 100)

        if not enemies_in_range or energia < 10:
            return 0.0

        target_doc = blackboard.get("target_enemy")
        if not target_doc:
            return 0.0

        personal_rels = world_state.get("personal_rels_map", {})
        rel_key = tuple(sorted((character_doc["_id"], target_doc["_id"])))
        relationship = personal_rels.get(rel_key)

        personal_modifier = 1.0
        if relationship and relationship.get("relationship_score", 0) < 0:
            personal_modifier = 1.0 + abs(relationship["relationship_score"]) / 100.0
        life_modifier = (
            character_doc["current_health"] / character_doc["species"]["base_health"]
        )

        strength_ratio = (
            character_doc["species"]["base_strength"]
            / target_doc["species"]["base_strength"]
        )
        strength_modifier = max(0.5, min(1.5, strength_ratio))
        advantage = blackboard.get("numerical_advantage", 0)
        numerical_modifier = 1.0 + (advantage * 0.3)

        bravura = character_doc.get("personality", {}).get("bravura", 50)
        bravery_modifier = 0.75 + ((bravura / 100.0) * 0.5)

        base_attack_desire = 60.0
        final_score = (
            base_attack_desire
            * life_modifier
            * strength_modifier
            * numerical_modifier
            * bravery_modifier
            * personal_modifier
        )

        return max(0, final_score)


class EatConsideration(Consideration):
    def calculate_utility(self, character_doc, world_state, blackboard):
        fome = character_doc.get("vitals", {}).get("fome", 0)

        base_hunger_desire = (fome / 100.0) ** 2 * 150

        ganancia = character_doc.get("personality", {}).get("ganancia", 50)
        greed_bonus = (ganancia / 100.0) * 10.0

        char_pos = character_doc["position"]
        current_territory = get_territory_at_position(
            world_state["all_territories"], char_pos["x"], char_pos["y"]
        )

        char_clan_id = character_doc.get("clan", {}).get("id")

        is_safe = True
        if current_territory and current_territory.get("owner_clan_id"):
            if current_territory["owner_clan_id"] != char_clan_id:
                is_safe = False

        caution_modifier = 1.0
        cautela = character_doc.get("personality", {}).get("cautela", 50)
        if not is_safe and cautela > 50:
            caution_modifier = 1.0 - ((cautela - 50) / 50.0) * 0.8

        return (base_hunger_desire + greed_bonus) * caution_modifier


class GroupConsideration(Consideration):
    def calculate_utility(self, character_doc, world_state, blackboard):
        sociability = character_doc.get("personality", {}).get("sociabilidade", 50)
        allies = blackboard.get("allies_in_range", [])

        if not allies:
            return 0.0

        from .simulation_utils import find_group_center

        group_center = find_group_center(character_doc, allies, world_state["get_rel"])

        distance_modifier = 1.0
        if group_center:
            char_pos = character_doc["position"]
            dist_sq = (group_center[0] - char_pos["x"]) ** 2 + (
                group_center[1] - char_pos["y"]
            ) ** 2
            if dist_sq < (GROUPING_DISTANCE**2):
                distance_modifier = 0.2

        base_desire = 12.0

        gender_bonus = 0.0
        my_gender = character_doc.get("gender")

        if my_gender:
            for ally_doc in blackboard.get("allies_in_range", []):
                if ally_doc.get("gender") and ally_doc.get("gender") != my_gender:
                    gender_bonus += 2.0

        return (base_desire * (sociability / 50.0)) * distance_modifier + gender_bonus


class RestConsideration(Consideration):
    def calculate_utility(self, character_doc, world_state, blackboard):
        if blackboard.get("enemies_in_range"):
            return 0.0

        energia = character_doc.get("vitals", {}).get("energia", 100)
        energy_percentage = energia / 100.0

        score = (1.0 - energy_percentage) ** 2 * 120
        return score


def build_character_ai_tree():
    flee_behavior = Sequence([IsEnemyNear(), Flee()])
    combat_behavior = Sequence([IsEnemyNear(), Attack()])
    eat_behavior = Selector(
        [
            Sequence([HasFoodInInventory(), EatFromInventory()]),
            Sequence([FindFoodResource(), MoveToAndGatherResource()]),
        ]
    )
    group_behavior = GroupOrFollowObjective()
    rest_behavior = Rest()
    wander_behavior = Wander()
    help_ally_behavior = HelpAllyBehavior()
    reproduce_behavior = Sequence([ReproduceAction()])

    considerations = [
        FleeConsideration(flee_behavior),
        HelpAllyConsideration(help_ally_behavior),
        AttackConsideration(combat_behavior),
        EatConsideration(eat_behavior),
        RestConsideration(rest_behavior),
        GroupConsideration(group_behavior),
        ReproduceConsideration(reproduce_behavior),
    ]

    root = UtilitySelector(
        considerations=considerations, default_behavior=wander_behavior
    )
    return root


class ReproduceConsideration(Consideration):
    def calculate_utility(self, character_doc, world_state, blackboard):
        if (
            blackboard.get("enemies_in_range")
            or character_doc.get("vitals", {}).get("fome", 0) > 50
            or character_doc.get("vitals", {}).get("energia", 100) < 50
        ):
            return 0.0

        my_gender = character_doc.get("gender")
        potential_partner = None
        for ally_doc in blackboard.get("allies_in_range", []):
            if (
                ally_doc.get("species", {}).get("id")
                == character_doc.get("species", {}).get("id")
                and ally_doc.get("gender")
                and ally_doc.get("gender") != my_gender
            ):
                rel_key = tuple(sorted((character_doc["_id"], ally_doc["_id"])))
                relationship = world_state.get("personal_rels_map", {}).get(rel_key)
                if relationship and relationship.get("relationship_score", 0) > 20:
                    potential_partner = ally_doc
                    break

        if potential_partner:
            blackboard["partner"] = potential_partner
            return 150.0

        return 0.0


class ReproduceAction(Node):
    def tick(
        self, character_doc, world_state, blackboard, events_to_create, bulk_updates
    ):
        partner = blackboard.get("partner")
        if not partner:
            return NodeStatus.FAILURE

        birth_payload = {
            "parent_a": {"id": character_doc["_id"], "name": character_doc["name"]},
            "parent_b": {"id": partner["_id"], "name": partner["name"]},
            "species": character_doc.get("species", {}).get("name"),
        }
        events_to_create.append(
            create_event(world_state["world"]["_id"], "CHARACTER_BIRTH", birth_payload)
        )

        print(f"{character_doc['name']} e {partner['name']} tiveram um filho!")

        return NodeStatus.SUCCESS
