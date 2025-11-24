import subprocess
import sys
import os
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId

from app.dependencies import get_db
from app.routes.worlds import get_current_user

router = APIRouter(
    prefix="/api/analysis",
    tags=["Analysis"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(get_current_user)],
)


@router.post("/{world_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_analysis_job(
    world_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Dispara a execução do script de análise (versão Pandas) em um processo separado.
    """
    try:
        world_obj_id = ObjectId(world_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Formato do ID do mundo inválido.")

    world_doc = await db.worlds.find_one(
        {"_id": world_obj_id, "user_id": current_user["_id"]}
    )
    if not world_doc:
        raise HTTPException(
            status_code=404, detail="Mundo não encontrado ou acesso não autorizado."
        )

    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))

        app_dir = os.path.abspath(os.path.join(current_dir, ".."))

        script_path = os.path.join(app_dir, "run_analysis.py")

        print(f"Caminho absoluto construído para o script: {script_path}")

        if not os.path.exists(script_path):
            error_msg = f"Arquivo do job de análise não encontrado no servidor. Caminho verificado: {script_path}"
            print(f"!!! ERRO CRÍTICO: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

        print(f"Disparando o job de análise (Pandas) para o mundo {world_id}...")
        subprocess.Popen([sys.executable, script_path, world_id])

    except Exception as e:
        print(f"Erro ao tentar iniciar o processo de análise: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao iniciar o job de análise: {e}",
        )

    return {
        "message": "O processo de análise foi iniciado. Os resultados podem levar alguns segundos para aparecer."
    }
