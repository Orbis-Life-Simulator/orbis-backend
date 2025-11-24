from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId

from app.dependencies import get_db
from .worlds import get_current_user


# Importa as novas funções que criamos
from app.storyteller.gemini_interpreter import interpretar_decreto
from app.storyteller.storyteller_utils import gerar_contexto_mundo, executar_comando

router = APIRouter(
    prefix="/api/storyteller",
    tags=["Storyteller (Gemini)"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(get_current_user)],
)


class DecretoRequest(BaseModel):
    decreto: str


@router.post("/{world_id}/decreto", status_code=status.HTTP_200_OK)
async def processar_decreto_storyteller(
    world_id: str,
    request: DecretoRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Recebe um comando em linguagem natural, interpreta-o com a IA do Gemini
    e executa a ação correspondente na simulação.
    """
    # 1. Valida o ID do mundo e a propriedade
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

    # 2. Gera o contexto atual do mundo para a IA
    contexto = await gerar_contexto_mundo(world_obj_id, db)

    # 3. Envia o decreto do usuário e o contexto para o Gemini interpretar
    comando_json = interpretar_decreto(request.decreto, contexto)

    if not comando_json:
        raise HTTPException(
            status_code=500,
            detail="A IA não conseguiu interpretar o comando. Verifique os logs do servidor.",
        )

    # 4. Executa o comando retornado pelo Gemini
    resultado = await executar_comando(comando_json, world_obj_id, db)

    if not resultado.get("success"):
        raise HTTPException(
            status_code=422,
            detail=resultado.get("message", "Falha ao executar o comando."),
        )

    return {
        "message": "Decreto executado com sucesso!",
        "details": resultado.get("message"),
    }
