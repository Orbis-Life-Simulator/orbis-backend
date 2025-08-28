from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from app.dependencies import get_db

from ..database import models
from ..schemas import world as world_schemas
from ..database.database import SessionLocal

router = APIRouter(
	prefix="/api/events",
	tags=["Event Logs"],
)


@router.get("/{world_id}", response_model=List[world_schemas.EventLog])
def get_world_events(
	world_id: int, 
	limit: int = 50, 
	char_id: Optional[int] = None,
	db: Session = Depends(get_db)
):
	"""
	Retorna o log de eventos para um mundo específico, ordenado do mais recente para o mais antigo.
	Pode ser filtrado por personagem.
	"""
	query = db.query(models.EventsLog).filter(models.EventsLog.world_id == world_id) # Assumindo world_id no log

	if char_id:
		query = query.filter(
			(models.EventsLog.primary_char_id == char_id) | 
			(models.EventsLog.secondary_char_id == char_id)
		)
		
	events = query.order_by(models.EventsLog.timestamp.desc()).limit(limit).all()
	return events
