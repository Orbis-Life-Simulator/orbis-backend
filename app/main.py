from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from . import models
from .database import engine, SessionLocal

# Criar as tabelas no banco
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Orbis API")

# Dependência para usar o banco em rotas
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Orbis API rodando 🚀"}
