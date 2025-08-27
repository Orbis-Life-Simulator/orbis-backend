from sqlalchemy import Column, Integer, String
from .database import Base

class Species(Base):
    __tablename__ = "species"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    base_health = Column(Integer, default=100)
    base_strength = Column(Integer, default=10)
