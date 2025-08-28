from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db

from ..database import models
from ..schemas import game_elements as ge_schemas
from ..database.database import SessionLocal

router = APIRouter(
	prefix="/api/world-elements",
	tags=["World Elements"],
	responses={404: {"description": "Not found"}},
)

@router.post("/resources", response_model=ge_schemas.ResourceType, status_code=201)
def create_resource_type(resource: ge_schemas.ResourceTypeCreate, db: Session = Depends(get_db)):
	"""
	Cria um novo tipo de recurso que pode existir no mundo (Madeira, Peixe, etc.).
	"""
	db_resource = models.ResourceType(**resource.dict())
	db.add(db_resource)
	db.commit()
	db.refresh(db_resource)
	return db_resource

@router.get("/resources", response_model=List[ge_schemas.ResourceType])
def get_all_resource_types(db: Session = Depends(get_db)):
	"""
	Lista todos os tipos de recursos existentes.
	"""
	return db.query(models.ResourceType).all()

# --- Rotas para Territories ---

@router.post("/territories", response_model=ge_schemas.Territory, status_code=201)
def create_territory(territory: ge_schemas.TerritoryCreate, db: Session = Depends(get_db)):
	"""
	Define uma nova região no mapa (Floresta de Aetherion, Minas de Durvak, etc.).
	"""
	db_territory = models.Territory(**territory.dict())
	db.add(db_territory)
	db.commit()
	db.refresh(db_territory)
	return db_territory

@router.get("/territories", response_model=List[ge_schemas.Territory])
def get_all_territories(db: Session = Depends(get_db)):
	"""
	Lista todas as regiões definidas no mapa.
	"""
	return db.query(models.Territory).all()

# --- Rotas para Ligar Recursos a Territórios ---

# Schema local, pois é muito específico para esta operação
class TerritoryResourceLink(ge_schemas.BaseModel):
	resource_type_id: int
	abundance: float

@router.post("/territories/{territory_id}/resources", status_code=201)
def add_resource_to_territory(territory_id: int, link: TerritoryResourceLink, db: Session = Depends(get_db)):
	"""
	Define que um certo recurso pode ser encontrado em um território, com uma certa abundância.
	"""
	# Verificar se ambos os IDs existem
	db_territory = db.query(models.Territory).get(territory_id)
	if not db_territory:
		raise HTTPException(404, "Territory not found")
	db_resource = db.query(models.ResourceType).get(link.resource_type_id)
	if not db_resource:
		raise HTTPException(404, "Resource Type not found")

	db_link = models.TerritoryResource(**link.dict(), territory_id=territory_id)
	db.add(db_link)
	db.commit()
	return {"message": "Resource linked to territory successfully"}
