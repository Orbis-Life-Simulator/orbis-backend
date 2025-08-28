from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db

from ..database import models
from ..schemas import species as species_schemas
from ..database.database import SessionLocal

router = APIRouter(
	prefix="/api/species",
	tags=["Species"],
	responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=species_schemas.Species, status_code=201)
def create_species(species: species_schemas.SpeciesCreate, db: Session = Depends(get_db)):
	"""
	Cria uma nova espécie.
	"""
	db_species = models.Species(**species.dict())
	db.add(db_species)
	db.commit()
	db.refresh(db_species)
	return db_species

@router.get("/", response_model=List[species_schemas.Species])
def read_all_species(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
	"""
	Retorna uma lista de todas as espécies.
	"""
	species_list = db.query(models.Species).offset(skip).limit(limit).all()
	return species_list

@router.get("/{species_id}", response_model=species_schemas.Species)
def read_species_by_id(species_id: int, db: Session = Depends(get_db)):
	"""
	Retorna uma única espécie pelo seu ID.
	"""
	db_species = db.query(models.Species).filter(models.Species.id == species_id).first()
	if db_species is None:
		raise HTTPException(status_code=404, detail="Species not found")
	return db_species

@router.put("/{species_id}", response_model=species_schemas.Species)
def update_species(species_id: int, species: species_schemas.SpeciesCreate, db: Session = Depends(get_db)):
	"""
	Atualiza os dados de uma espécie existente.
	"""
	db_species = db.query(models.Species).filter(models.Species.id == species_id).first()
	if db_species is None:
		raise HTTPException(status_code=404, detail="Species not found")
	
	db_species.name = species.name
	db_species.base_health = species.base_health
	db_species.base_strength = species.base_strength
	
	db.commit()
	db.refresh(db_species)
	return db_species

@router.delete("/{species_id}", status_code=204)
def delete_species(species_id: int, db: Session = Depends(get_db)):
	"""
	Deleta uma espécie pelo seu ID.
	"""
	db_species = db.query(models.Species).filter(models.Species.id == species_id).first()
	if db_species is None:
		raise HTTPException(status_code=404, detail="Species not found")
	
	db.delete(db_species)
	db.commit()
	return {"detail": "Species deleted successfully"}
