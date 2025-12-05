import os
import sys
from dotenv import load_dotenv
import pandas as pd
import pymongo
from bson import ObjectId
from datetime import datetime, timezone


def get_db_connection():
    """Conecta ao MongoDB e retorna o objeto do banco de dados."""
    load_dotenv()
    MONGO_URI = os.getenv("MONGO_URI")
    if not MONGO_URI:
        raise ValueError("MONGO_URI não encontrada no arquivo .env")

    client = pymongo.MongoClient(MONGO_URI)

    try:
        return client.get_default_database()
    except Exception:
        print("Aviso: Nome do banco não encontrado na URI. Usando 'orbis' como padrão.")
        return client["orbis"]


def main():
    if len(sys.argv) < 2:
        print("Erro: ID do mundo não fornecido.")
        return

    target_world_id_str = sys.argv[1]

    try:
        db = get_db_connection()
        try:
            world_obj_id = ObjectId(target_world_id_str)
        except Exception:
            print(f"Erro: ID do mundo inválido: {target_world_id_str}")
            return

        print(f"Iniciando análise para o mundo: {world_obj_id}")

        # Busca eventos de morte e aliança
        cursor = db.events.find(
            {
                "worldId": world_obj_id,
                "eventType": {"$in": ["CHARACTER_DEATH", "ALLIANCE_FORMED"]},
            }
        )
        events = list(cursor)

        if not events:
            print("Nenhum evento relevante encontrado.")
            empty_payload = {
                "report_total_deaths": [],
                "report_combat_kd_ratio": [],
                "report_alliances_formed": [],
                "report_conflict_heatmap": [],
                "last_analysis_at": datetime.now(timezone.utc).isoformat(),
            }
            db.world_analytics.update_one(
                {"_id": world_obj_id},
                {"$set": {"spark_reports": empty_payload}},
                upsert=True,
            )
            return

        death_records = []
        alliance_records = []

        print(f"Processando {len(events)} eventos...")

        for evt in events:
            payload = evt.get("payload", {})

            if evt["eventType"] == "CHARACTER_DEATH":
                # --- EXTRAÇÃO DA VÍTIMA ---
                char = payload.get("character", {})
                victim_species = "Desconhecido"
                if isinstance(char.get("species"), dict):
                    victim_species = char["species"].get("name") or "Desconhecido"
                elif isinstance(char.get("species"), str):
                    victim_species = char["species"]

                victim_id = str(char.get("id") or "unknown")
                reason = payload.get("reason", "Desconhecido")

                # --- EXTRAÇÃO DO ASSASSINO (CORREÇÃO) ---
                # Definimos um padrão "N/A" para não quebrar o gráfico se falhar
                killer_species = "N/A"
                killer_id = "N/A"

                killed_by = payload.get("killed_by")

                # Só tentamos extrair se killed_by existir e não for vazio
                if killed_by and isinstance(killed_by, dict) and killed_by.get("id"):
                    k_spec = killed_by.get("species")
                    if isinstance(k_spec, dict):
                        killer_species = k_spec.get("name") or "Desconhecido"
                    elif isinstance(k_spec, str):
                        killer_species = k_spec

                    killer_id = str(killed_by.get("id"))

                # --- LOCALIZAÇÃO ---
                loc = payload.get("location") or evt.get("location")
                loc_x = loc.get("x") if isinstance(loc, dict) else None
                loc_y = loc.get("y") if isinstance(loc, dict) else None

                death_records.append(
                    {
                        "victim_id": victim_id,
                        "victim_species": victim_species,
                        "reason": reason,
                        "killer_species": killer_species,
                        "killer_id": killer_id,
                        "x": loc_x,
                        "y": loc_y,
                    }
                )

            elif evt["eventType"] == "ALLIANCE_FORMED":
                clanA = payload.get("clanA", {}).get("name")
                clanB = payload.get("clanB", {}).get("name")
                if clanA and clanB:
                    alliance_records.append({"clan": clanA})
                    alliance_records.append({"clan": clanB})

        df_deaths = pd.DataFrame(death_records)

        # --- 1. Total de Mortes ---
        total_deaths_report = []
        if not df_deaths.empty:
            grouped = (
                df_deaths.groupby("victim_species")["victim_id"].nunique().reset_index()
            )
            grouped.columns = ["species", "total_deaths"]
            grouped = grouped.sort_values("total_deaths", ascending=False)
            total_deaths_report = grouped.to_dict(orient="records")

        # --- 2. K/D Ratio (CORRIGIDO PARA SER PERMISSIVO) ---
        kd_report_list = []
        if not df_deaths.empty:
            # Filtra apenas onde a razão é EXATAMENTE "Morto em combate"
            # Removemos o filtro de killer_species.notna() que estava limpando tudo
            combat_df = df_deaths[df_deaths["reason"] == "Morto em combate"].copy()

            # Debug print para ver se encontrou algo
            print(f"Mortes em combate encontradas: {len(combat_df)}")

            if not combat_df.empty:
                # Kills: Agrupa por quem matou (mesmo que seja "N/A")
                kills = (
                    combat_df.groupby("killer_species")["killer_id"]
                    .nunique()
                    .reset_index()
                )
                kills.columns = ["species", "kills"]

                # Deaths: Agrupa por quem morreu
                deaths = (
                    combat_df.groupby("victim_species")["victim_id"]
                    .nunique()
                    .reset_index()
                )
                deaths.columns = ["species", "deaths"]

                # Junta tudo. Se tiver "N/A", ele vai aparecer no gráfico, mostrando que há dados mas sem espécie.
                merged = pd.merge(kills, deaths, on="species", how="outer").fillna(0)

                # Remove a linha "N/A" se ela existir e não tiver kills reais, ou mantém para debug
                merged = merged[merged["species"] != "N/A"]

                # Calcula Ratio
                merged["kd_ratio"] = merged.apply(
                    lambda row: (
                        row["kills"] / row["deaths"]
                        if row["deaths"] > 0
                        else row["kills"]
                    ),
                    axis=1,
                )

                kd_report_list = merged.to_dict(orient="records")

        # --- 3. Heatmap ---
        heatmap_list = []
        if not df_deaths.empty:
            loc_df = df_deaths.dropna(subset=["x", "y"]).copy()
            if not loc_df.empty:
                loc_df["grid_x"] = (loc_df["x"] // 50).astype(int) * 50
                loc_df["grid_y"] = (loc_df["y"] // 50).astype(int) * 50
                heatmap_data = (
                    loc_df.groupby(["grid_x", "grid_y"])
                    .size()
                    .reset_index(name="conflict_intensity")
                )
                heatmap_list = heatmap_data.to_dict(orient="records")

        # --- 4. Alianças ---
        alliances_list = []
        if alliance_records:
            df_alliances = pd.DataFrame(alliance_records)
            grouped = (
                df_alliances.groupby("clan").size().reset_index(name="alliances_formed")
            )
            grouped = grouped.rename(columns={"clan": "clan_name"})
            alliances_list = grouped.to_dict(orient="records")

        analytics_payload = {
            "report_total_deaths": total_deaths_report,
            "report_combat_kd_ratio": kd_report_list,
            "report_alliances_formed": alliances_list,
            "report_conflict_heatmap": heatmap_list,
            "report_zombie_impact": [],
            "report_predator_prey": [],
            "report_war_casualties": [],
            "last_analysis_at": datetime.now(timezone.utc).isoformat(),
        }

        print(
            f"Resultados Finais: {len(total_deaths_report)} linhas de mortes totais, {len(kd_report_list)} linhas de K/D."
        )

        db.world_analytics.update_one(
            {"_id": world_obj_id},
            {"$set": {"spark_reports": analytics_payload}},
            upsert=True,
        )
        print("Analytics salvos com sucesso.")

    except Exception as e:
        print(f"\n--- ERRO CRÍTICO ---")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
