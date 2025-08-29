from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Importa a dependência 'get_db' para a injeção da sessão do banco de dados.
from app.dependencies import get_db

# Importa os modelos SQLAlchemy e os schemas Pydantic.
from ..database import models
from ..schemas import (
    relationships as rel_schemas,
)  # 'rel' como apelido para 'relationships'.
from ..database.database import SessionLocal

# Cria um APIRouter para organizar as rotas relacionadas a relacionamentos.
router = APIRouter(
    prefix="/api/relationships",
    tags=["Relationships"],  # Agrupa estas rotas na documentação da API.
    responses={404: {"description": "Not found"}},
)


# --- Endpoints para Relacionamentos de Espécies (SpeciesRelationship) ---
# Estes endpoints definem as relações inatas, padrões e instintivas entre as espécies.


@router.post(
    "/species", response_model=rel_schemas.SpeciesRelationship, status_code=201
)
def create_species_relationship(
    relationship: rel_schemas.SpeciesRelationshipCreate, db: Session = Depends(get_db)
):
    """
    Define uma nova relação padrão entre duas espécies (Ex: Anões são inimigos de Elfos).
    Esta é a relação base que se aplica a todos os membros dessas espécies,
    a menos que uma relação de clã a sobreponha.
    """
    # Cria a instância do modelo SQLAlchemy a partir do schema Pydantic.
    db_rel = models.SpeciesRelationship(**relationship.dict())
    db.add(db_rel)
    db.commit()
    db.refresh(db_rel)  # Atualiza o objeto para obter o ID gerado.
    return db_rel


@router.get("/species", response_model=List[rel_schemas.SpeciesRelationship])
def get_all_species_relationships(db: Session = Depends(get_db)):
    """
    Lista todas as relações padrão definidas entre as espécies.
    """
    return db.query(models.SpeciesRelationship).all()


@router.delete("/species/{relationship_id}", status_code=204)
def delete_species_relationship(relationship_id: int, db: Session = Depends(get_db)):
    """
    Deleta uma relação entre espécies pelo seu ID.
    """
    # Busca o registro de relacionamento específico pelo seu ID.
    db_rel = (
        db.query(models.SpeciesRelationship)
        .filter(models.SpeciesRelationship.id == relationship_id)
        .first()
    )

    # Se o relacionamento não for encontrado, levanta um erro 404.
    if db_rel is None:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Deleta o registro do banco de dados.
    db.delete(db_rel)
    db.commit()

    # O status 204 No Content indica sucesso, mas sem conteúdo no corpo da resposta.
    # FastAPI lida com o retorno de `None` ou de uma `Response` vazia para este status code.
    return


# --- Endpoints para Relacionamentos de Clãs (ClanRelationship) ---
# Estes endpoints definem as relações diplomáticas, que podem mudar e sobrepor as relações de espécie.


@router.post("/clans", response_model=rel_schemas.ClanRelationship, status_code=201)
def create_clan_relationship(
    relationship: rel_schemas.ClanRelationshipCreate, db: Session = Depends(get_db)
):
    """
    Define uma nova relação política/diplomática entre dois clãs (Ex: Clã A declara guerra ao Clã B).
    Esta relação tem prioridade sobre a relação de espécie.
    """
    db_rel = models.ClanRelationship(**relationship.dict())
    db.add(db_rel)
    db.commit()
    db.refresh(db_rel)
    return db_rel


@router.get("/clans", response_model=List[rel_schemas.ClanRelationship])
def get_all_clan_relationships(db: Session = Depends(get_db)):
    """
    Lista todas as relações políticas (diplomacia) ativas entre clãs.
    """
    return db.query(models.ClanRelationship).all()
