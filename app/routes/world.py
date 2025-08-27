from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import models
from ..schemas import world as world_schemas
# Supondo que a lógica da simulação estará em simulation_engine
# from ..simulation import simulation_engine 
from ..database.database import SessionLocal

router = APIRouter(
	prefix="/api/worlds",
	tags=["World & Simulation"],
	responses={404: {"description": "Not found"}},
)

def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()

@router.post("/", response_model=world_schemas.World, status_code=201)
def create_world(world: world_schemas.WorldCreate, db: Session = Depends(get_db)):
	"""
	Cria uma nova instância do mundo/simulação.
	"""
	db_world = models.World(**world.dict())
	db.add(db_world)
	db.commit()
	db.refresh(db_world)
	return db_world

@router.get("/", response_model=List[world_schemas.World])
def read_all_worlds(db: Session = Depends(get_db)):
	"""
	Lista todas as simulações salvas.
	"""
	return db.query(models.World).all()

@router.get("/{world_id}", response_model=world_schemas.World)
def read_world_by_id(world_id: int, db: Session = Depends(get_db)):
	"""
	Obtém o estado atual de uma simulação específica.
	"""
	db_world = db.query(models.World).filter(models.World.id == world_id).first()
	if not db_world:
		raise HTTPException(404, "World not found")
	return db_world

@router.post("/{world_id}/tick", response_model=world_schemas.World)
def advance_simulation_tick(world_id: int, db: Session = Depends(get_db)):
	"""
	Avança a simulação em um 'tick'. AQUI A MÁGICA ACONTECE.
	Esta rota chamará o motor da simulação para processar um passo.
	"""
	db_world = db.query(models.World).filter(models.World.id == world_id).first()
	if not db_world:
		raise HTTPException(404, "World not found")
	
	# --- CHAMADA PARA O MOTOR DA SIMULAÇÃO ---
	# simulation_engine.process_tick(db, world_id)
	# Por enquanto, vamos apenas incrementar o tick manualmente
	
	db_world.current_tick += 1
	db.commit()
	db.refresh(db_world)
	
	return db_world
