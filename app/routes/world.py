from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from fastapi.encoders import jsonable_encoder

from ..database import models
from ..schemas import world as world_schemas
from ..schemas import characters as char_schemas
from ..schemas import game_elements as ge_schemas
from ..dependencies import get_db 
from ..simulation import engine
from ..simulation.connection_manager import manager

router = APIRouter(
	prefix="/api/worlds",
	tags=["World & Simulation"],
	responses={404: {"description": "Not found"}},
)

# ... (as rotas POST /, GET / e GET /{world_id} permanecem as mesmas) ...
@router.post("/", response_model=world_schemas.World, status_code=201)
def create_world(world: world_schemas.WorldCreate, db: Session = Depends(get_db)):
	db_world = models.World(**world.dict())
	db.add(db_world)
	db.commit()
	db.refresh(db_world)
	return db_world

@router.get("/", response_model=list[world_schemas.World])
def read_all_worlds(db: Session = Depends(get_db)):
	return db.query(models.World).all()

@router.get("/{world_id}", response_model=world_schemas.World)
def read_world_by_id(world_id: int, db: Session = Depends(get_db)):
	db_world = db.query(models.World).filter(models.World.id == world_id).first()
	if not db_world:
		raise HTTPException(404, "World not found")
	return db_world

@router.get("/{world_id}/state", response_model=dict)
def get_full_world_state(world_id: int, db: Session = Depends(get_db)):
    db_world = db.query(models.World).filter(models.World.id == world_id).first()
    if not db_world: raise HTTPException(404, "World not found")

    all_characters = db.query(models.Character).filter(models.Character.world_id == world_id).all()
    recent_events = db.query(models.EventLog).filter(models.EventLog.world_id == world_id).order_by(models.EventLog.timestamp.desc()).limit(15).all()
    # --- NOVAS QUERIES ---
    all_territories = db.query(models.Territory).filter(models.Territory.world_id == world_id).all()
    all_resource_nodes = db.query(models.ResourceNode).join(models.Territory).filter(models.Territory.world_id == world_id).all()
    
    # --- CONVERSÃO PARA SCHEMAS ---
    characters_data = [char_schemas.Character.model_validate(c) for c in all_characters]
    world_data = world_schemas.World.model_validate(db_world)
    events_data = [world_schemas.EventLog.model_validate(e) for e in recent_events]
    territories_data = [ge_schemas.Territory.model_validate(t) for t in all_territories]
    nodes_data = [ge_schemas.ResourceNode.model_validate(n) for n in all_resource_nodes]

    full_state = {
        "world": world_data,
        "characters": characters_data,
        "events": events_data,
        "territories": territories_data, # <-- Adicionado
        "resourceNodes": nodes_data,   # <-- Adicionado
    }
    return jsonable_encoder(full_state)

@router.post("/{world_id}/tick", response_model=world_schemas.World)
async def advance_simulation_tick(world_id: int, db: Session = Depends(get_db)):
	db_world = db.query(models.World).filter(models.World.id == world_id).first()
	if not db_world: raise HTTPException(404, "World not found")
	
	engine.process_tick(db, world_id)
	
	db_world.current_tick += 1
	db.commit()
	db.refresh(db_world)

	# Busca todos os dados novamente para garantir consistência
	all_characters = db.query(models.Character).filter(models.Character.world_id == world_id).all()
	recent_events = db.query(models.EventLog).filter(models.EventLog.world_id == world_id).order_by(models.EventLog.timestamp.desc()).limit(15).all()
	all_territories = db.query(models.Territory).filter(models.Territory.world_id == world_id).all()
	all_resource_nodes = db.query(models.ResourceNode).join(models.Territory).filter(models.Territory.world_id == world_id).all()

	# Converte tudo para os schemas
	characters_data = [char_schemas.Character.model_validate(c) for c in all_characters]
	world_data = world_schemas.World.model_validate(db_world)
	events_data = [world_schemas.EventLog.model_validate(e) for e in recent_events]
	territories_data = [ge_schemas.Territory.model_validate(t) for t in all_territories]
	nodes_data = [ge_schemas.ResourceNode.model_validate(n) for n in all_resource_nodes]

	full_state = {
		"world": world_data,
		"characters": characters_data,
		"events": events_data,
		"territories": territories_data, # <-- Adicionado
        "resourceNodes": nodes_data,   # <-- Adicionado
	}
	
	json_compatible_state = jsonable_encoder(full_state)
	await manager.broadcast(json.dumps(json_compatible_state), world_id)
	
	return db_world
