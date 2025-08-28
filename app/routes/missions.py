from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db

from ..database import models
from ..schemas import game_elements as ge_schemas
from ..database.database import SessionLocal

router = APIRouter(
	prefix="/api/missions",
	tags=["Missions"],
	responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=ge_schemas.Mission, status_code=201)
def create_mission(mission: ge_schemas.MissionCreate, db: Session = Depends(get_db)):
	"""
	Cria uma nova missão e a atribui a um clã.
	"""
	db_mission = models.Mission(**mission.dict())
	db.add(db_mission)
	db.commit()
	db.refresh(db_mission)
	return db_mission

@router.get("/", response_model=List[ge_schemas.Mission])
def get_all_missions(status: ge_schemas.MissionStatus = None, db: Session = Depends(get_db)):
	"""
	Lista todas as missões, opcionalmente filtrando por status (ATIVA, CONCLUÍDA, FALHOU).
	"""
	query = db.query(models.Mission)
	if status:
		query = query.filter(models.Mission.status == status)
	return query.all()

@router.post("/{mission_id}/objectives", response_model=ge_schemas.MissionObjective, status_code=201)
def create_mission_objective(mission_id: int, objective: ge_schemas.MissionObjectiveCreate, db: Session = Depends(get_db)):
	"""
	Adiciona um novo passo/objetivo a uma missão existente.
	"""
	if mission_id != objective.mission_id:
		raise HTTPException(status_code=400, detail="Mission ID in URL and payload do not match.")
	
	db_mission = db.query(models.Mission).get(mission_id)
	if not db_mission:
		raise HTTPException(404, "Mission not found")

	db_objective = models.MissionObjective(**objective.dict())
	db.add(db_objective)
	db.commit()
	db.refresh(db_objective)
	return db_objective

@router.patch("/objectives/{objective_id}", response_model=ge_schemas.MissionObjective)
def update_objective_status(objective_id: int, is_complete: bool, db: Session = Depends(get_db)):
	"""
	Atualiza o status de um objetivo (Ex: marca como concluído).
	"""
	db_objective = db.query(models.MissionObjective).get(objective_id)
	if not db_objective:
		raise HTTPException(404, "Objective not found")

	db_objective.is_complete = is_complete
	db.commit()
	db.refresh(db_objective)
	return db_objective
