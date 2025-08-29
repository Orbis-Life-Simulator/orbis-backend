from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Importa a dependência 'get_db' para injetar a sessão do banco de dados.
from app.dependencies import get_db

# Importa os modelos SQLAlchemy e os schemas Pydantic.
from ..database import models
from ..schemas import species as species_schemas
from ..database.database import SessionLocal

# Cria um APIRouter para organizar as rotas relacionadas a Espécies.
router = APIRouter(
    prefix="/api/species",
    tags=["Species"],  # Agrupa estas rotas na documentação da API.
    responses={404: {"description": "Not found"}},
)


# --- Endpoint para CRIAR uma nova espécie (POST) ---
@router.post("/", response_model=species_schemas.Species, status_code=201)
def create_species(
    species: species_schemas.SpeciesCreate, db: Session = Depends(get_db)
):
    """
    Cria uma nova espécie no banco de dados.
    """
    # Cria uma instância do modelo SQLAlchemy 'Species' a partir dos dados do schema Pydantic.
    db_species = models.Species(**species.dict())
    # Adiciona o novo objeto à sessão do SQLAlchemy.
    db.add(db_species)
    # Confirma a transação, salvando os dados no banco.
    db.commit()
    # Atualiza o objeto 'db_species' com os dados do banco (como o ID gerado).
    db.refresh(db_species)
    return db_species


# --- Endpoint para LER todas as espécies (GET) ---
@router.get("/", response_model=List[species_schemas.Species])
def read_all_species(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retorna uma lista de todas as espécies, com suporte a paginação.
    """
    # Constrói e executa uma consulta para buscar espécies, aplicando paginação.
    species_list = db.query(models.Species).offset(skip).limit(limit).all()
    return species_list


# --- Endpoint para LER uma espécie específica pelo ID (GET) ---
@router.get("/{species_id}", response_model=species_schemas.Species)
def read_species_by_id(species_id: int, db: Session = Depends(get_db)):
    """
    Retorna uma única espécie pelo seu ID.
    """
    # Busca a primeira espécie que corresponde ao ID fornecido.
    db_species = (
        db.query(models.Species).filter(models.Species.id == species_id).first()
    )
    # Se nenhuma espécie for encontrada, lança um erro HTTP 404.
    if db_species is None:
        raise HTTPException(status_code=404, detail="Species not found")
    return db_species


# --- Endpoint para ATUALIZAR uma espécie (PUT) ---
@router.put("/{species_id}", response_model=species_schemas.Species)
def update_species(
    species_id: int,
    species: species_schemas.SpeciesCreate,
    db: Session = Depends(get_db),
):
    """
    Atualiza completamente os dados de uma espécie existente.
    O método PUT espera que todos os campos do modelo sejam fornecidos no corpo da requisição.
    """
    # Primeiro, busca a espécie que se deseja atualizar.
    db_species = (
        db.query(models.Species).filter(models.Species.id == species_id).first()
    )
    if db_species is None:
        raise HTTPException(status_code=404, detail="Species not found")

    # Atualiza cada atributo do objeto SQLAlchemy com os novos dados do schema Pydantic.
    db_species.name = species.name
    db_species.base_health = species.base_health
    db_species.base_strength = species.base_strength

    # Confirma a transação para salvar as alterações.
    db.commit()
    # Atualiza o objeto para refletir os dados salvos.
    db.refresh(db_species)
    return db_species


# --- Endpoint para DELETAR uma espécie (DELETE) ---
@router.delete("/{species_id}", status_code=204)
def delete_species(species_id: int, db: Session = Depends(get_db)):
    """
    Deleta uma espécie pelo seu ID.
    """
    # Busca a espécie a ser deletada.
    db_species = (
        db.query(models.Species).filter(models.Species.id == species_id).first()
    )
    if db_species is None:
        raise HTTPException(status_code=404, detail="Species not found")

    # Remove o objeto da sessão do SQLAlchemy.
    db.delete(db_species)
    # Confirma a transação, efetivando a remoção no banco de dados.
    db.commit()

    # Para uma resposta com status 204 (No Content), o corpo da resposta deve ser vazio.
    # Retornar `None` ou `Response(status_code=204)` é a prática padrão.
    # O FastAPI pode lidar com o retorno de um dicionário, mas isso não é o ideal para este status code.
    return  # Retorna uma resposta vazia.```
