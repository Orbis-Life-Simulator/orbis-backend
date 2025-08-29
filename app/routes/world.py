from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from fastapi.encoders import jsonable_encoder

# Importações de componentes da aplicação
from ..database import models
from ..schemas import world as world_schemas
from ..schemas import characters as char_schemas
from ..schemas import game_elements as ge_schemas
from ..dependencies import get_db
from ..simulation import engine  # O motor principal da IA e da lógica da simulação.
from ..simulation.connection_manager import (
    manager,
)  # O gerenciador de conexões WebSocket.

# Criação do APIRouter para organizar as rotas.
router = APIRouter(
    prefix="/api/worlds",
    tags=["World & Simulation"],  # Tag para agrupar na documentação da API.
    responses={404: {"description": "Not found"}},
)

# --- Endpoints CRUD Básicos para Mundos ---


@router.post("/", response_model=world_schemas.World, status_code=201)
def create_world(world: world_schemas.WorldCreate, db: Session = Depends(get_db)):
    """
    Cria um novo mundo (um novo "save game" ou instância de simulação).
    """
    db_world = models.World(**world.dict())
    db.add(db_world)
    db.commit()
    db.refresh(db_world)
    return db_world


@router.get("/", response_model=list[world_schemas.World])
def read_all_worlds(db: Session = Depends(get_db)):
    """
    Lista todos os mundos existentes.
    """
    return db.query(models.World).all()


@router.get("/{world_id}", response_model=world_schemas.World)
def read_world_by_id(world_id: int, db: Session = Depends(get_db)):
    """
    Retorna os detalhes de um único mundo pelo seu ID.
    """
    db_world = db.query(models.World).filter(models.World.id == world_id).first()
    if not db_world:
        raise HTTPException(status_code=404, detail="World not found")
    return db_world


# --- Endpoint para Obter o Estado Completo do Mundo ---


@router.get("/{world_id}/state", response_model=dict)
def get_full_world_state(world_id: int, db: Session = Depends(get_db)):
    """
    Retorna uma "fotografia" completa do estado atual de um mundo.
    Este endpoint é ideal para o frontend carregar a visualização inicial da simulação.
    """
    db_world = db.query(models.World).filter(models.World.id == world_id).first()
    if not db_world:
        raise HTTPException(status_code=404, detail="World not found")

    # --- Coleta de Dados do Banco ---
    # Busca todas as entidades associadas a este mundo.
    all_characters = (
        db.query(models.Character).filter(models.Character.world_id == world_id).all()
    )
    recent_events = (
        db.query(models.EventLog)
        .filter(models.EventLog.world_id == world_id)
        .order_by(models.EventLog.timestamp.desc())
        .limit(15)
        .all()
    )
    all_territories = (
        db.query(models.Territory).filter(models.Territory.world_id == world_id).all()
    )
    all_resource_nodes = (
        db.query(models.ResourceNode)
        .filter(models.ResourceNode.world_id == world_id)
        .all()
    )  # Simplificado

    # --- Conversão para Schemas Pydantic ---
    # É uma boa prática converter os objetos ORM em schemas Pydantic para garantir que
    # os dados enviados na resposta da API sigam a estrutura definida e sejam serializáveis.
    characters_data = [char_schemas.Character.model_validate(c) for c in all_characters]
    world_data = world_schemas.World.model_validate(db_world)
    events_data = [world_schemas.EventLog.model_validate(e) for e in recent_events]
    territories_data = [ge_schemas.Territory.model_validate(t) for t in all_territories]
    nodes_data = [ge_schemas.ResourceNode.model_validate(n) for n in all_resource_nodes]

    # Monta o objeto de estado completo.
    full_state = {
        "world": world_data,
        "characters": characters_data,
        "events": events_data,
        "territories": territories_data,
        "resourceNodes": nodes_data,
    }

    # Usa o `jsonable_encoder` do FastAPI para garantir que todos os tipos de dados
    # (como datetimes) sejam convertidos para um formato compatível com JSON.
    return jsonable_encoder(full_state)


# --- Endpoint para Avançar a Simulação ---


@router.post("/{world_id}/tick", response_model=world_schemas.World)
async def advance_simulation_tick(world_id: int, db: Session = Depends(get_db)):
    """
    Executa um único "passo" (tick) da simulação para o mundo especificado.
    Esta é a função central que faz o mundo evoluir.
    """
    db_world = db.query(models.World).filter(models.World.id == world_id).first()
    if not db_world:
        raise HTTPException(status_code=404, detail="World not found")

    # --- 1. Processa a Lógica da Simulação ---
    # Chama a função principal do motor da simulação, que modifica os estados dos personagens,
    # cria eventos, etc., diretamente na sessão 'db' do banco de dados.
    engine.process_tick(db, world_id)

    # --- 2. Atualiza o Estado Global do Mundo ---
    db_world.current_tick += 1
    db.commit()  # Salva as mudanças do tick e o incremento do contador.
    db.refresh(db_world)  # Atualiza o objeto 'db_world' com os dados do banco.

    # --- 3. Prepara e Transmite o Novo Estado ---
    # Reúne todos os dados atualizados do mundo para enviar aos clientes conectados.
    # Esta parte é semelhante ao endpoint get_full_world_state, mas é executada *após* o tick.
    all_characters = (
        db.query(models.Character).filter(models.Character.world_id == world_id).all()
    )
    recent_events = (
        db.query(models.EventLog)
        .filter(models.EventLog.world_id == world_id)
        .order_by(models.EventLog.timestamp.desc())
        .limit(15)
        .all()
    )
    all_territories = (
        db.query(models.Territory).filter(models.Territory.world_id == world_id).all()
    )
    all_resource_nodes = (
        db.query(models.ResourceNode)
        .filter(models.ResourceNode.world_id == world_id)
        .all()
    )

    # Converte os dados para schemas Pydantic.
    characters_data = [char_schemas.Character.model_validate(c) for c in all_characters]
    world_data = world_schemas.World.model_validate(db_world)
    events_data = [world_schemas.EventLog.model_validate(e) for e in recent_events]
    territories_data = [ge_schemas.Territory.model_validate(t) for t in all_territories]
    nodes_data = [ge_schemas.ResourceNode.model_validate(n) for n in all_resource_nodes]

    full_state = {
        "world": world_data,
        "characters": characters_data,
        "events": events_data,
        "territories": territories_data,
        "resourceNodes": nodes_data,
    }

    # Codifica o estado para um formato JSON compatível.
    json_compatible_state = jsonable_encoder(full_state)

    # --- 4. Transmissão via WebSocket ---
    # Usa o 'manager' para transmitir (broadcast) o estado completo e atualizado
    # para todos os clientes que estão "ouvindo" este 'world_id'.
    # A função é 'async' por causa desta operação de I/O (rede).
    await manager.broadcast(json.dumps(json_compatible_state), world_id)

    # Retorna a resposta HTTP para o cliente que iniciou o tick.
    # Isso serve como uma confirmação de que o tick foi processado.
    return db_world
