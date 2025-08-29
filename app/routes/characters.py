from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Importa a função de dependência que gerencia a sessão do banco de dados.
# Isso é crucial para o padrão de injeção de dependência do FastAPI.
from app.dependencies import get_db

# Importa os modelos SQLAlchemy (que representam as tabelas do banco de dados).
from ..database import models

# Importa os schemas Pydantic (que definem a estrutura dos dados da API).
from ..schemas import characters as char_schemas

# Importação direta da SessionLocal, embora get_db seja a forma preferencial de uso nas rotas.
from ..database.database import SessionLocal

# Cria uma instância de APIRouter. Isso ajuda a organizar as rotas em módulos.
# Todas as rotas definidas neste arquivo terão o prefixo "/api/characters".
router = APIRouter(
    prefix="/api/characters",
    # A 'tag' agrupa estas rotas na documentação automática da API (Swagger/OpenAPI).
    tags=["Characters"],
    # Define uma resposta padrão para o status 404, que aparecerá na documentação.
    responses={404: {"description": "Not found"}},
)


# --- Endpoint para CRIAR um novo personagem (POST) ---
@router.post("/", response_model=char_schemas.Character, status_code=201)
def create_character(
    character: char_schemas.CharacterCreate, db: Session = Depends(get_db)
):
    """
    Cria um novo personagem no banco de dados.

    - `character`: O corpo da requisição (JSON) é validado e convertido para um objeto `CharacterCreate` pelo FastAPI.
    - `db`: Uma sessão do banco de dados é injetada na função pela dependência `get_db`.
    - `response_model`: Garante que a resposta da API terá o formato do schema `Character`.
    - `status_code`: Define o código de status HTTP para "Created" em caso de sucesso.
    """
    # Converte o schema Pydantic (`character`) em um modelo SQLAlchemy (`models.Character`)
    # usando o método `.dict()` para criar a instância.
    db_character = models.Character(**character.dict())

    # Adiciona o novo objeto de personagem à sessão do banco de dados.
    db.add(db_character)
    # Confirma (salva) as mudanças no banco de dados.
    db.commit()
    # Atualiza o objeto `db_character` com os dados do banco de dados (ex: o ID que foi gerado).
    db.refresh(db_character)

    # Retorna o personagem recém-criado, que será serializado conforme o `response_model`.
    return db_character


# --- Endpoint para LER todos os personagens (GET) ---
@router.get("/", response_model=List[char_schemas.Character])
def read_all_characters(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retorna uma lista de todos os personagens com paginação.

    - `skip`: Parâmetro de consulta para pular um número de registros (para paginação).
    - `limit`: Parâmetro de consulta para limitar o número de registros retornados.
    """
    # Executa uma consulta no banco de dados para buscar todos os personagens,
    # aplicando o offset (skip) e o limit para a paginação.
    char_list = db.query(models.Character).offset(skip).limit(limit).all()
    return char_list


# --- Endpoint para LER um personagem específico pelo ID (GET) ---
@router.get("/{character_id}", response_model=char_schemas.Character)
def read_character_by_id(character_id: int, db: Session = Depends(get_db)):
    """
    Retorna um único personagem pelo seu ID.

    - `character_id`: Parâmetro de caminho, extraído da URL.
    """
    # Busca o primeiro personagem na tabela `Character` cujo ID corresponda ao fornecido.
    db_char = (
        db.query(models.Character).filter(models.Character.id == character_id).first()
    )

    # Se nenhum personagem for encontrado, lança uma exceção HTTP 404.
    # O FastAPI converte isso em uma resposta de erro JSON apropriada.
    if db_char is None:
        raise HTTPException(status_code=404, detail="Character not found")

    return db_char


# --- Endpoint para ATUALIZAR um personagem (PATCH) ---
@router.patch("/{character_id}", response_model=char_schemas.Character)
def update_character(
    character_id: int,
    character_update: char_schemas.CharacterUpdate,
    db: Session = Depends(get_db),
):
    """
    Atualiza parcialmente os dados de um personagem (posição, vida, estado, etc.).
    O método PATCH é ideal para atualizações parciais.

    - `character_update`: O corpo da requisição é validado pelo schema `CharacterUpdate`,
      onde todos os campos são opcionais.
    """
    # Primeiro, busca o personagem que se deseja atualizar.
    db_char = (
        db.query(models.Character).filter(models.Character.id == character_id).first()
    )
    if db_char is None:
        raise HTTPException(status_code=404, detail="Character not found")

    # Converte os dados recebidos em um dicionário. `exclude_unset=True` é crucial:
    # isso garante que apenas os campos que o cliente enviou na requisição
    # serão incluídos, evitando sobrescrever outros campos com `None`.
    update_data = character_update.dict(exclude_unset=True)

    # Itera sobre os dados recebidos e atualiza os atributos correspondentes
    # no objeto do modelo SQLAlchemy (`db_char`).
    for key, value in update_data.items():
        setattr(db_char, key, value)

    # Salva as alterações no banco de dados e atualiza o objeto local.
    db.commit()
    db.refresh(db_char)

    return db_char
