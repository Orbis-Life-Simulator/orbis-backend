from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import crud, models, schemas, database

router = APIRouter(prefix="/species", tags=["species"])

@router.post("/", response_model=schemas.Species)
def create_species(species: schemas.SpeciesCreate, db: Session = Depends(database.get_db)):
    return crud.create_species(db=db, species=species)

@router.get("/", response_model=list[schemas.Species])
def read_species(skip: int = 0, limit: int = 10, db: Session = Depends(database.get_db)):
    return crud.get_species(db, skip=skip, limit=limit)
