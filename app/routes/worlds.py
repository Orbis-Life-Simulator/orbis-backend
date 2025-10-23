from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
import json
import math
from datetime import datetime, timezone
import random
from bson import ObjectId

from fastapi.encoders import jsonable_encoder

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.simulation.constants import MOVE_SPEED

from ..auth import SECRET_KEY, ALGORITHM
from ..dependencies import get_db
from ..simulation import engine
from ..simulation.connection_manager import manager
from ..schemas import worlds as world_schemas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    # ... (código inalterado)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await db.users.find_one({"email": email})
    if user is None:
        raise credentials_exception
    user["id"] = str(user["_id"])
    return user


class CustomWorldCreate(BaseModel):
    name: str
    species_ids: List[int]
    initial_agents_per_species: int


router = APIRouter(
    prefix="/api/worlds",
    tags=["World & Simulation (MongoDB)"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(get_current_user)],
)


async def _create_resource_nodes_for_world(
    db: AsyncIOMotorDatabase,
    world_obj_id: ObjectId,
    map_width: int,
    map_height: int,
    count: int = 25,
):
    """
    Insere 'count' resource_nodes aleatórios para o mundo especificado.
    Usa os resource_types existentes; se não houver tipos, não insere nada.
    """
    resource_types = await db.resource_types.find().to_list(length=None)
    if not resource_types:
        return []

    nodes = []
    for _ in range(count):
        rt = random.choice(resource_types)
        pos = {"x": random.uniform(0, map_width), "y": random.uniform(0, map_height)}
        node = {
            "world_id": world_obj_id,
            "resource_type_id": rt["_id"],
            "territory_id": None,
            "position": pos,
            "quantity": random.randint(5, 30),
            "is_depleted": False,
            "created_at": datetime.now(timezone.utc),
        }
        nodes.append(node)

    res = await db.resource_nodes.insert_many(nodes)
    return res.inserted_ids


@router.post(
    "/", response_model=world_schemas.WorldResponse, status_code=status.HTTP_201_CREATED
)
async def create_custom_world(
    world_data: CustomWorldCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    world_id = ObjectId()
    user_id = current_user["_id"]
    world_doc = {
        "_id": world_id,
        "name": world_data.name,
        "user_id": user_id,
        "map_width": 1000,
        "map_height": 1000,
        "current_tick": 0,
        "global_event": "NONE",
        "created_at": datetime.now(timezone.utc),
    }
    await db.worlds.insert_one(world_doc)
    created_world = await db.worlds.find_one({"_id": world_id})

    try:
        await _create_resource_nodes_for_world(
            db,
            world_id,
            created_world.get("map_width", 1000),
            created_world.get("map_height", 1000),
            count=30,
        )
    except Exception:
        pass

    async def _next_int_id(collection_name: str, db: AsyncIOMotorDatabase) -> int:
        docs = await db[collection_name].find({}, {"_id": 1}).to_list(length=None)
        nums = [d["_id"] for d in docs if isinstance(d.get("_id"), int)]
        return (max(nums) + 1) if nums else 1

    try:
        created_clans = {}

        for spec_id in world_data.species_ids:
            species_doc = await db.species.find_one(
                {"id": spec_id}
            ) or await db.species.find_one({"_id": spec_id})
            spec_name = None
            base_health = 100
            if species_doc:
                spec_name = species_doc.get("name") or species_doc.get("species_name")
                base_health = species_doc.get("base_health", base_health)

            clan_name = f"Clã de {spec_name or spec_id}"

            clan_id = None
            try:
                existing_docs = await db.clans.find({}, {"_id": 1}).to_list(length=None)
                existing_ids = [c["_id"] for c in existing_docs]
                int_ids = [i for i in existing_ids if isinstance(i, int)]
                if int_ids:
                    clan_id = max(int_ids) + 1
            except Exception:
                clan_id = None

            clan_doc = {
                "_id": (clan_id if clan_id is not None else ObjectId()),
                "world_id": world_id,
                "name": clan_name,
                "species_id": spec_id,
                "created_at": datetime.now(timezone.utc),
            }

            if clan_id is not None:
                await db.clans.insert_one(clan_doc)
                created_clans[spec_id] = {"id": clan_id, "name": clan_name}
            else:
                res = await db.clans.insert_one(clan_doc)
                created_clans[spec_id] = {"id": res.inserted_id, "name": clan_name}

    except Exception:
        pass

    try:
        territories = []
        map_w = created_world.get("map_width", 1000)
        map_h = created_world.get("map_height", 1000)
        padding = 50

        min_w = 80
        min_h = 80
        max_w = max(min_w, map_w // 3)
        max_h = max(min_h, map_h // 3)

        for spec_id, clan_info in created_clans.items():
            tw = random.randint(min_w, min(max_w, max(min_w, map_w - 2 * padding)))
            th = random.randint(min_h, min(max_h, max(min_h, map_h - 2 * padding)))

            start_x = random.randint(padding, max(padding, map_w - padding - tw))
            start_y = random.randint(padding, max(padding, map_h - padding - th))
            end_x = start_x + tw
            end_y = start_y + th

            territory_doc = {
                "world_id": world_id,
                "name": f"Território {clan_info.get('name')}",
                "owner_clan_id": clan_info.get("id"),
                "start_x": int(start_x),
                "start_y": int(start_y),
                "end_x": int(min(end_x, map_w - padding)),
                "end_y": int(min(end_y, map_h - padding)),
            }
            territories.append(territory_doc)

        if territories:
            await db.territories.insert_many(territories)
    except Exception:
        pass

    try:
        try:
            existing_cids = [c["_id"] for c in db.characters.find({}, {"_id": 1})]
            int_cids = [i for i in existing_cids if isinstance(i, int)]
            next_char_id = (max(int_cids) + 1) if int_cids else 1
            use_int_char_ids = bool(int_cids)
        except Exception:
            use_int_char_ids = False
            next_char_id = None

        new_chars = []

        for spec_id in world_data.species_ids:
            species_doc = await db.species.find_one(
                {"id": spec_id}
            ) or await db.species.find_one({"_id": spec_id})
            spec_name = species_doc.get("name") if species_doc else str(spec_id)
            base_health = species_doc.get("base_health", 100) if species_doc else 100

            clan_info = created_clans.get(spec_id, {})
            clan_ref = clan_info.get("id")
            clan_name_for_char = clan_info.get("name")

            territory_doc = await db.territories.find_one(
                {"world_id": world_id, "owner_clan_id": clan_ref}
            )

            for i in range(world_data.initial_agents_per_species):
                if use_int_char_ids:
                    char_id = next_char_id
                    next_char_id += 1
                else:
                    char_id = None

                char_name = f"{spec_name} {i + 1}"

                if territory_doc:
                    sx, sy = territory_doc["start_x"], territory_doc["start_y"]
                    ex, ey = territory_doc["end_x"], territory_doc["end_y"]
                    px = random.uniform(sx, ex)
                    py = random.uniform(sy, ey)
                else:
                    px = random.uniform(0, created_world.get("map_width", 1000))
                    py = random.uniform(0, created_world.get("map_height", 1000))

                char_doc = {
                    ("_id" if char_id is not None else "_id"): (
                        char_id if char_id is not None else ObjectId()
                    ),
                    "name": char_name,
                    "world_id": world_id,
                    "status": "VIVO",
                    "species": {
                        "id": spec_id,
                        "name": spec_name,
                        "base_strength": (
                            species_doc.get("base_strength") if species_doc else None
                        ),
                        "base_health": base_health,
                    },
                    "clan": {"id": clan_ref, "name": clan_name_for_char},
                    "current_health": base_health,
                    "position": {"x": px, "y": py},
                    "vitals": {"fome": 0, "energia": 100, "idade": 0},
                    "gender": random.choice(["masculino", "feminino"]),
                    "personality": {
                        "bravura": 50,
                        "cautela": 50,
                        "sociabilidade": 50,
                        "ganancia": 50,
                        "inteligencia": 50,
                    },
                    "stats": {
                        "kills": 0,
                        "deaths": 0,
                        "damageDealt": 0,
                        "resourcesCollected": 0,
                    },
                    "inventory": [],
                    "notableEvents": [],
                    "lastUpdate": datetime.now(timezone.utc),
                }
                new_chars.append(char_doc)

        if new_chars:
            await db.characters.insert_many(new_chars)
    except Exception:
        pass

    return jsonable_encoder(created_world, custom_encoder={ObjectId: str})


@router.get("/", response_model=List[world_schemas.WorldResponse])
async def read_user_worlds(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db.worlds.find({"user_id": current_user["_id"]})
    return await cursor.to_list(length=None)


@router.get("/{world_id}/state", response_model=dict)
async def get_full_world_state(
    world_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retorna a "fotografia" completa do estado de um mundo, se o usuário tiver permissão."""
    try:
        world_obj_id = ObjectId(world_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid World ID format.")

    world_doc = await db.worlds.find_one(
        {"_id": world_obj_id, "user_id": current_user["_id"]}
    )
    if not world_doc:
        raise HTTPException(
            status_code=404, detail="World not found or you don't have access."
        )

    character_docs = await db.characters.find({"world_id": world_obj_id}).to_list(
        length=None
    )
    territory_docs = await db.territories.find({"world_id": world_obj_id}).to_list(
        length=None
    )
    resource_nodes = await db.resource_nodes.find({"world_id": world_obj_id}).to_list(
        length=None
    )
    analytics_doc = await db.world_analytics.find_one({"_id": world_obj_id})

    full_state = {
        "world": world_doc,
        "analytics": analytics_doc,
        "characters": character_docs,
        "territories": territory_docs,
        "resource_nodes": resource_nodes,
    }

    return jsonable_encoder(full_state, custom_encoder={ObjectId: str})


@router.post("/{world_id}/tick", response_model=world_schemas.WorldResponse)
async def advance_simulation_tick(
    world_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Executa um "tick" da simulação, se o usuário tiver permissão."""
    try:
        world_obj_id = ObjectId(world_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid World ID format.")

    world_doc = await db.worlds.find_one(
        {"_id": world_obj_id, "user_id": current_user["_id"]}
    )
    if not world_doc:
        raise HTTPException(
            status_code=404,
            detail="World not found or you don't have access to run tick.",
        )

    await engine.process_tick(db, world_obj_id)

    updated_world_state = await get_full_world_state(world_id, db, current_user)
    try:
        updated_world_state["resource_nodes"] = await db.resource_nodes.find(
            {"world_id": world_obj_id}
        ).to_list(length=None)
    except Exception:
        updated_world_state.setdefault("resource_nodes", [])

    message_str = json.dumps(
        jsonable_encoder(updated_world_state, custom_encoder={ObjectId: str})
    )

    await manager.broadcast(message_str, world_id)

    return updated_world_state["world"]


def find_nearest_resource_node(
    character_pos: dict, all_nodes_docs: list[dict], resource_category: str = None
) -> dict | None:
    """
    Retorna o documento do nó de recurso mais próximo que corresponda à category (se fornecida)
    e que não esteja marcado como is_depleted.
    """
    nearest = None
    best_dist_sq = float("inf")

    for node in all_nodes_docs:
        if node.get("is_depleted", False):
            continue
        if resource_category and node.get("category") != resource_category:
            continue

        node_pos = node.get("position") or node.get("pos") or {"x": 0, "y": 0}
        dx = node_pos["x"] - character_pos["x"]
        dy = node_pos["y"] - character_pos["y"]
        dist_sq = dx * dx + dy * dy

        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            nearest = node

    return nearest


def move_towards_position(
    character_pos: dict, target_pos: dict, world_doc: dict, stop_distance: float
) -> tuple[bool, dict]:
    """
    Move em direção a target_pos sem ultrapassar. Retorna (moved, new_pos).
    - Evita overshoot usando step = min(MOVE_SPEED, distance - stop_distance)
    - Se já dentro de stop_distance, não move (False, pos atual)
    """
    direction_x = target_pos["x"] - character_pos["x"]
    direction_y = target_pos["y"] - character_pos["y"]
    distance = math.hypot(direction_x, direction_y)

    if distance <= stop_distance or distance == 0:
        return False, character_pos

    remain = max(0.0, distance - stop_distance)
    step = min(MOVE_SPEED, remain)

    norm_x = direction_x / distance
    norm_y = direction_y / distance

    new_x = character_pos["x"] + norm_x * step
    new_y = character_pos["y"] + norm_y * step

    new_pos = {
        "x": max(0, min(world_doc.get("map_width", 0), new_x)),
        "y": max(0, min(world_doc.get("map_height", 0), new_y)),
    }

    return True, new_pos


def move_away_from_target(
    character_pos: dict, target_pos: dict, world_doc: dict
) -> dict:
    """
    Move para longe do alvo até um passo MOVE_SPEED, mantendo dentro do mapa.
    Se overlap exato, escolhe direção randômica.
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
        "x": max(0, min(world_doc.get("map_width", 0), new_x)),
        "y": max(0, min(world_doc.get("map_height", 0), new_y)),
    }


def process_wandering_state(character_pos: dict, world_doc: dict) -> dict:
    """
    Movimento aleatório suave: passo máximo MOVE_SPEED/2 para evitar pulos bruscos.
    """
    max_step = max(0.1, MOVE_SPEED / 2.0)
    dx = random.uniform(-max_step, max_step)
    dy = random.uniform(-max_step, max_step)

    new_x = character_pos["x"] + dx
    new_y = character_pos["y"] + dy

    return {
        "x": max(0, min(world_doc.get("map_width", 0), new_x)),
        "y": max(0, min(world_doc.get("map_height", 0), new_y)),
    }


@router.delete("/{world_id}", status_code=status.HTTP_200_OK)
async def delete_world_and_related(
    world_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Deleta um mundo e todos os dados associados:
    - characters, territories, resource_nodes, events, clans, world_analytics,
      clan_relationships, character_relationships, missions (se existir), etc.
    Requer que o usuário seja proprietário do mundo.
    """
    candidates = []
    try:
        candidates.append(int(world_id))
    except Exception:
        pass

    if len(world_id) == 24:
        try:
            candidates.append(ObjectId(world_id))
        except Exception:
            pass

    candidates.append(world_id)
    candidates_unique = list(dict.fromkeys(candidates))

    try:
        world_obj_id = ObjectId(world_id)
    except Exception:
        world_obj_id = candidates_unique[0]

    world_doc = db.worlds.find_one(
        {"_id": world_obj_id, "user_id": current_user["_id"]}
    )
    if not world_doc:
        raise HTTPException(
            status_code=404, detail="World not found or you don't have access."
        )

    if len(set(map(type, candidates_unique))) == 1 and len(candidates_unique) == 1:
        world_filter = {"world_id": candidates_unique[0]}
        events_filter = {"worldId": candidates_unique[0]}
        analytics_filter = {"_id": candidates_unique[0]}
    else:
        world_filter = {"world_id": {"$in": candidates_unique}}
        events_filter = {"worldId": {"$in": candidates_unique}}
        analytics_filter = {"_id": {"$in": candidates_unique}}

    deleted = {}

    char_docs = await db.characters.find(world_filter, {"_id": 1}).to_list(length=None)
    char_ids = [c["_id"] for c in char_docs]
    clan_docs = await db.clans.find(world_filter, {"_id": 1}).to_list(length=None)
    clan_ids = [c["_id"] for c in clan_docs]

    res = await db.characters.delete_many(world_filter)
    deleted["characters"] = res.deleted_count

    res = await db.territories.delete_many(world_filter)
    deleted["territories"] = res.deleted_count

    res = await db.resource_nodes.delete_many(world_filter)
    deleted["resource_nodes"] = res.deleted_count

    res = await db.events.delete_many(events_filter)
    deleted["events"] = res.deleted_count

    res = await db.world_analytics.delete_many(analytics_filter)
    deleted["world_analytics"] = res.deleted_count

    res = await db.clans.delete_many(world_filter)
    deleted["clans"] = res.deleted_count
    if clan_ids:
        res = await db.clan_relationships.delete_many(
            {
                "$or": [
                    {"clan_a_id": {"$in": clan_ids}},
                    {"clan_b_id": {"$in": clan_ids}},
                ]
            }
        )
        deleted["clan_relationships"] = res.deleted_count
    else:
        deleted["clan_relationships"] = 0

    if char_ids:
        res = await db.character_relationships.delete_many(
            {
                "$or": [
                    {"character_a_id": {"$in": char_ids}},
                    {"character_b_id": {"$in": char_ids}},
                ]
            }
        )
        deleted["character_relationships"] = res.deleted_count
    else:
        deleted["character_relationships"] = 0

    try:
        res = await db.missions.delete_many(world_filter)
        deleted["missions"] = res.deleted_count
    except Exception:
        deleted["missions"] = 0

    res = await db.worlds.delete_one({"_id": world_obj_id})
    deleted["world"] = res.deleted_count

    return jsonable_encoder(
        {"message": "World and related data deleted.", "deleted": deleted},
        custom_encoder={ObjectId: str},
    )
