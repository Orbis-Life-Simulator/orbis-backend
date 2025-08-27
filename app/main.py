from fastapi import FastAPI
from . import models, database
from .routers import species

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Orbis Backend API")

app.include_router(species.router)

@app.get("/")
def root():
    return {"message": "Bem-vindo ao Orbis!"}
