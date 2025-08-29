from sqlalchemy.orm import Session

# Importa a fábrica de sessões 'SessionLocal' que foi configurada no arquivo database.py.
from app.database.database import SessionLocal


# Esta função é uma "dependência" do FastAPI.
# O sistema de Injeção de Dependência do FastAPI chamará esta função para cada
# requisição que a declarar em seus parâmetros (ex: `db: Session = Depends(get_db)`).
def get_db():
    """
    Esta função geradora cria uma sessão de banco de dados independente por requisição,
    usa essa sessão no bloco `try`, e garante que ela seja fechada no bloco `finally`.
    """
    # 1. CRIAÇÃO DA SESSÃO:
    # Cria uma nova instância de sessão a partir da nossa fábrica `SessionLocal`.
    # Cada requisição terá seu próprio objeto de sessão.
    db = SessionLocal()

    # O bloco `try...finally` é um padrão de gerenciamento de recursos em Python.
    # Ele garante que o código dentro do `finally` será executado, não importa o que
    # aconteça dentro do `try` (seja um sucesso ou um erro).
    try:
        # 2. FORNECIMENTO DA SESSÃO (YIELD):
        # A palavra-chave `yield` transforma a função em um gerador. No contexto do FastAPI,
        # o valor fornecido (aqui, o objeto `db`) é o que é injetado na rota.
        # A execução da função `get_db` "pausa" aqui, enquanto a rota e sua lógica
        # são executadas usando a sessão `db`.
        yield db
    finally:
        # 3. FECHAMENTO DA SESSÃO:
        # Assim que a rota termina de processar a requisição e a resposta é enviada,
        # a execução da função `get_db` é retomada, e o bloco `finally` é executado.
        # `db.close()` fecha a sessão, o que retorna a conexão do banco de dados
        # de volta ao "pool" de conexões, deixando-a disponível para a próxima requisição.
        # Isso é crucial para evitar o esgotamento das conexões do banco de dados.
        db.close()
