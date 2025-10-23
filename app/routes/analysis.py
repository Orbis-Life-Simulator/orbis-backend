from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from ..dependencies import get_db

router = APIRouter(prefix="/api/analysis", tags=["Analysis (Spark Reports)"])


@router.get("/kd-ratio", response_model=List[dict])
async def get_kd_ratio_report(db: AsyncIOMotorDatabase = Depends(get_db)):
    report_data = await db.species_kd_report.find({}, {"_id": 0}).to_list(length=None)
    return report_data
