from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Importa o 'engine' e a 'Base' do SQLAlchemy, configurados no arquivo database.py.
from .database.database import engine, Base

# Importa os módulos de rotas (APIRouters) que definem os endpoints da API.
from .routes import (
    species,
    characters,
    clans,
    world,
    events,
    relationships,
    game_elements,
    missions,
)

# Importa o gerenciador de conexões WebSocket.
from .simulation.connection_manager import manager

# --- Inicialização do Banco de Dados ---
# Esta linha é crucial. Ela instrui o SQLAlchemy a olhar todos os modelos que
# herdam da classe 'Base' (definidos em models.py) e a criar as tabelas
# correspondentes no banco de dados conectado ao 'engine', caso elas ainda não existam.
# Isso efetivamente cria o seu esquema de banco de dados na primeira vez que a aplicação é executada.
Base.metadata.create_all(bind=engine)

# --- Criação da Instância Principal do FastAPI ---
# 'app' é a instância principal da sua aplicação web.
app = FastAPI(
    # Estes metadados são usados para gerar a documentação automática da API (ex: em /docs).
    title="Orbis Life Simulator API",
    description="API para gerenciar a simulação de vida do projeto Orbis.",
    version="0.1.0",
)

# ===================================================================
# --- Configuração do Middleware CORS ---
# O CORS (Cross-Origin Resource Sharing) é um mecanismo de segurança do navegador
# que impede que uma página web (ex: seu frontend em React rodando em localhost:3000)
# faça requisições para uma API em uma origem diferente (ex: sua API em localhost:8000).
# Este middleware informa ao navegador que é seguro permitir requisições das origens listadas.
# ===================================================================
# Lista de origens (domínios) que têm permissão para acessar esta API.
origins = [
    "http://localhost",
    "http://localhost:3000",  # Comum para create-react-app
    "http://localhost:5173",  # Comum para Vite.js
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Permite as origens listadas.
    allow_credentials=True,  # Permite o envio de cookies.
    allow_methods=["*"],  # Permite todos os métodos HTTP (GET, POST, PUT, etc.).
    allow_headers=["*"],  # Permite todos os cabeçalhos HTTP.
)
# ===================================================================

# --- Inclusão das Rotas Modulares ---
# Em vez de definir todos os endpoints neste arquivo, nós os organizamos em
# "routers" separados por funcionalidade. Aqui, incluímos esses routers na
# aplicação principal. Isso torna o código mais limpo e organizado.
app.include_router(species.router)
app.include_router(characters.router)
app.include_router(clans.router)
app.include_router(world.router)
app.include_router(events.router)
app.include_router(relationships.router)
app.include_router(game_elements.router)
app.include_router(missions.router)


# --- Rota Raiz (Root Endpoint) ---
@app.get("/", tags=["Root"])
def read_root():
    """
    Endpoint simples para verificar se a API está funcionando.
    """
    return {"message": "Bem-vindo à API do mundo de Orbis!"}


# --- Endpoint WebSocket ---
@app.websocket("/ws/{world_id}")
async def websocket_endpoint(websocket: WebSocket, world_id: int):
    """
    Endpoint para a comunicação em tempo real via WebSocket.
    Clientes (como o frontend) podem se conectar a esta rota para receber
    atualizações do estado da simulação de um mundo específico.
    """
    # Usa o nosso gerenciador de conexões para registrar o novo cliente.
    await manager.connect(websocket, world_id)

    # O bloco try...except é o padrão para lidar com o ciclo de vida do WebSocket.
    try:
        # Mantém a conexão viva em um loop infinito.
        while True:
            # Espera por uma mensagem do cliente. Neste caso, o servidor não faz
            # nada com a mensagem recebida, mas esta linha é essencial para
            # manter a conexão aberta e detectar quando o cliente se desconecta.
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Se o cliente fechar a conexão, uma exceção WebSocketDisconnect é levantada.
        # Nós a capturamos para remover o cliente da nossa lista de conexões ativas.
        manager.disconnect(websocket, world_id)
