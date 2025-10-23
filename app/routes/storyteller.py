from fastapi import APIRouter, Depends, HTTPException, Body, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from datetime import datetime, timezone

from ..dependencies import get_db
from ..simulation.divine_decree import interpretar_decreto

router = APIRouter(
    prefix="/api/worlds/{world_id}/storyteller",
    tags=["Storyteller (IA, MongoDB)"],
)


class DivineDecreeRequest(BaseModel):
    decreto: str


@router.post("/decree", status_code=status.HTTP_200_OK)
async def execute_divine_decree(
    world_id: int,
    request: DivineDecreeRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Recebe um comando em linguagem natural, coleta contexto do mundo,
    interpreta com a IA (Gemini) e executa a ação correspondente no MongoDB.
    """
    world_doc = await db.worlds.find_one({"_id": world_id})
    if not world_doc:
        raise HTTPException(status_code=404, detail="Mundo não encontrado.")

    contexto_para_ia = (
        f"Evento global atual: {world_doc.get('global_event', 'Nenhum')}."
    )
    print(f"Contexto enviado para a IA: {contexto_para_ia}")

    comando_ia = interpretar_decreto(request.decreto, contexto_para_ia)

    if not comando_ia:
        raise HTTPException(
            status_code=400,
            detail="A IA não conseguiu interpretar o seu decreto. Tente ser mais específico.",
        )

    nome_funcao = comando_ia.get("name")
    argumentos = comando_ia.get("args", {})

    if nome_funcao == "informar_usuario":
        return {"message": f"IA Informa: {argumentos.get('mensagem')}"}

    elif nome_funcao == "gerar_evento_global":
        nome_evento = argumentos.get("nome_evento")
        await db.worlds.update_one(
            {"_id": world_id}, {"$set": {"global_event": nome_evento}}
        )
        return {
            "message": f"Decreto executado: Evento global '{nome_evento}' iniciado!"
        }

    elif nome_funcao == "declarar_guerra":
        cla_agressor = await db.clans.find_one(
            {"name": argumentos["cla_agressor"], "world_id": world_id}
        )
        cla_alvo = await db.clans.find_one(
            {"name": argumentos["cla_alvo"], "world_id": world_id}
        )

        if not cla_agressor or not cla_alvo:
            raise HTTPException(
                status_code=404,
                detail="Um ou ambos os clãs mencionados não foram encontrados.",
            )

        nova_guerra_doc = {
            "clan_a_id": cla_agressor["_id"],
            "clan_b_id": cla_alvo["_id"],
            "relationship_type": "WAR",
        }
        await db.clan_relationships.insert_one(nova_guerra_doc)
        return {
            "message": f"Decreto executado: {cla_agressor['name']} está agora em guerra com {cla_alvo['name']}."
        }

    elif nome_funcao == "criar_missao_conquista":
        cla_executor = await db.clans.find_one(
            {"name": argumentos["cla_executor"], "world_id": world_id}
        )
        territorio = await db.territories.find_one(
            {"name": argumentos["territorio_alvo"], "world_id": world_id}
        )

        if not cla_executor or not territorio:
            raise HTTPException(
                status_code=404,
                detail="O clã ou território mencionado não foi encontrado.",
            )

        last_mission = await db.missions.find_one(sort=[("_id", -1)])
        new_id = (last_mission["_id"] + 1) if last_mission else 1

        nova_missao_doc = {
            "_id": new_id,
            "world_id": world_id,
            "title": argumentos["titulo_missao"],
            "assignee_clan_id": cla_executor["_id"],
            "status": "ATIVA",
            "created_at": datetime.now(timezone.utc),
            "objectives": [
                {
                    "objective_type": "CONQUER_TERRitory",
                    "target_territory_id": territorio["_id"],
                    "is_complete": False,
                }
            ],
        }
        await db.missions.insert_one(nova_missao_doc)
        return {
            "message": f"Decreto executado: Missão '{nova_missao_doc['title']}' atribuída a {cla_executor['name']}."
        }

    else:
        raise HTTPException(
            status_code=400,
            detail=f"A IA retornou uma função desconhecida: {nome_funcao}",
        )
