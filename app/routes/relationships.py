from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db

from ..database import models
from ..schemas import relationships as rel_schemas
from ..database.database import SessionLocal

router = APIRouter(
	prefix="/api/relationships",
	tags=["Relationships"],
	responses={404: {"description": "Not found"}},
)

@router.post("/species", response_model=rel_schemas.SpeciesRelationship, status_code=201)
def create_species_relationship(relationship: rel_schemas.SpeciesRelationshipCreate, db: Session = Depends(get_db)):
	"""
	Define uma nova relação padrão entre duas espécies (Ex: Anões são inimigos de Elfos).
	"""
	db_rel = models.SpeciesRelationship(**relationship.dict())
	db.add(db_rel)
	db.commit()
	db.refresh(db_rel)
	return db_rel

@router.get("/species", response_model=List[rel_schemas.SpeciesRelationship])
def get_all_species_relationships(db: Session = Depends(get_db)):
	"""
	Lista todas as relações definidas entre espécies.
	"""
	return db.query(models.SpeciesRelationship).all()

# --- Rotas para Clan Relationships ---

@router.post("/clans", response_model=rel_schemas.ClanRelationship, status_code=201)
def create_clan_relationship(relationship: rel_schemas.ClanRelationshipCreate, db: Session = Depends(get_db)):
	"""
	Define uma nova relação política entre dois clãs (Ex: Clã A declara guerra ao Clã B).
	"""
	db_rel = models.ClanRelationship(**relationship.dict())
	db.add(db_rel)
	db.commit()
	db.refresh(db_rel)
	return db_rel

@router.get("/clans", response_model=List[rel_schemas.ClanRelationship])
def get_all_clan_relationships(db: Session = Depends(get_db)):
	"""
	Lista todas as relações políticas ativas entre clãs.
	"""
	return db.query(models.ClanRelationship).all()

@router.delete("/species/{relationship_id}", status_code=204)
def delete_species_relationship(relationship_id: int, db: Session = Depends(get_db)):
	"""
	Deleta uma relação entre espécies pelo seu ID.
	"""
	db_rel = db.query(models.SpeciesRelationship).filter(models.SpeciesRelationship.id == relationship_id).first()
	if db_rel is None:
		raise HTTPException(status_code=404, detail="Relationship not found")
	
	db.delete(db_rel)
	db.commit()
	return # Retorna uma resposta vazia com status 204 No Content
