from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from ..database import models
from ..dependencies import get_db
from ..simulation.divine_decree import interpretar_decreto

router = APIRouter(
    prefix="/api/worlds/{world_id}/storyteller",
    tags=["Storyteller (IA)"],
)

from pydantic import BaseModel


class DivineDecreeRequest(BaseModel):
    decreto: str


@router.post("/decree", status_code=200)
def execute_divine_decree(
    world_id: int, request: DivineDecreeRequest, db: Session = Depends(get_db)
):
    world = db.query(models.World).filter(models.World.id == world_id).first()
    if not world:
        raise HTTPException(status_code=404, detail="Mundo não encontrado.")

    contexto_para_ia = f"Evento global atual: {world.global_event or 'Nenhum'}."
    print(f"Contexto enviado para a IA: {contexto_para_ia}")

    comando_ia = interpretar_decreto(request.decreto, contexto_para_ia)

    if not comando_ia:
        raise HTTPException(
            status_code=400,
            detail="A IA não conseguiu interpretar o seu decreto. Tente ser mais específico.",
        )

    nome_funcao = comando_ia["name"]
    argumentos = comando_ia["args"]

    if nome_funcao == "informar_usuario":
        return {"message": f"IA Informa: {argumentos.get('mensagem')}"}

    elif nome_funcao == "gerar_evento_global":
        nome_evento = argumentos.get("nome_evento")
        duracao = argumentos.get("duracao_ticks")
        world.global_event = nome_evento
        db.commit()
        return {
            "message": f"Decreto executado: Evento global '{nome_evento}' iniciado!"
        }

    elif nome_funcao == "declarar_guerra":
        cla_agressor = (
            db.query(models.Clan)
            .filter(
                models.Clan.name == argumentos["cla_agressor"],
                models.Clan.world_id == world_id,
            )
            .first()
        )
        cla_alvo = (
            db.query(models.Clan)
            .filter(
                models.Clan.name == argumentos["cla_alvo"],
                models.Clan.world_id == world_id,
            )
            .first()
        )

        if not cla_agressor or not cla_alvo:
            raise HTTPException(
                status_code=404,
                detail="Um ou ambos os clãs mencionados não foram encontrados neste mundo.",
            )

        nova_guerra = models.ClanRelationship(
            clan_a_id=cla_agressor.id,
            clan_b_id=cla_alvo.id,
            relationship_type=models.ClanRelationshipTypeEnum.WAR,
        )
        db.add(nova_guerra)
        db.commit()
        return {
            "message": f"Decreto executado: {cla_agressor.name} está agora em guerra com {cla_alvo.name}."
        }

    elif nome_funcao == "criar_missao_conquista":
        cla_executor = (
            db.query(models.Clan)
            .filter(
                models.Clan.name == argumentos["cla_executor"],
                models.Clan.world_id == world_id,
            )
            .first()
        )
        territorio = (
            db.query(models.Territory)
            .filter(
                models.Territory.name == argumentos["territorio_alvo"],
                models.Territory.world_id == world_id,
            )
            .first()
        )

        if not cla_executor or not territorio:
            raise HTTPException(
                status_code=404,
                detail="O clã ou território mencionado não foi encontrado.",
            )

        nova_missao = models.Mission(
            world_id=world_id,
            title=argumentos["titulo_missao"],
            assignee_clan_id=cla_executor.id,
            status="ATIVA",
        )
        db.add(nova_missao)
        db.flush()

        objetivo = models.MissionObjective(
            mission_id=nova_missao.id,
            objective_type=models.ObjectiveTypeEnum.CONQUER_TERRITORY,
            target_territory_id=territorio.id,
        )
        db.add(objetivo)
        db.commit()
        return {
            "message": f"Decreto executado: Missão '{nova_missao.title}' atribuída a {cla_executor.name}."
        }

    else:
        raise HTTPException(
            status_code=400,
            detail=f"A IA retornou uma função desconhecida: {nome_funcao}",
        )
