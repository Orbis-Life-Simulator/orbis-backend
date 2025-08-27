from sqlalchemy.orm import Session
from . import models, schemas

def get_species(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Species).offset(skip).limit(limit).all()

def get_species_by_id(db: Session, species_id: int):
    return db.query(models.Species).filter(models.Species.id == species_id).first()

def create_species(db: Session, species: schemas.SpeciesCreate):
    db_species = models.Species(
        name=species.name,
        base_health=species.base_health,
        base_strength=species.base_strength
    )
    db.add(db_species)
    db.commit()
    db.refresh(db_species)
    return db_species
