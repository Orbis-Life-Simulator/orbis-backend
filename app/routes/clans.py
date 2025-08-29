from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Importa a função `get_db` que fornece uma sessão de banco de dados para a rota.
# Este é o mecanismo de Injeção de Dependência do FastAPI.
from app.dependencies import get_db

# Importa os modelos de dados do SQLAlchemy (a representação das tabelas do banco de dados).
from ..database import models

# Importa os schemas Pydantic para clãs (a representação dos dados na API).
from ..schemas import clans as clan_schemas

# Embora `get_db` seja o método preferencial, esta importação também está presente.
from ..database.database import SessionLocal

# Cria uma instância de APIRouter para organizar as rotas relacionadas a clãs.
# Todas as rotas neste arquivo serão prefixadas com "/api/clans".
router = APIRouter(
    prefix="/api/clans",
    # A tag "Clans" agrupará estas rotas na documentação automática da API (Swagger UI).
    tags=["Clans"],
    # Define uma resposta padrão para o erro 404 (Não Encontrado) na documentação.
    responses={404: {"description": "Not found"}},
)


# --- Endpoint para CRIAR um novo clã (POST) ---
@router.post("/", response_model=clan_schemas.Clan, status_code=201)
def create_clan(clan: clan_schemas.ClanCreate, db: Session = Depends(get_db)):
    """
    Cria um novo clã.

    - `clan`: O corpo da requisição (JSON) é validado pelo schema Pydantic `ClanCreate`.
    - `db`: Uma sessão do banco de dados é injetada na função pela dependência `get_db`.
    - `response_model`: Garante que a resposta da API será formatada de acordo com o schema `Clan`.
    - `status_code`: Define o código de status HTTP como 201 (Created) para uma criação bem-sucedida.
    """
    # Cria uma instância do modelo SQLAlchemy `models.Clan` a partir dos dados do schema Pydantic.
    db_clan = models.Clan(**clan.dict())

    # Adiciona o novo objeto de clã à sessão do SQLAlchemy (preparando para salvar).
    db.add(db_clan)
    # Confirma a transação, salvando o novo clã no banco de dados.
    db.commit()
    # Atualiza o objeto `db_clan` com os dados recém-salvos (incluindo o ID gerado pelo banco).
    db.refresh(db_clan)

    # Retorna o clã criado, que será serializado para JSON pelo FastAPI.
    return db_clan


# --- Endpoint para LER todos os clãs (GET) ---
@router.get("/", response_model=List[clan_schemas.Clan])
def read_all_clans(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retorna uma lista de todos os clãs, com suporte a paginação.

    - `skip` e `limit`: Parâmetros de consulta (query parameters) para controlar a paginação.
    """
    # Executa uma consulta ao banco de dados para buscar todos os registros da tabela `Clan`.
    # `.offset(skip)` pula os primeiros 'skip' registros.
    # `.limit(limit)` restringe o número de resultados a 'limit'.
    clans_list = db.query(models.Clan).offset(skip).limit(limit).all()
    return clans_list


# --- Endpoint para LER um clã específico pelo ID (GET) ---
@router.get("/{clan_id}", response_model=clan_schemas.Clan)
def read_clan_by_id(clan_id: int, db: Session = Depends(get_db)):
    """
    Retorna um único clã pelo seu ID.

    - `clan_id`: Parâmetro de caminho (path parameter) extraído da URL.
    """
    # Consulta o banco de dados para encontrar o primeiro clã cujo ID corresponde ao fornecido.
    db_clan = db.query(models.Clan).filter(models.Clan.id == clan_id).first()

    # Se a consulta não retornar nenhum resultado, `db_clan` será None.
    # Nesse caso, uma exceção HTTP 404 é lançada, resultando em uma resposta de erro para o cliente.
    if db_clan is None:
        raise HTTPException(status_code=404, detail="Clan not found")

    # Se o clã foi encontrado, ele é retornado.
    return db_clan


# Como o comentário sugere, este é o local ideal para adicionar endpoints
# para atualizar (PUT/PATCH) e deletar (DELETE) clãs, seguindo padrões
# semelhantes aos vistos em outros arquivos de rota.
