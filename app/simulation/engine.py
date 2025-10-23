from collections import defaultdict
from datetime import datetime, timezone
from typing import Tuple, List, Dict, Any
import asyncio
import os
import math
from concurrent.futures import ProcessPoolExecutor

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from app.simulation.simulation_utils import (
    check_and_update_mission_progress,
    create_event,
    get_effective_relationship,
    create_new_character_document,
    get_clan_goal_position,
)
from .constants import *


def process_character_chunk(args: Tuple[List[Dict[str, Any]], Dict[str, Any]]):
    """
    Processa um 'chunk' de personagens. Retorna uma tupla com a lista de eventos
    e a lista de operações de atualização (UpdateOne).
    """
    character_chunk, world_state = args

    from app.simulation.behavior_tree import build_character_ai_tree

    from app.simulation.simulation_utils import get_effective_relationship

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

    ai_tree = build_character_ai_tree()
    local_events: List[Dict[str, Any]] = []
    local_bulk_updates: List[UpdateOne] = []

    for char_doc in character_chunk:
        try:
            blackboard = {}
            ai_tree.tick(
                char_doc, world_state, blackboard, local_events, local_bulk_updates
            )
        except Exception:
            import traceback

            traceback.print_exc()

    return local_events, local_bulk_updates


async def process_tick(db: AsyncIOMotorDatabase, world_id: Any):
    """Versão assíncrona e concorrente do motor da simulação."""
    print(f"\n--- Iniciando Tick (async) para Mundo {world_id} ---")
    loop = asyncio.get_running_loop()

    world_doc = await db.worlds.find_one({"_id": world_id})
    if not world_doc:
        print(f"Mundo {world_id} não encontrado. Abortando tick.")
        return

    all_character_docs = await db.characters.find(
        {"world_id": world_id, "status": "VIVO"}
    ).to_list(length=None)
    if not all_character_docs:
        await asyncio.gather(
            db.worlds.update_one({"_id": world_id}, {"$inc": {"current_tick": 1}}),
            db.world_analytics.update_one(
                {"_id": world_id}, {"$inc": {"currentTick": 1}}
            ),
        )
        return

    tasks = [
        db.territories.find({"world_id": world_id}).to_list(length=None),
        db.resource_nodes.find({"world_id": world_id, "is_depleted": False}).to_list(
            length=None
        ),
        db.clan_relationships.find().to_list(length=None),
        db.species_relationships.find().to_list(length=None),
        db.character_relationships.find().to_list(length=None),
        db.clans.find({"world_id": world_id}).to_list(length=None),
    ]
    (
        all_territory_docs,
        all_resource_node_docs,
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

    goal_tasks = [get_clan_goal_position(db, clan["_id"]) for clan in clans_list]
    goal_results = await asyncio.gather(*goal_tasks)
    clan_goals = {clans_list[i]["_id"]: goal_results[i] for i in range(len(clans_list))}

    zombie_species = await db.species.find_one({"name": "Zumbi"})
    zombie_species_id = zombie_species["_id"] if zombie_species else None

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

    num_workers = max(1, (os.cpu_count() or 4) - 1)
    chunk_size = math.ceil(len(all_character_docs) / num_workers)
    chunks = [
        all_character_docs[i : i + chunk_size]
        for i in range(0, len(all_character_docs), chunk_size)
    ]

    events_to_create: List[Dict[str, Any]] = []
    bulk_character_updates: List[UpdateOne] = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            loop.run_in_executor(
                executor, process_character_chunk, (chunk, world_state)
            )
            for chunk in chunks
        ]
        for fut in asyncio.as_completed(futures):
            chunk_events, chunk_updates = await fut
            events_to_create.extend(chunk_events)
            bulk_character_updates.extend(chunk_updates)

    new_characters_to_add: List[Dict[str, Any]] = []
    character_map = {c["_id"]: c for c in all_character_docs}

    for event in list(events_to_create):
        if event.get("eventType") == "CHARACTER_BIRTH":
            parent_a = character_map.get(
                event.get("payload", {}).get("parent_a", {}).get("id")
            )
            parent_b = character_map.get(
                event.get("payload", {}).get("parent_b", {}).get("id")
            )
            if parent_a and parent_b:
                new_doc = await create_new_character_document(
                    db, world_id, parent_a, parent_b
                )
                new_characters_to_add.append(new_doc)

    for char_doc in all_character_docs:
        new_fome = int(
            min(100, char_doc.get("vitals", {}).get("fome", 0) + HUNGER_INCREASE_RATE)
        )
        bulk_character_updates.append(
            UpdateOne({"_id": char_doc["_id"]}, {"$set": {"vitals.fome": new_fome}})
        )
        if new_fome >= 100:
            new_health = char_doc["current_health"] - STARVATION_DAMAGE
            bulk_character_updates.append(
                UpdateOne(
                    {"_id": char_doc["_id"]}, {"$set": {"current_health": new_health}}
                )
            )
            if new_health <= 0:
                events_to_create.append(
                    create_event(
                        world_id,
                        "CHARACTER_DEATH",
                        {"character_id": char_doc["_id"], "reason": "Fome"},
                    )
                )
                bulk_character_updates.append(
                    UpdateOne(
                        {"_id": char_doc["_id"]},
                        {"$set": {"status": "MORTO", "current_health": 0}},
                    )
                )

        is_resting = any(
            e
            for e in events_to_create
            if e.get("eventType") == "CHARACTER_ACTION_REST"
            and e.get("payload", {}).get("character", {}).get("id") == char_doc["_id"]
        )
        is_moving = any(
            e
            for e in events_to_create
            if e.get("eventType", "").startswith("CHARACTER_MOVE")
            and e.get("payload", {}).get("character", {}).get("id") == char_doc["_id"]
        )

        if not is_resting and not is_moving:
            bulk_character_updates.append(
                UpdateOne(
                    {"_id": char_doc["_id"]},
                    {"$inc": {"vitals.energia": ENERGY_REGEN_RATE}},
                )
            )

    try:
        db_tasks = []
        if events_to_create:
            db_tasks.append(db.events.insert_many(events_to_create, ordered=False))
        if new_characters_to_add:
            db_tasks.append(db.characters.insert_many(new_characters_to_add))
        if bulk_character_updates:
            db_tasks.append(
                db.characters.bulk_write(bulk_character_updates, ordered=False)
            )
        if world_state["relationship_updates"]:
            db_tasks.append(
                db.character_relationships.bulk_write(
                    world_state["relationship_updates"], ordered=False
                )
            )

        if db_tasks:
            await asyncio.gather(*db_tasks)

        await check_and_update_mission_progress(db, world_id)

    except Exception as e:
        print(f"Erro na persistência: {e}")
        import traceback

        traceback.print_exc()

    pipeline = [
        {"$match": {"world_id": world_id, "status": "VIVO"}},
        {"$group": {"_id": "$species.name", "count": {"$sum": 1}}},
    ]
    population_data = await db.characters.aggregate(pipeline).to_list(length=None)
    pop_by_species = {item["_id"]: item["count"] for item in population_data}

    total_population = 0
    if population_data:
        total_population = sum(item["count"] for item in population_data)

    await db.world_analytics.update_one(
        {"_id": world_id},
        {
            "$set": {
                "population.total": total_population,
                "population.bySpecies": pop_by_species,
                "lastUpdate": datetime.now(timezone.utc),
            },
            "$inc": {"currentTick": 1},
        },
    )
    await db.worlds.update_one({"_id": world_id}, {"$inc": {"current_tick": 1}})

    print(f"--- Tick (async) para Mundo {world_id} concluído ---")
