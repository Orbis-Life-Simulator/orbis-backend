from enum import Enum
from ..database import models
from .engine import (
    GATHER_RANGE,
    GROUPING_DISTANCE,
    VISION_RANGE,
    find_nearest_resource_node,
    find_group_center,
    move_away_from_target,
    move_towards_target,
    move_towards_position,
    process_wandering_state,
    consume_food_from_inventory,
    get_territory_at_position,
)


class NodeStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"


class Node:
    def tick(
        self,
        character: models.Character,
        world_state: dict,
        blackboard: dict,
        commands: dict,
    ) -> NodeStatus:
        raise NotImplementedError


class Selector(Node):
    def __init__(self, children: list[Node]):
        self.children = children

    def tick(self, character, world_state, blackboard, commands):
        for child in self.children:
            status = child.tick(character, world_state, blackboard, commands)
            if status != NodeStatus.FAILURE:
                return status
        return NodeStatus.FAILURE


class Sequence(Node):
    def __init__(self, children: list[Node]):
        self.children = children

    def tick(self, character, world_state, blackboard, commands):
        for child in self.children:
            status = child.tick(character, world_state, blackboard, commands)
            if status != NodeStatus.SUCCESS:
                return status
        return NodeStatus.SUCCESS


class Consideration:
    def __init__(self, behavior_tree: Node):
        self.behavior_tree = behavior_tree

    def calculate_utility(
        self, character: models.Character, world_state: dict, blackboard: dict
    ) -> float:
        raise NotImplementedError


class UtilitySelector(Node):
    def __init__(self, considerations: list[Consideration], default_behavior: Node):
        self.considerations = considerations
        self.default_behavior = default_behavior

    def tick(self, character, world_state, blackboard, commands):
        blackboard.clear()
        allies_in_range = []
        enemies_in_range = []
        valid_targets = [
            c for c in world_state["all_characters"] if c.id != character.id
        ]

        for other in valid_targets:
            dist_sq = (other.position_x - character.position_x) ** 2 + (
                other.position_y - character.position_y
            ) ** 2
            if dist_sq < VISION_RANGE**2:
                rel = world_state["get_rel"](character, other)
                if rel == "FRIEND":
                    allies_in_range.append(other)
                elif rel == "ENEMY":
                    enemies_in_range.append(other)

        blackboard["enemies_in_range"] = enemies_in_range
        blackboard["allies_in_range"] = allies_in_range
        blackboard["numerical_advantage"] = len(allies_in_range) - len(enemies_in_range)

        log_event = world_state["log_event_func"]

        scores_info = {}
        best_consideration = None
        highest_score = -1.0

        for consideration in self.considerations:
            score = consideration.calculate_utility(character, world_state, blackboard)
            scores_info[consideration.__class__.__name__] = round(score, 2)
            if score > highest_score:
                highest_score = score
                best_consideration = consideration

        scores_str = ", ".join(
            [f"{name}: {score}" for name, score in scores_info.items()]
        )

        UTILITY_THRESHOLD = 10.0

        if best_consideration and highest_score > UTILITY_THRESHOLD:
            chosen_behavior_name = best_consideration.__class__.__name__.replace(
                "Consideration", ""
            )

            description = (
                f"'{character.name}' decidiu '{chosen_behavior_name}' com score {round(highest_score, 2)}. "
                f"Scores: [{scores_str}]"
            )
            log_event(
                commands, world_state["world"].id, "DECISION", character, description
            )

            return best_consideration.behavior_tree.tick(
                character, world_state, blackboard, commands
            )

        description = (
            f"'{character.name}' não atingiu o limiar de utilidade e irá perambular (Wander). "
            f"Maior score foi {round(highest_score, 2)}. Scores: [{scores_str}]"
        )
        log_event(commands, world_state["world"].id, "DECISION", character, description)

        return self.default_behavior.tick(character, world_state, blackboard, commands)


class IsEnemyNear(Node):
    def tick(self, character, world_state, blackboard, commands):
        if blackboard.get("enemies_in_range"):
            blackboard["target_enemy"] = min(
                blackboard["enemies_in_range"],
                key=lambda e: (e.position_x - character.position_x) ** 2
                + (e.position_y - character.position_y) ** 2,
            )
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


class HasFoodInInventory(Node):
    def tick(self, character, world_state, blackboard, commands):
        char_inventory = world_state["inventory_map"].get(character.id, {})
        for item in char_inventory.values():
            if item.resource_type_id in world_state["food_resource_type_ids"]:
                return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


class Flee(Node):
    def tick(self, character, world_state, blackboard, commands):
        target = blackboard.get("target_enemy")
        if not target:
            return NodeStatus.FAILURE

        log_event = world_state["log_event_func"]
        description = f"'{character.name}' está fugindo de '{target.name}'."
        log_event(
            commands,
            world_state["world"].id,
            "ACTION_FLEE",
            character,
            description,
            secondary_char=target,
        )

        move_away_from_target(character, target, world_state["world"])
        return NodeStatus.RUNNING


class Attack(Node):
    def tick(
        self,
        character: models.Character,
        world_state: dict,
        blackboard: dict,
        commands: dict,
    ) -> NodeStatus:
        target = blackboard.get("target_enemy")
        if not target or target.id in commands["characters_to_delete_ids"]:
            return NodeStatus.FAILURE

        if not move_towards_target(character, target, world_state["world"]):
            log_event = world_state["log_event_func"]
            damage = character.species.base_strength
            character.energia -= 5
            target.current_health -= damage

            commands["rels_to_update"].append((character.id, target.id, -5.0))

            description = (
                f"'{character.name}' atacou '{target.name}' por {damage} de dano."
            )
            log_event(
                commands,
                world_state["world"].id,
                "ATAQUE",
                character,
                description,
                secondary_char=target,
            )

            if target.current_health <= 0:
                commands["characters_to_delete_ids"].add(target.id)
                death_desc = f"'{target.name}' foi morto por '{character.name}'."
                log_event(
                    commands,
                    world_state["world"].id,
                    "MORTE",
                    target,
                    death_desc,
                    secondary_char=character,
                )
                commands["rels_to_update"].append((character.id, target.id, -20.0))

            return NodeStatus.SUCCESS

        character.energia -= 1
        return NodeStatus.RUNNING


class HelpAllyBehavior(Node):
    def tick(
        self,
        character: models.Character,
        world_state: dict,
        blackboard: dict,
        commands: dict,
    ) -> NodeStatus:
        threat_to_ally = blackboard.get("threat_to_ally")
        ally_in_danger = blackboard.get("ally_in_danger")

        if not threat_to_ally or not ally_in_danger:
            return NodeStatus.FAILURE

        commands["rels_to_update"].append((character.id, ally_in_danger.id, 2.5))

        blackboard["target_enemy"] = threat_to_ally

        return Attack().tick(character, world_state, blackboard, commands)


class HelpAllyConsideration(Consideration):
    def calculate_utility(self, character, world_state, blackboard):
        allies = blackboard.get("allies_in_range", [])
        enemies = blackboard.get("enemies_in_range", [])
        if not allies or not enemies:
            return 0.0

        personal_rels = world_state["personal_rels_map"]
        best_ally_to_help = None
        highest_urgency = 0.0

        for ally in allies:
            closest_enemy_to_ally = None
            min_dist_sq = float("inf")
            for enemy in enemies:
                dist_sq = (ally.position_x - enemy.position_x) ** 2 + (
                    ally.position_y - enemy.position_y
                ) ** 2
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    closest_enemy_to_ally = enemy

            ATTACK_RANGE_SQ = 225.0  # (15*15)
            if closest_enemy_to_ally and min_dist_sq < ATTACK_RANGE_SQ:
                rel_key = tuple(sorted((character.id, ally.id)))
                relationship = personal_rels.get(rel_key)

                if relationship and relationship.relationship_score > 0:
                    ally_life_multiplier = 1.0 - (
                        ally.current_health / ally.species.base_health
                    )
                    urgency = relationship.relationship_score * (
                        1 + ally_life_multiplier
                    )

                    if urgency > highest_urgency:
                        highest_urgency = urgency
                        best_ally_to_help = (ally, closest_enemy_to_ally)

        if best_ally_to_help:
            ally_in_danger, threat = best_ally_to_help
            blackboard["ally_in_danger"] = ally_in_danger
            blackboard["threat_to_ally"] = threat

            return highest_urgency

        return 0.0


class EatFromInventory(Node):
    def tick(self, character, world_state, blackboard, commands):
        ate, item_to_delete = consume_food_from_inventory(
            character,
            world_state["inventory_map"],
            world_state["food_resource_type_ids"],
        )
        if ate:
            log_event = world_state["log_event_func"]
            nova_fome = max(0, character.fome - 50)
            description = f"'{character.name}' comeu do inventário. Fome: {character.fome} -> {nova_fome}."
            log_event(
                commands, world_state["world"].id, "ACTION_EAT", character, description
            )
            character.fome = nova_fome

        if item_to_delete:
            commands["objects_to_delete"].append(item_to_delete)
        return NodeStatus.SUCCESS if ate else NodeStatus.FAILURE


class FindFoodResource(Node):
    def tick(self, character, world_state, blackboard, commands):
        target_node = find_nearest_resource_node(
            character, world_state["all_nodes"], resource_category="COMIDA"
        )
        if target_node:
            blackboard["target_node"] = target_node
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


class MoveToAndGatherResource(Node):
    def tick(
        self,
        character: models.Character,
        world_state: dict,
        blackboard: dict,
        commands: dict,
    ) -> NodeStatus:
        target_node = blackboard.get("target_node")
        if not target_node or target_node.is_depleted:
            return NodeStatus.FAILURE

        log_event = world_state["log_event_func"]

        is_still_moving = move_towards_position(
            character,
            target_node.position_x,
            target_node.position_y,
            world_state["world"],
            GATHER_RANGE,
        )

        if is_still_moving:
            description = f"'{character.name}' está se movendo para coletar '{target_node.resource_type.name}'."
            log_event(
                commands,
                world_state["world"].id,
                "ACTION_MOVE_GATHER",
                character,
                description,
            )

            character.energia -= 1

            return NodeStatus.RUNNING

        else:
            description = (
                f"'{character.name}' coletou 1 '{target_node.resource_type.name}'."
            )
            log_event(
                commands,
                world_state["world"].id,
                "ACTION_GATHER",
                character,
                description,
            )

            inv_map = world_state["inventory_map"]
            inventory_item = inv_map.get(character.id, {}).get(
                target_node.resource_type_id
            )
            if inventory_item:
                inventory_item.quantity += 1
            else:
                new_item = models.CharacterInventory(
                    character_id=character.id,
                    resource_type_id=target_node.resource_type_id,
                    quantity=1,
                )
                inv_map.setdefault(character.id, {})[
                    target_node.resource_type_id
                ] = new_item
                commands["objects_to_add"].append(new_item)

            target_node.quantity -= 1
            character.energia -= 3

            if target_node.quantity <= 0:
                target_node.is_depleted = True

            return NodeStatus.SUCCESS


class GroupOrFollowObjective(Node):
    def tick(self, character, world_state, blackboard, commands):
        character.energia -= 1
        clan_goal = world_state["clan_goals"].get(character.clan_id)
        if clan_goal:
            move_towards_position(
                character,
                clan_goal[0],
                clan_goal[1],
                world_state["world"],
                GATHER_RANGE,
            )
            return NodeStatus.RUNNING
        group_center = find_group_center(
            character, blackboard.get("allies_in_range", []), world_state["get_rel"]
        )
        if group_center:
            move_towards_position(
                character,
                group_center[0],
                group_center[1],
                world_state["world"],
                GROUPING_DISTANCE,
            )
            return NodeStatus.RUNNING
        return NodeStatus.FAILURE


class Wander(Node):
    def tick(self, character, world_state, blackboard, commands):
        character.energia -= 1
        process_wandering_state(character, world_state["world"])

        log_event = world_state["log_event_func"]
        description = f"'{character.name}' está perambulando (Wandering)."
        log_event(
            commands, world_state["world"].id, "ACTION_WANDER", character, description
        )

        return NodeStatus.SUCCESS


class Rest(Node):
    """Ação de descansar. O personagem simplesmente para. A regeneração de energia
    será tratada no loop principal do engine.py."""

    def tick(self, character, world_state, blackboard, commands):
        return NodeStatus.SUCCESS


class FleeConsideration(Consideration):
    def calculate_utility(self, character, world_state, blackboard):
        if not blackboard["enemies_in_range"]:
            return 0.0
        life_percentage = character.current_health / character.species.base_health
        base_flee_desire = ((1.0 - life_percentage) ** 2) * 150
        bravery_modifier = 1.0 - ((character.bravura - 50) / 100.0)
        disadvantage_modifier = 1.0 - min(0, blackboard["numerical_advantage"]) * 0.2
        return base_flee_desire * bravery_modifier * disadvantage_modifier


class AttackConsideration(Consideration):
    def calculate_utility(self, character, world_state, blackboard):
        enemies_in_range = blackboard["enemies_in_range"]
        if not enemies_in_range or character.energia < 10:
            return 0.0

        target = min(
            enemies_in_range,
            key=lambda e: (e.position_x - character.position_x) ** 2
            + (e.position_y - character.position_y) ** 2,
        )

        personal_rels = world_state["personal_rels_map"]
        rel_key = tuple(sorted((character.id, target.id)))
        relationship = personal_rels.get(rel_key)

        personal_modifier = 1.0
        if relationship and relationship.relationship_score < 0:
            personal_modifier = 1.0 + abs(relationship.relationship_score) / 100.0

        life_modifier = character.current_health / character.species.base_health
        strength_ratio = character.species.base_strength / target.species.base_strength
        strength_modifier = max(0.5, min(1.5, strength_ratio))
        advantage = blackboard["numerical_advantage"]
        numerical_modifier = 1.0 + (advantage * 0.3)
        bravery_modifier = 0.75 + ((character.bravura / 100.0) * 0.5)

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
    def calculate_utility(self, character, world_state, blackboard):
        base_hunger_desire = (character.fome / 100.0) * 100.0
        greed_bonus = (character.ganancia / 100.0) * 15.0

        current_territory = get_territory_at_position(
            world_state["all_territories"], character.position_x, character.position_y
        )
        is_safe = (
            not current_territory
            or not current_territory.owner_clan_id
            or current_territory.owner_clan_id == character.clan_id
        )

        caution_modifier = 1.0
        if not is_safe and character.cautela > 50:
            caution_modifier = 1.0 - ((character.cautela - 50) / 50.0) * 0.8

        return (base_hunger_desire + greed_bonus) * caution_modifier


class GroupConsideration(Consideration):
    def calculate_utility(self, character, world_state, blackboard):
        return 15.0 * (character.sociabilidade / 50.0)


class RestConsideration(Consideration):
    def calculate_utility(self, character, world_state, blackboard):

        if blackboard["enemies_in_range"]:
            return 0.0

        energy_percentage = character.energia / 100.0
        score = (1.0 - energy_percentage) * 80
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

    considerations = [
        FleeConsideration(flee_behavior),
        HelpAllyConsideration(help_ally_behavior),
        AttackConsideration(combat_behavior),
        EatConsideration(eat_behavior),
        RestConsideration(rest_behavior),
        GroupConsideration(group_behavior),
    ]

    root = UtilitySelector(
        considerations=considerations, default_behavior=wander_behavior
    )
    return root
