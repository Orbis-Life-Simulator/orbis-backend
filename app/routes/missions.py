from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Importa a dependência 'get_db' para gerenciar a sessão do banco de dados.
from app.dependencies import get_db

# Importa os modelos SQLAlchemy e os schemas Pydantic.
from ..database import models
from ..schemas import game_elements as ge_schemas  # Usando 'ge' como apelido.
from ..database.database import SessionLocal

# Cria um APIRouter para organizar as rotas relacionadas a missões.
router = APIRouter(
    prefix="/api/missions",
    tags=["Missions"],  # Agrupa estas rotas na documentação da API.
    responses={404: {"description": "Not found"}},
)

# --- Endpoints para Missões ---


@router.post("/", response_model=ge_schemas.Mission, status_code=201)
def create_mission(mission: ge_schemas.MissionCreate, db: Session = Depends(get_db)):
    """
    Cria uma nova missão e a atribui a um clã.
    """
    # Cria uma instância do modelo SQLAlchemy 'Mission' a partir do schema Pydantic.
    db_mission = models.Mission(**mission.dict())
    db.add(db_mission)
    db.commit()
    db.refresh(db_mission)  # Atualiza o objeto para obter o ID gerado pelo banco.
    return db_mission


@router.get("/", response_model=List[ge_schemas.Mission])
def get_all_missions(
    status: ge_schemas.MissionStatus = None, db: Session = Depends(get_db)
):
    """
    Lista todas as missões, com a opção de filtrar por status (ATIVA, CONCLUÍDA, FALHOU).

    - `status`: Um parâmetro de consulta opcional. Se fornecido (ex: /api/missions?status=ATIVA),
              a lista será filtrada.
    """
    # Inicia a consulta base, selecionando todas as missões.
    query = db.query(models.Mission)

    # Se o parâmetro 'status' foi incluído na requisição, adiciona um filtro à consulta.
    if status:
        query = query.filter(models.Mission.status == status)

    # Executa a consulta (com ou sem o filtro) e retorna todos os resultados.
    return query.all()


# --- Endpoints para Objetivos de Missões ---


@router.post(
    "/{mission_id}/objectives",
    response_model=ge_schemas.MissionObjective,
    status_code=201,
)
def create_mission_objective(
    mission_id: int,
    objective: ge_schemas.MissionObjectiveCreate,
    db: Session = Depends(get_db),
):
    """
    Adiciona um novo passo ou objetivo a uma missão já existente.
    """
    # --- Validações ---
    # Garante que o ID da missão na URL corresponde ao ID no corpo da requisição.
    # Isso previne inconsistências nos dados.
    if mission_id != objective.mission_id:
        raise HTTPException(
            status_code=400, detail="Mission ID in URL and payload do not match."
        )

    # Verifica se a missão à qual estamos tentando adicionar um objetivo realmente existe.
    db_mission = db.query(models.Mission).get(mission_id)
    if not db_mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    # --- Criação ---
    # Se as validações passarem, cria o novo objeto de objetivo.
    db_objective = models.MissionObjective(**objective.dict())
    db.add(db_objective)
    db.commit()
    db.refresh(db_objective)
    return db_objective


@router.patch("/objectives/{objective_id}", response_model=ge_schemas.MissionObjective)
def update_objective_status(
    objective_id: int, is_complete: bool, db: Session = Depends(get_db)
):
    """
    Atualiza o status de um objetivo (por exemplo, marca como concluído).

    - `objective_id`: O ID do objetivo a ser atualizado (da URL).
    - `is_complete`: O novo status booleano, enviado no corpo da requisição.
                     FastAPI espera um corpo como `{"is_complete": true}`.
    """
    # Busca o objetivo específico pelo seu ID.
    db_objective = db.query(models.MissionObjective).get(objective_id)
    if not db_objective:
        raise HTTPException(status_code=404, detail="Objective not found")

    # Atualiza o campo 'is_complete' do objeto com o valor recebido.
    db_objective.is_complete = is_complete
    db.commit()  # Salva a alteração.
    db.refresh(db_objective)  # Atualiza o objeto com o estado do banco.
    return db_objective
