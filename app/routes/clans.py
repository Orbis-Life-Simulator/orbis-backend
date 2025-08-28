from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db

from ..database import models
from ..schemas import clans as clan_schemas
from ..database.database import SessionLocal

router = APIRouter(
	prefix="/api/clans",
	tags=["Clans"],
	responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=clan_schemas.Clan, status_code=201)
def create_clan(clan: clan_schemas.ClanCreate, db: Session = Depends(get_db)):
	"""
	Cria um novo clã.
	"""
	db_clan = models.Clan(**clan.dict())
	db.add(db_clan)
	db.commit()
	db.refresh(db_clan)
	return db_clan

@router.get("/", response_model=List[clan_schemas.Clan])
def read_all_clans(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
	"""
	Retorna uma lista de todos os clãs.
	"""
	clans_list = db.query(models.Clan).offset(skip).limit(limit).all()
	return clans_list

@router.get("/{clan_id}", response_model=clan_schemas.Clan)
def read_clan_by_id(clan_id: int, db: Session = Depends(get_db)):
	"""
	Retorna um único clã pelo seu ID.
	"""
	db_clan = db.query(models.Clan).filter(models.Clan.id == clan_id).first()
	if db_clan is None:
		raise HTTPException(status_code=404, detail="Clan not found")
	return db_clan

# Você pode adicionar rotas PUT e DELETE para clãs seguindo o exemplo de Species.
