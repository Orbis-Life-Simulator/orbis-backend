from fastapi import FastAPI
from .database.database import engine, Base

from .routes import (
	species, 
	characters, 
	clans, 
	world, 
	events,
	relationships,      
	game_elements,     
	missions            
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
	title="Orbis Life Simulator API",
	description="API para gerenciar a simulação de vida do projeto Orbis.",
	version="0.1.0"
)

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
	"""
	Endpoint raiz para verificar se a API está funcionando.
	"""
	return {"message": "Bem-vindo à API do mundo de Orbis!"}
