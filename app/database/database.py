from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define a URL de conexão com o banco de dados.
# Neste caso, estamos usando um banco de dados SQLite.
# "sqlite:///" indica que o arquivo do banco de dados estará no sistema de arquivos local.
# "./orbis.db" é o nome do arquivo que será criado no mesmo diretório do projeto.
SQLALCHEMY_DATABASE_URL = "sqlite:///./orbis.db"

# Cria o "motor" (engine) do SQLAlchemy, que é o ponto central de comunicação
# com o banco de dados. É ele quem gerencia os pools de conexão e a dialeta específica
# do banco de dados (neste caso, SQLite).
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # O argumento `connect_args` é necessário especificamente para o SQLite.
    # Por padrão, o SQLite só permite que a conexão seja usada pela thread que a criou.
    # Como o FastAPI pode usar múltiplas threads para lidar com uma única requisição,
    # precisamos desabilitar essa verificação para evitar erros.
    connect_args={"check_same_thread": False},
)

# Cria uma classe "fábrica" de sessões chamada `SessionLocal`.
# Esta não é a sessão do banco de dados em si, mas uma classe que será usada
# para criar novas instâncias de sessão sempre que uma requisição for recebida.
SessionLocal = sessionmaker(
    autocommit=False,  # Desabilita o commit automático. As transações serão gerenciadas manualmente.
    autoflush=False,  # Desabilita o flush automático. Os dados só serão enviados ao DB quando explicitamente confirmado.
    bind=engine,  # Vincula esta fábrica de sessões ao nosso motor (engine).
)

# Cria uma classe base para nossos modelos declarativos do ORM.
# Todas as classes de modelo (como `Character`, `World`, `Species`, etc.)
# no seu arquivo `models.py` herdarão desta classe `Base`.
# É através desta base que o SQLAlchemy mapeia as classes Python para as tabelas do banco de dados.
Base = declarative_base()
