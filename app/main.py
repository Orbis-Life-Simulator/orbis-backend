from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt

from app.auth import ALGORITHM, SECRET_KEY
from app.dependencies import get_db
from app.schemas.types import PyObjectId

from .routes import (
    characters,
    clan_relationships,
    clans,
    events,
    missions,
    resource_types,
    species_relationships,
    species,
    storyteller,
    users,
    worlds,
    analysis,
)

from .simulation.connection_manager import manager

app = FastAPI(
    title="Orbis Life Simulator API (MongoDB Edition)",
    description="API para gerenciar a simulação de vida do projeto Orbis com arquitetura de Big Data.",
    version="0.2.0",
)

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Incluindo roteadores da API...")
app.include_router(worlds.router)
app.include_router(species.router)
app.include_router(clans.router)
app.include_router(characters.router)
app.include_router(events.router)
app.include_router(missions.router)
app.include_router(storyteller.router)
app.include_router(species_relationships.router)
app.include_router(clan_relationships.router)
app.include_router(resource_types.router)
app.include_router(users.router)
app.include_router(analysis.router)


print("Roteadores incluídos com sucesso.")


@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Bem-vindo à API do mundo de Orbis (MongoDB Edition)!"}


@app.websocket("/ws/{world_id}")
async def websocket_endpoint(websocket: WebSocket, world_id: str):

    token = websocket.query_params.get("token")
    await websocket.accept()

    if token is None:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Token não fornecido."
        )
        return

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido."
            )
            return
    except JWTError:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido ou expirado."
        )
        return

    db = get_db()

    user = db.users.find_one({"email": email})

    if user is None:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Usuário não encontrado."
        )
        return

    try:
        world_obj_id = PyObjectId(world_id)
        world = db.worlds.find_one({"_id": world_obj_id, "user_id": user["_id"]})
        if not world:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Acesso ao mundo não autorizado.",
            )
            return
    except Exception:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="ID do mundo inválido."
        )
        return

    await manager.connect(websocket, world_id)
    print(f"Cliente autenticado ({user['email']}) conectado ao mundo {world_id}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, world_id)
        print(f"Cliente ({user['email']}) desconectado do mundo {world_id}")
