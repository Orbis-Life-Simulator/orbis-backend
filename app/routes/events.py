from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

# Importa a dependência 'get_db' para injetar a sessão do banco de dados em cada requisição.
from app.dependencies import get_db

# Importa os modelos SQLAlchemy (representação das tabelas do banco de dados).
from ..database import models

# Importa os schemas Pydantic relacionados ao mundo e aos logs de eventos.
from ..schemas import world as world_schemas

# A importação direta do SessionLocal é geralmente para outros usos, sendo 'get_db' o padrão para rotas.
from ..database.database import SessionLocal

# Cria uma instância do APIRouter para organizar as rotas relacionadas aos logs de eventos.
router = APIRouter(
    # Todas as rotas neste arquivo terão o prefixo "/api/events".
    prefix="/api/events",
    # Agrupa estas rotas sob a tag "Event Logs" na documentação automática da API.
    tags=["Event Logs"],
)


# --- Endpoint para LER os logs de eventos de um mundo (GET) ---
@router.get("/{world_id}", response_model=List[world_schemas.EventLog])
def get_world_events(
    world_id: int,
    limit: int = 50,
    char_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Retorna o log de eventos para um mundo específico, ordenado do mais recente para o mais antigo.
    Permite filtrar opcionalmente por um personagem específico.

    - `world_id`: (Path Parameter) O ID do mundo cujos eventos serão buscados.
    - `limit`: (Query Parameter) O número máximo de eventos a serem retornados. O padrão é 50.
    - `char_id`: (Query Parameter) Se fornecido, retorna apenas eventos onde este personagem
                 foi o ator principal ou secundário.
    - `db`: A sessão do banco de dados injetada pela dependência `get_db`.
    """
    # Inicia a construção da consulta SQLAlchemy, selecionando da tabela EventsLog
    # e aplicando um filtro inicial obrigatório pelo ID do mundo.
    # O comentário original "Assumindo world_id no log" é importante, pois confirma que
    # o modelo EventsLog tem uma coluna para associá-lo a um mundo.
    query = db.query(models.EventLog).filter(models.EventLog.world_id == world_id)

    # Se o parâmetro de consulta 'char_id' foi fornecido na URL (ex: /api/events/1?char_id=123),
    # adiciona um filtro à consulta.
    if char_id:
        # O filtro usa um 'OR' lógico para encontrar logs onde o 'char_id' fornecido
        # corresponde à coluna 'primary_char_id' OU à coluna 'secondary_char_id'.
        # Isso captura todos os eventos em que o personagem esteve envolvido.
        query = query.filter(
            (models.EventLog.primary_char_id == char_id)
            | (models.EventLog.secondary_char_id == char_id)
        )

    # Executa a consulta final com as seguintes modificações:
    # 1. .order_by(models.EventLog.timestamp.desc()): Ordena os resultados pela coluna de timestamp
    #    em ordem decrescente, garantindo que os eventos mais recentes apareçam primeiro.
    # 2. .limit(limit): Restringe o número de resultados ao valor do parâmetro 'limit'.
    # 3. .all(): Executa a consulta e retorna todos os resultados como uma lista de objetos.
    events = query.order_by(models.EventLog.timestamp.desc()).limit(limit).all()

    # Retorna a lista de eventos. O FastAPI irá serializá-la para JSON
    # de acordo com o `response_model` definido no decorador.
    return events
