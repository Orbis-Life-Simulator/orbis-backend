import asyncio
import math
import os
from datetime import datetime, timezone
import random
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

# Importa as funções auxiliares necessárias
from app.simulation.simulation_utils import (
    check_and_update_mission_progress,
    create_event,
    get_clan_goal_position,
    get_effective_relationship,
)

# Importa as constantes da simulação
from .constants import *


async def process_tick(db: AsyncIOMotorDatabase, world_id: Any):
    """
    Processa um único 'tick' da simulação.
    CORREÇÃO: Garante que a detecção de morte em combate compare IDs como strings.
    """
    from .behavior_tree import build_character_ai_tree

    print(f"\n--- Iniciando Tick para Mundo {world_id} ---")

    # --- FASE 1: CARREGAMENTO DE DADOS ---
    world_doc = await db.worlds.find_one({"_id": world_id})
    if not world_doc:
        return

    all_character_docs = await db.characters.find(
        {"world_id": world_id, "status": "VIVO"}
    ).to_list(length=None)

    if not all_character_docs:
        await db.world_analytics.update_one(
            {"_id": world_id}, {"$inc": {"currentTick": 1}}, upsert=True
        )
        return

    tasks = [
        db.territories.find({"world_id": world_id}).to_list(length=None),
        db.resource_nodes.find({"world_id": world_id, "is_depleted": False}).to_list(
            length=None
        ),
        db.resource_types.find().to_list(length=None),
        db.clan_relationships.find().to_list(length=None),
        db.species_relationships.find().to_list(length=None),
        db.character_relationships.find().to_list(length=None),
        db.clans.find({"world_id": world_id}).to_list(length=None),
    ]
    (
        all_territory_docs,
        all_resource_node_docs,
        all_resource_type_docs,
        clan_rels_list,
        species_rels_list,
        personal_rels_list,
        clans_list,
    ) = await asyncio.gather(*tasks)

    clan_rels = {
        tuple(sorted((r["clan_a_id"], r["clan_b_id"]))): r.get("relationship_type")
        for r in clan_rels_list
    }
    species_rels = {
        tuple(sorted((r["species_a_id"], r["species_b_id"]))): r.get(
            "relationship_type"
        )
        for r in species_rels_list
    }
    personal_rels = {
        tuple(sorted((r["character_a_id"], r["character_b_id"]))): r
        for r in personal_rels_list
    }

    resource_types_map = {rt["_id"]: rt for rt in all_resource_type_docs}
    for node in all_resource_node_docs:
        rt = resource_types_map.get(node.get("resource_type_id"))
        if rt:
            node.setdefault("category", rt.get("category"))
            node.setdefault(
                "resource_type", {"id": rt.get("_id"), "name": rt.get("name")}
            )

    goal_tasks = [get_clan_goal_position(db, clan["_id"]) for clan in clans_list]
    goal_results = await asyncio.gather(*goal_tasks)
    clan_goals = {clans_list[i]["_id"]: goal_results[i] for i in range(len(clans_list))}

    zombie_species = await db.species.find_one({"name": "Zumbi"})
    zombie_species_id = zombie_species["_id"] if zombie_species else None

    # --- FASE 2: CONSTRUÇÃO DO WORLD_STATE ---
    world_state = {
        "world": world_doc,
        "all_characters": all_character_docs,
        "all_territories": all_territory_docs,
        "all_resource_nodes": all_resource_node_docs,
        "relationship_updates": [],
        "zombie_species_id": zombie_species_id,
        "clan_rels": clan_rels,
        "species_rels": species_rels,
        "personal_rels": personal_rels,
        "clan_goals": clan_goals,
    }

    # --- FASE 3: PROCESSAMENTO DA IA ---
    ai_tree = build_character_ai_tree()

    def get_rel_func(char1, char2):
        return get_effective_relationship(
            char1,
            char2,
            world_state["zombie_species_id"],
            world_state["clan_rels"],
            world_state["species_rels"],
            world_state["personal_rels"],
        )

    world_state["get_rel"] = get_rel_func

    events_to_create: List[Dict[str, Any]] = []
    bulk_character_updates: List[UpdateOne] = []

    for char_doc in all_character_docs:
        try:
            blackboard = {}
            ai_tree.tick(
                char_doc,
                world_state,
                blackboard,
                events_to_create,
                bulk_character_updates,
            )
        except Exception as e:
            import traceback

            print(f"Erro ao processar IA para o personagem {char_doc.get('_id')}: {e}")

    # --- FASE 3.5: PERSISTÊNCIA INTERMEDIÁRIA ---
    if bulk_character_updates:
        await db.characters.bulk_write(bulk_character_updates, ordered=False)
    bulk_character_updates = []

    # --- FASE 4: PÓS-PROCESSAMENTO E LÓGICA PASSIVA CENTRALIZADA ---
    living_characters_after_ai = await db.characters.find(
        {"world_id": world_id, "status": "VIVO"}
    ).to_list(length=None)

    dead_this_tick = set()
    for char_doc in living_characters_after_ai:
        char_id = char_doc["_id"]

        # 1. VERIFICAÇÃO DE MORTE POR COMBATE (VIDA <= 0)
        if char_doc["current_health"] <= 0:
            # <<< CORREÇÃO CRÍTICA AQUI >>>
            # Convertemos o char_id para string para comparar com o ID no evento (que é string)
            target_id_str = str(char_id)

            combat_event = next(
                (
                    e
                    for e in reversed(events_to_create)
                    if e.get("eventType") == "COMBAT_ACTION"
                    and str(e.get("payload", {}).get("defender", {}).get("id"))
                    == target_id_str
                ),
                None,
            )

            if combat_event:
                reason = "Morto em combate"
                killer_info = combat_event.get("payload", {}).get("attacker", {})
            else:
                # Fallback apenas se realmente não achou o evento
                reason = "Dano passivo"
                killer_info = {}

            death_payload = {
                "character": {
                    "id": target_id_str,
                    "name": char_doc.get("name"),
                    "species": char_doc.get("species"),
                    "clan": char_doc.get("clan"),
                },
                "reason": reason,
                "killed_by": killer_info,
                "location": char_doc.get("position"),
            }
            events_to_create.append(
                create_event(world_id, "CHARACTER_DEATH", death_payload)
            )
            bulk_character_updates.append(
                UpdateOne({"_id": char_id}, {"$set": {"status": "MORTO"}})
            )
            dead_this_tick.add(char_id)
            continue

        # 2. VELHICE
        current_age_ticks = char_doc.get("vitals", {}).get("idade", 0)
        death_age_in_ticks = char_doc.get("lifespan", {}).get("death_age_ticks")
        if death_age_in_ticks and (current_age_ticks + 1) >= death_age_in_ticks:
            death_payload = {
                "character": {
                    "id": str(char_id),
                    "name": char_doc.get("name"),
                    "species": char_doc.get("species"),
                },
                "reason": "Velhice",
                "location": char_doc.get("position"),
            }
            events_to_create.append(
                create_event(world_id, "CHARACTER_DEATH", death_payload)
            )
            bulk_character_updates.append(
                UpdateOne(
                    {"_id": char_id}, {"$set": {"status": "MORTO", "current_health": 0}}
                )
            )
            dead_this_tick.add(char_id)
            continue

        bulk_character_updates.append(
            UpdateOne({"_id": char_id}, {"$inc": {"vitals.idade": 1}})
        )

        # 3. FOME
        new_fome = min(
            100, char_doc.get("vitals", {}).get("fome", 0) + HUNGER_INCREASE_RATE
        )
        bulk_character_updates.append(
            UpdateOne({"_id": char_id}, {"$set": {"vitals.fome": new_fome}})
        )

        if new_fome >= 100:
            new_health = char_doc["current_health"] - STARVATION_DAMAGE
            bulk_character_updates.append(
                UpdateOne({"_id": char_id}, {"$set": {"current_health": new_health}})
            )
            if new_health <= 0:
                death_payload = {
                    "character": {
                        "id": str(char_id),
                        "name": char_doc.get("name"),
                        "species": char_doc.get("species"),
                    },
                    "reason": "Fome",
                    "location": char_doc.get("position"),
                }
                events_to_create.append(
                    create_event(world_id, "CHARACTER_DEATH", death_payload)
                )
                bulk_character_updates.append(
                    UpdateOne(
                        {"_id": char_id},
                        {"$set": {"status": "MORTO", "current_health": 0}},
                    )
                )
                dead_this_tick.add(char_id)
                continue

        # 4. ENERGIA
        current_energy = char_doc.get("vitals", {}).get("energia", 100)
        new_energy = min(100, current_energy + ENERGY_REGEN_RATE)
        if new_energy != current_energy:
            bulk_character_updates.append(
                UpdateOne({"_id": char_id}, {"$set": {"vitals.energia": new_energy}})
            )

    # --- Lógica de Alianças ---
    alliance_inserts = []
    if random.random() < 0.05:
        for i in range(len(clans_list)):
            for j in range(i + 1, len(clans_list)):
                claA, claB = clans_list[i], clans_list[j]
                s_key = tuple(sorted((claA.get("species_id"), claB.get("species_id"))))
                if species_rels.get(s_key) == "FRIEND":
                    clan_key = tuple(sorted((claA["_id"], claB["_id"])))
                    if clan_key not in clan_rels:
                        alliance_doc = {
                            "clan_a_id": claA["_id"],
                            "clan_b_id": claB["_id"],
                            "relationship_type": "ALLIANCE",
                            "world_id": world_id,
                        }
                        alliance_inserts.append(alliance_doc)
                        events_to_create.append(
                            create_event(
                                world_id,
                                "ALLIANCE_FORMED",
                                {
                                    "clanA": {
                                        "id": claA["_id"],
                                        "name": claA.get("name"),
                                    },
                                    "clanB": {
                                        "id": claB["_id"],
                                        "name": claB.get("name"),
                                    },
                                },
                            )
                        )
                        clan_rels[clan_key] = "ALLIANCE"

    # --- FASE 5: PERSISTÊNCIA FINAL ---
    final_tasks = []
    if alliance_inserts:
        final_tasks.append(db.clan_relationships.insert_many(alliance_inserts))
    if events_to_create:
        final_tasks.append(db.events.insert_many(events_to_create, ordered=False))
    if bulk_character_updates:
        final_tasks.append(
            db.characters.bulk_write(bulk_character_updates, ordered=False)
        )
    if world_state["relationship_updates"]:
        final_tasks.append(
            db.character_relationships.bulk_write(
                world_state["relationship_updates"], ordered=False
            )
        )

    if final_tasks:
        await asyncio.gather(*final_tasks)
    await check_and_update_mission_progress(db, world_id)

    # --- FASE 6: ATUALIZAR ANALYTICS ---
    current_population = len(living_characters_after_ai) - len(dead_this_tick)
    pipeline = [
        {"$match": {"world_id": world_id, "status": "VIVO"}},
        {"$group": {"_id": "$species.name", "count": {"$sum": 1}}},
    ]
    population_data = await db.characters.aggregate(pipeline).to_list(length=None)
    pop_by_species = {item["_id"]: item["count"] for item in population_data}

    await db.world_analytics.update_one(
        {"_id": world_id},
        {
            "$set": {
                "population.total": current_population,
                "population.bySpecies": pop_by_species,
                "lastUpdate": datetime.now(timezone.utc),
            },
            "$inc": {"currentTick": 1},
        },
        upsert=True,
    )

    print(f"--- Tick para Mundo {world_id} concluído ---")
