from databases import Database
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
import json
import math
from datetime import datetime, timezone
import random
from bson import ObjectId

from fastapi.encoders import jsonable_encoder

from app.simulation.constants import TICKS_PER_YEAR, SPECIES_LIFESPAN_YEARS

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
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Cria um novo mundo customizado, semeando-o com clãs, personagens,
    territórios, recursos temáticos (dentro dos territórios) e
    recursos genéricos (espalhados pelo mapa).
    """
    world_id = ObjectId()
    user_id = current_user["_id"]

    MAP_WIDTH = 1000
    MAP_HEIGHT = 1000

    # 1. Cria o documento principal do Mundo
    world_doc = {
        "_id": world_id,
        "name": world_data.name,
        "user_id": user_id,
        "map_width": MAP_WIDTH,
        "map_height": MAP_HEIGHT,
        "current_tick": 0,
        "global_event": "NONE",
        "created_at": datetime.now(timezone.utc),
    }
    await db.worlds.insert_one(world_doc)

    # 2. Cria os Clãs
    created_clans = {}
    for spec_id in world_data.species_ids:
        species_doc = await db.species.find_one({"_id": spec_id})
        if not species_doc:
            continue

        clan_doc = {
            "_id": ObjectId(),
            "name": f"Clã de {species_doc['name']}",
            "species_id": spec_id,
            "world_id": world_id,
        }
        await db.clans.insert_one(clan_doc)
        created_clans[spec_id] = {
            "id": clan_doc["_id"],
            "name": clan_doc["name"],
            "species_name": species_doc["name"],
        }

    all_resource_types = await db.resource_types.find().to_list(length=None)
    territories_to_create = []
    resource_nodes_to_create = []

    def rects_overlap(a, b):
        return not (
            a["end_x"] <= b["start_x"]
            or a["start_x"] >= b["end_x"]
            or a["end_y"] <= b["start_y"]
            or a["start_y"] >= b["end_y"]
        )

    for spec_id, clan_info in created_clans.items():
        placed = False
        for _ in range(100):
            start_x = random.randint(50, MAP_WIDTH - 250)
            start_y = random.randint(50, MAP_HEIGHT - 250)
            candidate_rect = {
                "start_x": start_x,
                "start_y": start_y,
                "end_x": start_x + 200,
                "end_y": start_y + 200,
            }
            if not any(rects_overlap(candidate_rect, t) for t in territories_to_create):
                territory_doc = {
                    "_id": ObjectId(),
                    "world_id": world_id,
                    "name": f"Território de {clan_info['name']}",
                    "owner_clan_id": clan_info["id"],
                    **candidate_rect,
                }
                territories_to_create.append(territory_doc)
                placed = True
                break
        if not placed:
            continue

        species_name = clan_info["species_name"].lower()
        resource_map = {
            "anão": [("Minério de Ferro", 10), ("Pedra", 15)],
            "elfo": [("Madeira", 15), ("Baga Silvestre", 5)],
            "humano": [("Peixe", 5), ("Madeira", 5), ("Pedra", 5)],
            "orc": [("Madeira", 10), ("Peixe", 5)],
            "default": [("Baga Silvestre", 10), ("Pedra", 5)],
        }
        resources_for_species = resource_map.get(
            species_name,
            resource_map.get(species_name.rstrip("s"), resource_map["default"]),
        )

        for resource_name, count in resources_for_species:
            res_type = next(
                (rt for rt in all_resource_types if rt["name"] == resource_name), None
            )
            if not res_type:
                continue
            for _ in range(count):
                node_doc = {
                    "_id": ObjectId(),
                    "world_id": world_id,
                    "resource_type_id": res_type["_id"],
                    "category": res_type["category"],
                    "position": {
                        "x": random.uniform(
                            territory_doc["start_x"], territory_doc["end_x"]
                        ),
                        "y": random.uniform(
                            territory_doc["start_y"], territory_doc["end_y"]
                        ),
                    },
                    "quantity": random.randint(20, 50),
                    "is_depleted": False,
                }
                resource_nodes_to_create.append(node_doc)

    # <<< MUDANÇA PRINCIPAL COMEÇA AQUI >>>

    # 4. Adiciona Recursos Genéricos no Resto do Mapa
    if all_resource_types:
        # Função auxiliar para verificar se um ponto está dentro de algum território já definido
        def is_point_in_any_territory(x, y, territories):
            for t in territories:
                if t["start_x"] <= x <= t["end_x"] and t["start_y"] <= y <= t["end_y"]:
                    return True
            return False

        # Define quantos recursos aleatórios queremos espalhar pelo mapa
        NUM_GENERIC_RESOURCES = 50

        for _ in range(NUM_GENERIC_RESOURCES):
            # Tenta encontrar uma posição válida (fora de territórios)
            for _ in range(100):  # Tenta 100 vezes
                pos_x = random.uniform(0, MAP_WIDTH)
                pos_y = random.uniform(0, MAP_HEIGHT)

                if not is_point_in_any_territory(pos_x, pos_y, territories_to_create):
                    # Escolhe um tipo de recurso aleatório
                    random_res_type = random.choice(all_resource_types)

                    node_doc = {
                        "_id": ObjectId(),
                        "world_id": world_id,
                        "resource_type_id": random_res_type["_id"],
                        "category": random_res_type["category"],
                        "position": {"x": pos_x, "y": pos_y},
                        "quantity": random.randint(15, 40),
                        "is_depleted": False,
                    }
                    resource_nodes_to_create.append(node_doc)
                    break  # Posição encontrada, vai para o próximo recurso

    # 5. Insere Territórios e Recursos no Banco de Dados
    if territories_to_create:
        await db.territories.insert_many(territories_to_create)
    if resource_nodes_to_create:
        await db.resource_nodes.insert_many(resource_nodes_to_create)

    # 6. Cria os Personagens
    new_chars = []
    for spec_id in world_data.species_ids:
        species_doc = await db.species.find_one({"_id": spec_id})
        clan_info = created_clans.get(spec_id, {})
        territory_doc = next(
            (
                t
                for t in territories_to_create
                if t["owner_clan_id"] == clan_info.get("id")
            ),
            None,
        )

        for i in range(world_data.initial_agents_per_species):

            # <<< MUDANÇA PRINCIPAL COMEÇA AQUI >>>

            # 1. Obter o nome da espécie e a expectativa de vida em anos a partir das constantes
            species_name = species_doc.get("name", "").lower()
            # Usamos 70 como um padrão seguro caso a espécie não esteja no dicionário
            lifespan_in_years = SPECIES_LIFESPAN_YEARS.get(species_name, 70)

            if lifespan_in_years:
                # 2. Calcular a idade de morte média em "ticks"
                avg_death_age_ticks = lifespan_in_years * TICKS_PER_YEAR

                # 3. Adicionar variabilidade para tornar mais realista (ex: +/- 20%)
                min_lifespan_ticks = int(avg_death_age_ticks * 0.8)
                max_lifespan_ticks = int(avg_death_age_ticks * 1.2)
                death_age_in_ticks = random.randint(
                    min_lifespan_ticks, max_lifespan_ticks
                )
            else:
                # Caso de zumbis ou outras criaturas "imortais"
                death_age_in_ticks = None

            # <<< FIM DA MUDANÇA >>>

            px, py = (random.uniform(50, 950), random.uniform(50, 950))
            if territory_doc:
                px = random.uniform(territory_doc["start_x"], territory_doc["end_x"])
                py = random.uniform(territory_doc["start_y"], territory_doc["end_y"])

            char_doc = {
                # ID será gerado pelo MongoDB
                "name": f"{species_doc['name']} {i + 1}",
                "world_id": world_id,
                "gender": random.choice(["masculino", "feminino"]),
                "status": "VIVO",
                "species": {
                    "id": spec_id,
                    "name": species_doc["name"],
                    "base_strength": species_doc["base_strength"],
                    "base_health": species_doc["base_health"],
                    "max_offspring": species_doc.get("max_offspring", 1),
                },
                "clan": {"id": clan_info.get("id"), "name": clan_info.get("name")},
                "current_health": species_doc["base_health"],
                "position": {"x": px, "y": py},
                "vitals": {"fome": 0, "energia": 100, "idade": 0},
                # O novo valor calculado é inserido aqui
                "lifespan": {"death_age_ticks": death_age_in_ticks},
                "personality": {
                    "bravura": random.randint(25, 75),
                    "cautela": random.randint(25, 75),
                    "sociabilidade": random.randint(25, 75),
                    "ganancia": random.randint(25, 75),
                    "inteligencia": random.randint(25, 75),
                },
                "stats": {
                    "kills": 0,
                    "deaths": 0,
                    "damageDealt": 0,
                    "resourcesCollected": 0,
                    "children_count": 0,
                },
                "inventory": [],
                "notableEvents": [],
                "lastUpdate": datetime.now(timezone.utc),
            }
            new_chars.append(char_doc)

    if new_chars:
        await db.characters.insert_many(new_chars)

    # 7. Retorna o documento do mundo criado
    created_world_doc = await db.worlds.find_one({"_id": world_id})
    return jsonable_encoder(created_world_doc, custom_encoder={ObjectId: str})


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

    # Normalize analytics document: some jobs write metrics nested under 'analytics',
    # while seed/other code may use top-level fields. Merge them so the front always
    # receives a consistent structure.
    normalized_analytics = None
    if analytics_doc:
        if isinstance(analytics_doc.get("analytics"), dict):
            # Start with nested analytics
            normalized = dict(analytics_doc.get("analytics") or {})
            # If there are top-level convenience fields (seed or older code), prefer them
            for key in (
                "worldName",
                "currentTick",
                "population",
                "activeWars",
                "leaderboards",
                "lastUpdate",
            ):
                if key in analytics_doc and analytics_doc.get(key) is not None:
                    # don't overwrite existing nested keys unless missing
                    normalized.setdefault(key, analytics_doc.get(key))
            normalized_analytics = normalized
        else:
            # fallback: use the document as-is
            normalized_analytics = analytics_doc

    full_state = {
        "world": world_doc,
        "analytics": normalized_analytics,
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

    # 1. Primeiro, o motor da IA processa todas as ações e consequências
    await engine.process_tick(db, world_obj_id)

    # 2. AGORA, o orquestrador avança o tempo do mundo no banco de dados
    await db.worlds.update_one({"_id": world_obj_id}, {"$inc": {"current_tick": 1}})

    # 3. Com o tick já atualizado no DB, buscamos o estado final e completo
    updated_world_state = await get_full_world_state(world_id, db, current_user)

    # 4. Envia o estado atualizado (com o novo current_tick) para todos os clientes
    message_str = json.dumps(
        jsonable_encoder(updated_world_state, custom_encoder={ObjectId: str})
    )
    await manager.broadcast(message_str, world_id)

    # 5. Retorna a parte 'world' do estado para a resposta HTTP
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
    Deleta um mundo e todos os dados associados de forma segura e completa.
    Requer que o usuário seja proprietário do mundo.
    """
    # 1. Validação rigorosa do ObjectId
    try:
        world_obj_id = ObjectId(world_id)
    except InvalidId:  # pyright: ignore[reportUndefinedVariable]
        raise HTTPException(status_code=400, detail="Formato do ID do mundo inválido.")

    # 2. Verifica se o mundo existe e se pertence ao usuário logado
    world_doc = await db.worlds.find_one(
        {"_id": world_obj_id, "user_id": current_user["_id"]}
    )
    if not world_doc:
        raise HTTPException(
            status_code=404, detail="Mundo não encontrado ou acesso não autorizado."
        )

    # Dicionário para armazenar a contagem de itens deletados
    deletion_counts = {}

    # 3. Define os filtros simples e consistentes
    filter_by_world_id = {"world_id": world_obj_id}
    filter_for_events = {"worldId": world_obj_id}

    # 4. Obtém os IDs de clãs e personagens ANTES de deletá-los, para limpar os relacionamentos depois
    clan_docs = await db.clans.find(filter_by_world_id, {"_id": 1}).to_list(length=None)
    clan_ids = [c["_id"] for c in clan_docs]

    char_docs = await db.characters.find(filter_by_world_id, {"_id": 1}).to_list(
        length=None
    )
    char_ids = [c["_id"] for c in char_docs]

    # 5. Executa as exclusões em massa nas coleções principais
    res = await db.characters.delete_many(filter_by_world_id)
    deletion_counts["characters"] = res.deleted_count

    res = await db.territories.delete_many(filter_by_world_id)
    deletion_counts["territories"] = res.deleted_count

    res = await db.resource_nodes.delete_many(filter_by_world_id)
    deletion_counts["resource_nodes"] = res.deleted_count

    res = await db.events.delete_many(filter_for_events)
    deletion_counts["events"] = res.deleted_count

    res = await db.clans.delete_many(filter_by_world_id)
    deletion_counts["clans"] = res.deleted_count

    # Tenta deletar missões, se a coleção existir
    try:
        res = await db.missions.delete_many(filter_by_world_id)
        deletion_counts["missions"] = res.deleted_count
    except Exception:
        deletion_counts["missions"] = 0

    # 6. Limpa as coleções de relacionamentos
    if clan_ids:
        res = await db.clan_relationships.delete_many(
            {
                "$or": [
                    {"clan_a_id": {"$in": clan_ids}},
                    {"clan_b_id": {"$in": clan_ids}},
                ]
            }
        )
        deletion_counts["clan_relationships"] = res.deleted_count
    else:
        deletion_counts["clan_relationships"] = 0

    if char_ids:
        res = await db.character_relationships.delete_many(
            {
                "$or": [
                    {"character_a_id": {"$in": char_ids}},
                    {"character_b_id": {"$in": char_ids}},
                ]
            }
        )
        deletion_counts["character_relationships"] = res.deleted_count
    else:
        deletion_counts["character_relationships"] = 0

    # 7. Deleta os documentos de análise e, por último, o próprio mundo
    res = await db.world_analytics.delete_one({"_id": world_obj_id})
    deletion_counts["world_analytics"] = res.deleted_count

    res = await db.worlds.delete_one({"_id": world_obj_id})
    deletion_counts["world"] = res.deleted_count

    return {
        "message": "Mundo e todos os dados relacionados foram deletados com sucesso.",
        "deleted_counts": deletion_counts,
    }


@router.get("/{world_id}/analytics", response_model=dict)
async def get_world_analytics(
    world_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    # A dependência get_current_user já é aplicada a todo o router
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna o documento de análise completo para um mundo, contendo todos os
    relatórios pré-processados pelo Spark.
    """
    try:
        world_obj_id = ObjectId(world_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid World ID format.")

    # Busca o documento 'world_analytics' correspondente
    analytics_doc = await db.world_analytics.find_one({"_id": world_obj_id})

    if not analytics_doc:
        raise HTTPException(
            status_code=404,
            detail="Analytics data not found for this world. Run the Spark analysis job first.",
        )

    # O documento já está quase pronto para ser enviado.
    # O jsonable_encoder garante que o _id e outras datas sejam serializados.
    return jsonable_encoder(analytics_doc, custom_encoder={ObjectId: str})
