from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId


async def gerar_contexto_mundo(world_id: ObjectId, db: AsyncIOMotorDatabase) -> str:
    """
    Coleta informações cruciais do mundo para fornecer contexto à IA.
    """
    clans_cursor = db.clans.find({"world_id": world_id}, {"name": 1})
    territories_cursor = db.territories.find({"world_id": world_id}, {"name": 1})

    clans = await clans_cursor.to_list(length=None)
    territories = await territories_cursor.to_list(length=None)

    clan_names = [c.get("name") for c in clans if c.get("name")]
    territory_names = [t.get("name") for t in territories if t.get("name")]

    contexto = (
        f"Clãs existentes: {', '.join(clan_names) if clan_names else 'Nenhum'}. "
        f"Territórios existentes: {', '.join(territory_names) if territory_names else 'Nenhum'}."
    )
    return contexto


async def executar_comando(
    comando: dict, world_id: ObjectId, db: AsyncIOMotorDatabase
) -> dict:
    """
    Recebe o JSON do Gemini e executa a ação correspondente no banco de dados.
    """
    nome_comando = comando.get("name")
    args = comando.get("args", {})

    print(f"Executando comando '{nome_comando}' com argumentos: {args}")

    if nome_comando == "declarar_guerra":
        cla_agressor_nome = args.get("cla_agressor")
        cla_alvo_nome = args.get("cla_alvo")

        cla_a = await db.clans.find_one(
            {"world_id": world_id, "name": cla_agressor_nome}
        )
        cla_b = await db.clans.find_one({"world_id": world_id, "name": cla_alvo_nome})

        if not cla_a or not cla_b:
            return {
                "success": False,
                "message": "Um ou ambos os clãs não foram encontrados.",
            }

        # Usa upsert para criar ou atualizar a relação
        await db.clan_relationships.update_one(
            {"clan_a_id": cla_a["_id"], "clan_b_id": cla_b["_id"]},
            {"$set": {"relationship_type": "WAR", "world_id": world_id}},
            upsert=True,
        )
        return {
            "success": True,
            "message": f"Guerra declarada entre {cla_agressor_nome} e {cla_alvo_nome}.",
        }

    elif nome_comando == "formar_alianca":
        cla_A_nome = args.get("cla_A")
        cla_B_nome = args.get("cla_B")

        cla_a = await db.clans.find_one({"world_id": world_id, "name": cla_A_nome})
        cla_b = await db.clans.find_one({"world_id": world_id, "name": cla_B_nome})

        if not cla_a or not cla_b:
            return {
                "success": False,
                "message": "Um ou ambos os clãs não foram encontrados.",
            }

        await db.clan_relationships.update_one(
            {"clan_a_id": cla_a["_id"], "clan_b_id": cla_b["_id"]},
            {"$set": {"relationship_type": "ALLIANCE", "world_id": world_id}},
            upsert=True,
        )
        return {
            "success": True,
            "message": f"Aliança formada entre {cla_A_nome} e {cla_B_nome}.",
        }

    elif nome_comando == "informar_usuario":
        return {
            "success": False,
            "message": args.get("mensagem", "A IA não pôde processar o pedido."),
        }

    # Adicione a lógica para outros comandos (criar_missao, etc.) aqui...

    else:
        return {"success": False, "message": f"Comando desconhecido: '{nome_comando}'."}
