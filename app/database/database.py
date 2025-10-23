import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("A variável de ambiente MONGO_URI não foi configurada.")

client = AsyncIOMotorClient(MONGO_URI)
db = client.orbis_database

print("Conexão ASSÍNCRONA com o MongoDB estabelecida.")

worlds_collection = db.worlds
species_collection = db.species
clans_collection = db.clans
characters_collection = db.characters
events_collection = db.events
resources_collection = db.resources
territories_collection = db.territories
missions_collection = db.missions
relationships_collection = db.relationships

world_analytics_collection = db.world_analytics
