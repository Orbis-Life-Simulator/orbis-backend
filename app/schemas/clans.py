from pydantic import BaseModel

class ClanBase(BaseModel):
    name: str
    species_id: int

class ClanCreate(ClanBase):
    pass

class Clan(ClanBase):
    id: int

    class Config:
        from_attributes = True
