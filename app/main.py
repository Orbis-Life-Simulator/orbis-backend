# app/main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .database.database import engine, Base
from .routes import (
	species, characters, clans, world, events,
	relationships, game_elements, missions            
)
from .simulation.connection_manager import manager

Base.metadata.create_all(bind=engine)

app = FastAPI(
	title="Orbis Life Simulator API",
	description="API para gerenciar a simulação de vida do projeto Orbis.",
	version="0.1.0"
)

# ===================================================================
# O MIDDLEWARE CORS DEVE VIR AQUI!
# ANTES de incluir qualquer rota.
# ===================================================================
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
# ===================================================================

# Agora, inclua as rotas
app.include_router(species.router)
app.include_router(characters.router)
app.include_router(clans.router)
app.include_router(world.router)
app.include_router(events.router)
app.include_router(relationships.router) 
app.include_router(game_elements.router) 
app.include_router(missions.router)      

@app.get("/", tags=["Root"])
def read_root():
	return {"message": "Bem-vindo à API do mundo de Orbis!"}

@app.websocket("/ws/{world_id}")
async def websocket_endpoint(websocket: WebSocket, world_id: int):
    await manager.connect(websocket, world_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, world_id)
