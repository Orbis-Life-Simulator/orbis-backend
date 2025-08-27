from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import models
from ..schemas import characters as char_schemas
from ..database.database import SessionLocal

router = APIRouter(
    prefix="/api/characters",
    tags=["Characters"],
    responses={404: {"description": "Not found"}},
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=char_schemas.Character, status_code=201)
def create_character(character: char_schemas.CharacterCreate, db: Session = Depends(get_db)):
    """
    Cria um novo personagem.
    """
    db_character = models.Character(**character.dict())
    db.add(db_character)
    db.commit()
    db.refresh(db_character)
    return db_character

@router.get("/", response_model=List[char_schemas.Character])
def read_all_characters(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retorna uma lista de todos os personagens.
    """
    char_list = db.query(models.Character).offset(skip).limit(limit).all()
    return char_list

@router.get("/{character_id}", response_model=char_schemas.Character)
def read_character_by_id(character_id: int, db: Session = Depends(get_db)):
    """
    Retorna um único personagem pelo seu ID.
    """
    db_char = db.query(models.Character).filter(models.Character.id == character_id).first()
    if db_char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    return db_char

@router.patch("/{character_id}", response_model=char_schemas.Character)
def update_character(character_id: int, character_update: char_schemas.CharacterUpdate, db: Session = Depends(get_db)):
    """
    Atualiza parcialmente os dados de um personagem (posição, vida, estado, etc.).
    """
    db_char = db.query(models.Character).filter(models.Character.id == character_id).first()
    if db_char is None:
        raise HTTPException(status_code=404, detail="Character not found")

    update_data = character_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_char, key, value)

    db.commit()
    db.refresh(db_char)
    return db_char

