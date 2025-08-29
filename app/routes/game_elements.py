from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Importa a dependência 'get_db' para injetar a sessão do banco de dados.
from app.dependencies import get_db

# Importa os modelos SQLAlchemy e os schemas Pydantic.
from ..database import models
from ..schemas import (
    game_elements as ge_schemas,
)  # 'ge' como apelido para 'game_elements'
from ..database.database import SessionLocal

# Cria um APIRouter para organizar as rotas relacionadas aos elementos do mundo.
router = APIRouter(
    prefix="/api/world-elements",
    tags=["World Elements"],  # Agrupa estas rotas na documentação da API.
    responses={404: {"description": "Not found"}},
)

# --- Endpoints para ResourceType (Tipos de Recursos) ---


@router.post("/resources", response_model=ge_schemas.ResourceType, status_code=201)
def create_resource_type(
    resource: ge_schemas.ResourceTypeCreate, db: Session = Depends(get_db)
):
    """
    Cria um novo tipo de recurso que pode existir no mundo (ex: Madeira, Peixe, Minério).
    Este endpoint define o "template" do recurso.
    """
    # Cria uma instância do modelo SQLAlchemy a partir do schema Pydantic.
    db_resource = models.ResourceType(**resource.dict())
    db.add(db_resource)
    db.commit()
    db.refresh(db_resource)  # Atualiza o objeto com o ID gerado pelo banco.
    return db_resource


@router.get("/resources", response_model=List[ge_schemas.ResourceType])
def get_all_resource_types(db: Session = Depends(get_db)):
    """
    Lista todos os tipos de recursos existentes e definidos no sistema.
    """
    # Retorna todos os registros da tabela ResourceType.
    return db.query(models.ResourceType).all()


# --- Endpoints para Territories (Territórios) ---


@router.post("/territories", response_model=ge_schemas.Territory, status_code=201)
def create_territory(
    territory: ge_schemas.TerritoryCreate, db: Session = Depends(get_db)
):
    """
    Define uma nova região/território no mapa (ex: Floresta de Aetherion, Minas de Durvak).
    """
    db_territory = models.Territory(**territory.dict())
    db.add(db_territory)
    db.commit()
    db.refresh(db_territory)
    return db_territory


@router.get("/territories", response_model=List[ge_schemas.Territory])
def get_all_territories(db: Session = Depends(get_db)):
    """
    Lista todas as regiões/territórios definidos no mapa.
    """
    return db.query(models.Territory).all()


# --- Endpoint para Ligar Recursos a Territórios ---


# Define um schema Pydantic localmente. Isso é útil quando o schema é simples
# e usado exclusivamente por este endpoint, evitando poluir o arquivo principal de schemas.
class TerritoryResourceLink(ge_schemas.BaseModel):
    resource_type_id: int  # O ID do recurso a ser adicionado.
    abundance: float  # Um valor que representa a abundância (ex: 0.8 = 80% de chance de encontrar).


@router.post("/territories/{territory_id}/resources", status_code=201)
def add_resource_to_territory(
    territory_id: int, link: TerritoryResourceLink, db: Session = Depends(get_db)
):
    """
    Associa um tipo de recurso a um território, definindo que aquele recurso
    pode ser encontrado naquela área, com uma certa abundância.
    """
    # --- Validação ---
    # Antes de criar a ligação, é crucial verificar se tanto o território quanto
    # o tipo de recurso realmente existem no banco de dados para manter a integridade referencial.

    # Busca o território pelo ID fornecido na URL. .get() é uma forma rápida de buscar pela chave primária.
    db_territory = db.query(models.Territory).get(territory_id)
    if not db_territory:
        raise HTTPException(status_code=404, detail="Territory not found")

    # Busca o tipo de recurso pelo ID fornecido no corpo da requisição.
    db_resource = db.query(models.ResourceType).get(link.resource_type_id)
    if not db_resource:
        raise HTTPException(status_code=404, detail="Resource Type not found")

    # --- Criação do Vínculo ---
    # Cria a entrada na tabela de associação (TerritoryResource) com os dados validados.
    db_link = models.TerritoryResource(**link.dict(), territory_id=territory_id)
    db.add(db_link)
    db.commit()

    # Retorna uma mensagem de sucesso, pois a operação não precisa necessariamente
    # retornar o objeto criado.
    return {"message": "Resource linked to territory successfully"}
