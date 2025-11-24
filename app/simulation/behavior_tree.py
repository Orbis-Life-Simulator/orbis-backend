from enum import Enum
import random
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

        # Threshold to decide whether a consideration is strong enough to override the default
        # Lower threshold so considerações (especialmente ataque e reprodução) sejam
        # mais facilmente escolhidas em vez do comportamento padrão.
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
                "health": character_doc.get("current_health"),
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
        # Moving while fleeing consumes energy
        bulk_updates.append(update_operation)
        bulk_updates.append(
            UpdateOne(
                {"_id": character_doc["_id"]},
                {"$inc": {"vitals.energia": -MOVE_ENERGY_COST}},
            )
        )

        return NodeStatus.RUNNING


# Arquivo: app/simulation/behavior_tree.py


class Attack(Node):
    """
    Nó de ação que faz o personagem se mover em direção ao 'target_enemy'
    e atacá-lo quando estiver no alcance. A função apenas aplica o dano;
    a lógica de morte é centralizada no engine.
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
        # Garante que não estamos tentando atacar um personagem que já foi marcado como morto neste tick
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
            bulk_updates.append(
                UpdateOne(
                    {"_id": char_id}, {"$inc": {"vitals.energia": -MOVE_ENERGY_COST}}
                )
            )
            return NodeStatus.RUNNING

        # <<< MUDANÇA PRINCIPAL COMEÇA AQUI >>>
        # Se não está se movendo, está em alcance de ataque.
        else:
            damage = character_doc["species"].get("base_strength", 10)

            combat_payload = {
                "attacker": {
                    "id": char_id,
                    "name": character_doc["name"],
                    "species": character_doc["species"]["name"],
                    "clan": character_doc.get("clan"),  # Adicionado clan do atacante
                },
                "defender": {
                    "id": target_id,
                    "name": target_doc["name"],
                    "species": target_doc["species"]["name"],
                    "clan": target_doc.get("clan"),  # Adicionado clan do defensor
                },
                "location": {
                    "x": target_doc["position"]["x"],
                    "y": target_doc["position"]["y"],
                },
                "damageDealt": damage,
                "defenderHealthAfter": target_doc["current_health"] - damage,
            }
            events_to_create.append(
                create_event(
                    world_state["world"]["_id"], "COMBAT_ACTION", combat_payload
                )
            )

            # 2. As operações de atualização de dano são mantidas.
            bulk_updates.append(
                UpdateOne({"_id": target_id}, {"$inc": {"current_health": -damage}})
            )
            bulk_updates.append(
                UpdateOne({"_id": char_id}, {"$inc": {"stats.damageDealt": damage}})
            )

            # 3. A lógica de morte ('if health <= 0') foi COMPLETAMENTE REMOVIDA.
            # A responsabilidade de verificar a vida e criar o evento de morte
            # agora pertence ao 'engine.py', que fará isso de forma centralizada
            # após todos os personagens agirem, evitando duplicatas e garantindo
            # a integridade dos dados de 'kills'.

            # Se o ataque deixar o alvo com vida negativa, incrementamos o kill count do atacante.
            # O engine cuidará de marcar o alvo como MORTO.
            if (target_doc["current_health"] - damage) <= 0:
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

            # If ally is critically low, prioritize helping strongly
            try:
                ally_health_ratio = ally_in_danger.get(
                    "current_health", 100
                ) / ally_in_danger.get("species", {}).get("base_health", 100)
            except Exception:
                ally_health_ratio = 1.0

            if ally_health_ratio < 0.4:
                return max(highest_urgency, 1000.0)

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

        # Zombies do not gather resources
        sp_name = str(character_doc.get("species", {}).get("name", "")).lower()
        if "zumb" in sp_name or "zombie" in sp_name:
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
            # moving to attack consumes energy
            bulk_updates.append(
                UpdateOne(
                    {"_id": char_id}, {"$inc": {"vitals.energia": -MOVE_ENERGY_COST}}
                )
            )
            return NodeStatus.RUNNING

        else:
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
                            "inventory.$.quantity": GATHER_AMOUNT,
                            "stats.resourcesCollected": GATHER_AMOUNT,
                        }
                    },
                )
            else:
                # Use resource_type metadata attached by engine when available
                rt = target_node.get("resource_type", {}) or {}
                new_item_doc = {
                    "resource_id": target_node["resource_type_id"],
                    "name": rt.get("name", "Recurso"),
                    "category": rt.get("category", "GENERIC"),
                    "quantity": GATHER_AMOUNT,
                }
                update_op = UpdateOne(
                    {"_id": char_id},
                    {
                        "$push": {"inventory": new_item_doc},
                        "$inc": {"stats.resourcesCollected": GATHER_AMOUNT},
                    },
                )
            bulk_updates.append(update_op)

            # decrement resource node by the configured gather amount
            bulk_updates.append(
                UpdateOne(
                    {"_id": target_node["_id"]}, {"$inc": {"quantity": -GATHER_AMOUNT}}
                )
            )

            # Emitir evento de coleta para o Spark/analytics
            gather_payload = {
                "character": {"id": char_id, "name": character_doc.get("name")},
                "resource_type": {
                    "id": target_node.get("resource_type_id"),
                    "name": target_node.get("resource_type", {}).get("name"),
                    "category": target_node.get("category"),
                },
                "location": target_node.get("position"),
                "quantity": GATHER_AMOUNT,
            }
            events_to_create.append(
                create_event(
                    world_state["world"]["_id"], "CHARACTER_GATHER", gather_payload
                )
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
                    {"_id": character_doc["_id"]},
                    {"$inc": {"vitals.energia": -MOVE_ENERGY_COST}},
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
        # events_to_create.append(
        #     create_event(
        #         world_state["world"]["_id"], "CHARACTER_MOVE_WANDER", move_payload
        #     )
        # )

        update_pos_op = UpdateOne(
            {"_id": character_doc["_id"]}, {"$set": {"position": new_pos}}
        )
        update_energy_op = UpdateOne(
            {"_id": character_doc["_id"]},
            {"$inc": {"vitals.energia": -WANDER_ENERGY_COST}},
        )

        bulk_updates.append(update_pos_op)
        bulk_updates.append(update_energy_op)

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
        species_name = str(character_doc.get("species", {}).get("name", "")).lower()
        if "zumb" in species_name or "zombie" in species_name:
            return 0.0

        enemies = blackboard.get("enemies_in_range")
        if not enemies:
            return 0.0

        life_percentage = character_doc.get("current_health", 0) / character_doc[
            "species"
        ].get("base_health", 100)

        base_flee_desire = ((1.0 - life_percentage) ** 2) * 70

        bravura = character_doc.get("personality", {}).get("bravura", 50)
        bravery_modifier = 1.0 - ((bravura - 50) / 100.0)

        numerical_disadvantage = blackboard.get("numerical_advantage", 0)
        disadvantage_modifier = 1.0 - max(0, -numerical_disadvantage) * 0.15

        score = base_flee_desire * bravery_modifier * disadvantage_modifier

        if life_percentage < 0.25 or numerical_disadvantage < -2:
            return max(score, 1000.0)

        return max(0.0, score)


# class AttackConsideration(Consideration):
#     """
#     COMPORTAMENTO AJUSTADO: Calcula a utilidade de atacar, agora considerando
#     competição por recursos e agressividade por invasão de território.
#     """

#     def calculate_utility(
#         self, character_doc: dict, world_state: dict, blackboard: dict
#     ) -> float:
#         enemies_in_range = blackboard.get("enemies_in_range")
#         energia = character_doc.get("vitals", {}).get("energia", 100)

#         if not enemies_in_range or energia < 20:
#             return 0.0

#         if (
#             character_doc.get("current_health", 100)
#             < character_doc["species"].get("base_health", 100) * 0.3
#         ):
#             return 0.0

#         target_doc = blackboard.get("target_enemy")
#         if not target_doc:
#             return 0.0

#         territory_aggression_modifier = 1.0
#         char_pos = character_doc["position"]
#         current_territory = get_territory_at_position(
#             world_state["all_territories"], char_pos["x"], char_pos["y"]
#         )
#         char_clan_id = character_doc.get("clan", {}).get("id")
#         if current_territory and current_territory.get("owner_clan_id") != char_clan_id:
#             territory_aggression_modifier = 1.4

#         resource_competition_bonus = 0.0
#         fome = character_doc.get("vitals", {}).get("fome", 0)
#         target_resource_node = blackboard.get("target_node")
#         if fome > 60 and target_resource_node:
#             dist_sq_enemy_to_resource = (
#                 target_doc["position"]["x"] - target_resource_node["position"]["x"]
#             ) ** 2 + (
#                 target_doc["position"]["y"] - target_resource_node["position"]["y"]
#             ) ** 2
#             if dist_sq_enemy_to_resource < (VISION_RANGE / 2) ** 2:
#                 resource_competition_bonus = 400.0

#         life_modifier = (
#             character_doc["current_health"] / character_doc["species"]["base_health"]
#         )
#         strength_ratio = (
#             character_doc["species"]["base_strength"]
#             / target_doc["species"]["base_strength"]
#         )
#         strength_modifier = max(0.5, min(1.5, strength_ratio))
#         advantage = blackboard.get("numerical_advantage", 0)
#         numerical_modifier = 1.0 + (advantage * 0.5)
#         bravura = character_doc.get("personality", {}).get("bravura", 50)
#         bravery_modifier = 0.75 + ((bravura / 100.0) * 0.75)
#         ganancia = character_doc.get("personality", {}).get("ganancia", 50)
#         greed_modifier = 1.0 + ((ganancia - 50) / 100.0) * 1.5

#         species_name = str(character_doc.get("species", {}).get("name", "")).lower()
#         species_aggression_map = {
#             "orc": 1.5,
#             "goblin": 1.4,
#             "troll": 1.45,
#             "zumbi": 2.0,
#         }
#         species_aggression = species_aggression_map.get(species_name, 1.0)

#         base_attack_desire = 500.0

#         final_score = (
#             (
#                 (base_attack_desire * territory_aggression_modifier)
#                 + resource_competition_bonus
#             )
#             * life_modifier
#             * strength_modifier
#             * numerical_modifier
#             * bravery_modifier
#             * greed_modifier
#             * species_aggression
#         )

#         return max(0.0, final_score)


class AttackConsideration(Consideration):
    def calculate_utility(self, character_doc, world_state, blackboard):
        enemies = blackboard.get("enemies_in_range")

        if enemies:
            return 1000.0

        return 0.0


class EatConsideration(Consideration):
    """
    Calcula a utilidade de procurar/comer comida. A pontuação é influenciada
    pela fome, personalidade (ganância, cautela), proximidade de recursos
    e segurança do local.
    """

    def calculate_utility(self, character_doc, world_state, blackboard):
        fome = character_doc.get("vitals", {}).get("fome", 0)

        # --- AJUSTE 1: Curva de fome mais agressiva ---
        # Aumentamos o desejo base. A fome se torna uma preocupação mais cedo.
        # A fórmula exponencial (fome^2) faz com que a urgência cresça rapidamente
        # quando a fome atinge níveis críticos.
        base_hunger_desire = ((fome / 100.0) ** 2) * 250.0 + (fome / 100.0 * 20.0)

        # --- AJUSTE 2: Bônus de Oportunidade ---
        # Verifica se há comida visível. Se sim, aumenta o desejo de coletar.
        opportunity_bonus = 0.0
        nearest_food_node = find_nearest_resource_node(
            character_doc["position"],
            world_state.get("all_resource_nodes", []),
            resource_category="COMIDA",
        )
        if nearest_food_node:
            char_pos = character_doc["position"]
            node_pos = nearest_food_node["position"]
            dist_sq = (node_pos["x"] - char_pos["x"]) ** 2 + (
                node_pos["y"] - char_pos["y"]
            ) ** 2

            # Se a comida estiver muito perto, o bônus é maior.
            if dist_sq < (VISION_RANGE / 2) ** 2:
                opportunity_bonus = 60.0  # Bônus significativo por comida próxima
            elif dist_sq < VISION_RANGE**2:
                opportunity_bonus = 30.0  # Bônus menor por comida visível

        ganancia = character_doc.get("personality", {}).get("ganancia", 50)
        # Personagens gananciosos são mais propensos a acumular recursos.
        greed_bonus = (ganancia / 100.0) * 30.0

        # --- AJUSTE 3: Modificador de Risco/Segurança ---
        # A lógica de segurança é mantida, mas refinada.
        char_pos = character_doc["position"]
        current_territory = get_territory_at_position(
            world_state["all_territories"], char_pos["x"], char_pos["y"]
        )
        char_clan_id = character_doc.get("clan", {}).get("id")

        is_safe_location = True
        if current_territory and current_territory.get("owner_clan_id"):
            # Território é considerado perigoso se não pertencer ao clã do personagem
            if current_territory["owner_clan_id"] != char_clan_id:
                is_safe_location = False

        # Se houver inimigos por perto, o local NUNCA é seguro para coletar.
        if blackboard.get("enemies_in_range"):
            is_safe_location = False

        caution_modifier = 1.0
        cautela = character_doc.get("personality", {}).get("cautela", 50)
        if not is_safe_location:
            # Personagens cautelosos recebem uma penalidade maior por coletar em locais perigosos.
            # A penalidade escala com o nível de cautela.
            caution_modifier = 1.0 - (cautela / 100.0) * 0.9

        # A pontuação final combina a necessidade (fome), a oportunidade e a personalidade,
        # ponderada pelo risco do local.
        final_score = (
            base_hunger_desire + opportunity_bonus + greed_bonus
        ) * caution_modifier

        # Se o personagem estiver morrendo de fome, a busca por comida se torna prioridade máxima,
        # ignorando parcialmente o risco.
        if fome > 95:
            return max(final_score, 1000.0)

        return max(0.0, final_score)


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

        # Make grouping more attractive so characters form groups more often.
        base_desire = 30.0

        gender_bonus = 0.0
        my_gender = character_doc.get("gender")

        if my_gender:
            for ally_doc in blackboard.get("allies_in_range", []):
                if ally_doc.get("gender") and ally_doc.get("gender") != my_gender:
                    gender_bonus += 2.0

        return (base_desire * (sociability / 50.0)) * distance_modifier + gender_bonus


class HasBuildingMaterials(Node):
    """
    Verifica se o personagem tem madeira e pedra suficientes no inventário.
    """

    def tick(
        self, character_doc, world_state, blackboard, events_to_create, bulk_updates
    ):
        inv = character_doc.get("inventory", [])
        wood_qty = 0
        stone_qty = 0
        for it in inv:
            name = str(it.get("name", "")).lower()
            cat = str(it.get("category", "")).lower()
            qty = int(it.get("quantity", 0))
            if (
                "madeir" in name
                or "wood" in name
                or "madeira" in name
                or cat == "madeira"
            ):
                wood_qty += qty
            if "pedra" in name or "stone" in name or cat == "pedra":
                stone_qty += qty

        if wood_qty >= HOUSE_WOOD_COST and stone_qty >= HOUSE_STONE_COST:
            blackboard["can_build_house"] = True
            return NodeStatus.SUCCESS

        return NodeStatus.FAILURE


class BuildHouseAction(Node):
    """
    Consome madeira e pedra do inventário e registra um evento de construção.
    Não cria coleção persistente de estruturas aqui; registra o evento e atualiza
    o inventário/estatísticas do personagem.
    """

    def tick(
        self, character_doc, world_state, blackboard, events_to_create, bulk_updates
    ):
        if not blackboard.get("can_build_house"):
            return NodeStatus.FAILURE

        char_id = character_doc["_id"]
        # Criar evento
        build_payload = {
            "character": {"id": char_id, "name": character_doc.get("name")},
            "location": character_doc.get("position"),
            "costs": {"wood": HOUSE_WOOD_COST, "stone": HOUSE_STONE_COST},
        }
        events_to_create.append(
            create_event(
                world_state["world"]["_id"], "CHARACTER_BUILD_HOUSE", build_payload
            )
        )

        # Deduzir recursos do inventário: usamos updates separados para madeira e pedra.
        # Primeiro, decrement wood
        bulk_updates.append(
            UpdateOne(
                {
                    "_id": char_id,
                    "inventory.name": {"$regex": "(?i)madeir|wood|madeira"},
                },
                {"$inc": {"inventory.$.quantity": -HOUSE_WOOD_COST}},
            )
        )
        # Depois, decrement stone
        bulk_updates.append(
            UpdateOne(
                {"_id": char_id, "inventory.name": {"$regex": "(?i)pedra|stone"}},
                {"$inc": {"inventory.$.quantity": -HOUSE_STONE_COST}},
            )
        )

        # Incrementa estatística de casas construídas
        bulk_updates.append(
            UpdateOne({"_id": char_id}, {"$inc": {"stats.housesBuilt": 1}})
        )

        return NodeStatus.SUCCESS


class BuildHouseConsideration(Consideration):
    def calculate_utility(self, character_doc, world_state, blackboard):
        # Prefer construir quando se tem muitos recursos e quando não há inimigos por perto
        if blackboard.get("enemies_in_range"):
            return 0.0

        inv = character_doc.get("inventory", [])
        wood_qty = 0
        stone_qty = 0
        for it in inv:
            name = str(it.get("name", "")).lower()
            cat = str(it.get("category", "")).lower()
            qty = int(it.get("quantity", 0))
            if (
                "madeir" in name
                or "wood" in name
                or "madeira" in name
                or cat == "madeira"
            ):
                wood_qty += qty
            if "pedra" in name or "stone" in name or cat == "pedra":
                stone_qty += qty

        if wood_qty >= HOUSE_WOOD_COST and stone_qty >= HOUSE_STONE_COST:
            # Score escalates with surplus resources
            surplus = (wood_qty - HOUSE_WOOD_COST) + (stone_qty - HOUSE_STONE_COST)
            return 80.0 + min(200.0, surplus * 5.0)

        return 0.0


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
    wander_behavior = Wander()
    help_ally_behavior = HelpAllyBehavior()
    build_house_behavior = Sequence([HasBuildingMaterials(), BuildHouseAction()])

    seek_resource_behavior = Sequence(
        [FindNeededResourceNode(), MoveToAndGatherResource()]
    )

    invade_behavior = InvadeEnemyTerritoryAction()

    considerations = [
        # FleeConsideration(flee_behavior),
        DefendTerritoryConsideration(combat_behavior),
        HelpAllyConsideration(help_ally_behavior),
        AttackConsideration(combat_behavior),
        EatConsideration(eat_behavior),
        SeekStrategicResourceConsideration(seek_resource_behavior),
        InvadeConsideration(invade_behavior),
        # BuildHouseConsideration(build_house_behavior),
        GroupConsideration(group_behavior),
    ]

    root = UtilitySelector(
        considerations=considerations, default_behavior=wander_behavior
    )
    return root


class ReproduceConsideration(Consideration):
    def calculate_utility(
        self, character_doc: dict, world_state: dict, blackboard: dict
    ) -> float:

        # # --- VERIFICAÇÕES DE BLOQUEIO DO PRÓPRIO PERSONAGEM ---

        # # 1. Limite de Filhos: A verificação mais importante.
        # # Usa .get() com um padrão alto (ex: 99) para garantir que, se o limite não for definido, a reprodução não aconteça.
        # max_offspring = character_doc.get("species", {}).get("max_offspring", 1)
        # if character_doc.get("stats", {}).get("children_count", 0) >= max_offspring:
        #     return 0.0

        # # 2. Idade Fértil (se você implementou)
        # # ... (sua lógica de verificação de idade)

        # # 3. Cooldown: Essencial para evitar spam de tentativas
        # if character_doc.get("cooldowns", {}).get("reproduction", 0) > 0:
        #     return 0.0

        # # 4. Condições de Perigo e Vitais
        # if (
        #     blackboard.get("enemies_in_range")
        #     or character_doc.get("vitals", {}).get("fome", 0) > 20
        #     or character_doc.get("vitals", {}).get("energia", 100) < 80
        # ):
        #     return 0.0

        # my_gender = character_doc.get("gender")
        # if not my_gender:
        #     return 0.0

        # # --- VERIFICAÇÃO DO PARCEIRO ---
        # potential_partner = None
        # for ally_doc in blackboard.get("allies_in_range", []):
        #     # O parceiro também não pode ter atingido o limite de filhos
        #     partner_max_offspring = ally_doc.get("species", {}).get("max_offspring", 1)
        #     if (
        #         ally_doc.get("stats", {}).get("children_count", 0)
        #         >= partner_max_offspring
        #     ):
        #         continue

        #     if (
        #         ally_doc.get("species", {}).get("id")
        #         == character_doc.get("species", {}).get("id")
        #         and ally_doc.get("gender")
        #         and ally_doc.get("gender") != my_gender
        #         and ally_doc.get("cooldowns", {}).get("reproduction", 0) == 0
        #     ):
        #         potential_partner = ally_doc
        #         break

        # # --- CÁLCULO DA PONTUAÇÃO ---
        # if potential_partner:
        #     blackboard["partner"] = potential_partner
        #     # A pontuação pode ser alta, pois as condições para chegar aqui são muito raras
        #     return 200.0

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

        bulk_updates.append(
            UpdateOne(
                {"_id": character_doc["_id"]},
                {"$set": {"cooldowns.reproduction": REPRODUCTION_COOLDOWN_TICKS * 5}},
            )
        )
        bulk_updates.append(
            UpdateOne(
                {"_id": partner["_id"]},
                {"$set": {"cooldowns.reproduction": REPRODUCTION_COOLDOWN_TICKS * 5}},
            )
        )

        print(f"{character_doc['name']} e {partner['name']} tiveram um filho!")
        return NodeStatus.SUCCESS


class FindNeededResourceNode(Node):
    """
    Nó de condição que procura o recurso estratégico mais próximo que foi
    identificado como "necessário" pela Consideration e o coloca no blackboard.
    """

    def tick(
        self,
        character_doc: dict,
        world_state: dict,
        blackboard: dict,
        events_to_create: list,
        bulk_updates: list,
    ) -> NodeStatus:
        needed_category = blackboard.get("needed_resource_category")
        if not needed_category:
            return NodeStatus.FAILURE

        # Procura o nó mais próximo da categoria necessária em TODO o mapa
        nearest_node = find_nearest_resource_node(
            character_doc["position"],
            world_state.get("all_resource_nodes", []),
            resource_category=needed_category,
        )

        if nearest_node:
            blackboard["target_node"] = nearest_node
            return NodeStatus.SUCCESS

        return NodeStatus.FAILURE


class SeekStrategicResourceConsideration(Consideration):
    """
    Calcula a utilidade de sair do território para buscar um recurso essencial
    que não está disponível localmente. Esta é uma consideração de alta prioridade
    para impulsionar a expansão e o conflito.
    """

    def calculate_utility(
        self, character_doc: dict, world_state: dict, blackboard: dict
    ) -> float:
        # Personagens com fome crítica ou pouca energia devem focar em sobrevivência imediata.
        if (
            character_doc.get("vitals", {}).get("fome", 0) > 70
            or character_doc.get("vitals", {}).get("energia", 100) < 30
        ):
            return 0.0

        # Personagens em combate não devem iniciar missões de coleta.
        if blackboard.get("enemies_in_range"):
            return 0.0

        # 1. Identificar o território atual do personagem
        char_pos = character_doc["position"]
        home_territory = get_territory_at_position(
            world_state["all_territories"], char_pos["x"], char_pos["y"]
        )

        # Só executa a lógica se o personagem estiver em um território do seu clã
        if not home_territory or home_territory.get(
            "owner_clan_id"
        ) != character_doc.get("clan", {}).get("id"):
            return 0.0

        # 2. Mapear quais categorias de recursos estão disponíveis no território natal
        local_resource_categories = set()
        for node in world_state.get("all_resource_nodes", []):
            node_pos = node["position"]
            if (
                home_territory["start_x"] <= node_pos["x"] <= home_territory["end_x"]
                and home_territory["start_y"]
                <= node_pos["y"]
                <= home_territory["end_y"]
            ):
                local_resource_categories.add(node.get("category"))

        # 3. Definir recursos essenciais e encontrar o que está faltando
        ESSENTIAL_CATEGORIES = ["MADEIRA", "PEDRA", "COMIDA"]
        needed_category = None
        for category in ESSENTIAL_CATEGORIES:
            if category not in local_resource_categories:
                needed_category = category
                break  # Encontrou o primeiro recurso essencial em falta

        if not needed_category:
            return (
                0.0  # O território tem tudo o que é essencial, sem necessidade de sair.
            )

        # 4. Se um recurso é necessário, calcular a pontuação de utilidade
        blackboard["needed_resource_category"] = needed_category

        # Pontuação base alta para tornar esta uma prioridade
        base_desire = 180.0

        # Modificadores de personalidade
        ganancia = character_doc.get("personality", {}).get("ganancia", 50)
        bravura = character_doc.get("personality", {}).get("bravura", 50)
        cautela = character_doc.get("personality", {}).get("cautela", 50)

        # Ganância e Bravura aumentam a vontade de se aventurar. Cautela diminui.
        personality_modifier = (
            1.0
            + ((ganancia - 50) / 100.0)
            + ((bravura - 50) / 100.0)
            - ((cautela - 50) / 100.0)
        )

        final_score = base_desire * personality_modifier

        return max(0.0, final_score)


class InvadeEnemyTerritoryAction(Node):
    """
    Faz o personagem se mover em direção ao centro de um território inimigo.
    """

    def tick(
        self, character_doc, world_state, blackboard, events_to_create, bulk_updates
    ):
        target_territory = blackboard.get("target_invasion_territory")
        if not target_territory:
            return NodeStatus.FAILURE

        # Calcula o centro do território alvo
        center_x = (target_territory["start_x"] + target_territory["end_x"]) / 2
        center_y = (target_territory["start_y"] + target_territory["end_y"]) / 2
        target_pos = {"x": center_x, "y": center_y}

        is_moving, new_pos = move_towards_position(
            character_doc["position"],
            target_pos,
            world_state["world"],
            stop_distance=20.0,
        )

        if is_moving:
            bulk_updates.append(
                UpdateOne(
                    {"_id": character_doc["_id"]},
                    {
                        "$set": {"position": new_pos},
                        "$inc": {"vitals.energia": -MOVE_ENERGY_COST},
                    },
                )
            )
            return NodeStatus.RUNNING

        return NodeStatus.SUCCESS


# class InvadeConsideration(Consideration):
#     def calculate_utility(self, character_doc, world_state, blackboard):
#         if character_doc.get("vitals", {}).get("fome", 0) > 50:
#             return 0.0
#         if character_doc.get("current_health", 0) < 80:
#             return 0.0

#         if blackboard.get("enemies_in_range"):
#             return 0.0

#         bravura = character_doc.get("personality", {}).get("bravura", 50)
#         ganancia = character_doc.get("personality", {}).get("ganancia", 50)

#         if bravura < 60 or ganancia < 60:
#             return 0.0

#         my_clan = character_doc.get("clan", {}).get("id")

#         enemy_territories = [
#             t
#             for t in world_state["all_territories"]
#             if t.get("owner_clan_id") != my_clan
#         ]

#         if not enemy_territories:
#             return 0.0

#         target_terr = random.choice(enemy_territories)
#         blackboard["target_invasion_territory"] = target_terr

#         random_impulse = random.uniform(0, 50)

#         return 150.0 + random_impulse


class InvadeConsideration(Consideration):
    def calculate_utility(self, character_doc, world_state, blackboard):
        if blackboard.get("enemies_in_range"):
            return 0.0

        my_clan = character_doc.get("clan", {}).get("id")

        enemy_terrs = [
            t
            for t in world_state["all_territories"]
            if t.get("owner_clan_id") != my_clan
        ]

        if not enemy_terrs:
            return 0.0

        target = random.choice(enemy_terrs)
        blackboard["target_invasion_territory"] = target

        return 500.0


# --- NOVO: Consideração de Defesa (Reação) ---
class DefendTerritoryConsideration(Consideration):
    def calculate_utility(self, character_doc, world_state, blackboard):
        enemies = blackboard.get("enemies_in_range")
        if not enemies:
            return 0.0

        char_pos = character_doc["position"]
        home_territory = get_territory_at_position(
            world_state["all_territories"], char_pos["x"], char_pos["y"]
        )
        my_clan = character_doc.get("clan", {}).get("id")

        # Se estou no meu território e há inimigos
        if home_territory and home_territory.get("owner_clan_id") == my_clan:
            # Verifica se o inimigo também está no meu território (invasão real)
            invader = False
            for e in enemies:
                e_terr = get_territory_at_position(
                    world_state["all_territories"],
                    e["position"]["x"],
                    e["position"]["y"],
                )
                if e_terr and e_terr["_id"] == home_territory["_id"]:
                    invader = True
                    break

            if invader:
                bravura = character_doc.get("personality", {}).get("bravura", 50)
                return 600.0 + (bravura * 2)  # Defesa furiosa (Alta prioridade)

        return 0.0
