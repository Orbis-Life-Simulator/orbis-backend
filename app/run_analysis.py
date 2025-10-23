import os
from dotenv import load_dotenv
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, count, when, avg, lit


def setup_spark_session() -> SparkSession:
    """Configura e retorna uma sessão do Spark com o conector MongoDB."""
    load_dotenv()
    MONGO_URI = os.getenv("MONGO_URI")
    if not MONGO_URI:
        raise ValueError("MONGO_URI não encontrada no arquivo .env")

    print("Configurando a sessão do Spark com o conector MongoDB...")
    spark = (
        SparkSession.builder.appName("OrbisAnalysis")
        .config("spark.mongodb.input.uri", MONGO_URI)
        .config("spark.mongodb.output.uri", MONGO_URI)
        .config(
            "spark.jars.packages", "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1"
        )
        .getOrCreate()
    )
    return spark


def load_data(spark: SparkSession, collection_name: str) -> DataFrame | None:
    """Carrega uma coleção do MongoDB para um DataFrame do Spark."""
    print(f"Lendo a coleção '{collection_name}' do MongoDB...")
    try:
        df = spark.read.format("mongo").option("collection", collection_name).load()
        df.cache()
        print(f"Total de {df.count()} documentos lidos de '{collection_name}'.")
        if df.count() == 0:
            print(f"Aviso: Coleção '{collection_name}' está vazia.")
            return None
        return df
    except Exception as e:
        print(f"Erro ao ler a coleção '{collection_name}'. Erro: {e}")
        return None


def write_report(df: DataFrame, collection_name: str):
    """Salva um DataFrame de relatório no MongoDB, sobrescrevendo a coleção."""
    if df:
        print(f"Salvando relatório na coleção '{collection_name}'...")
        df.write.format("mongo").option("collection", collection_name).mode(
            "overwrite"
        ).save()
        print("Relatório salvo com sucesso.")


def analyze_population(events_df: DataFrame):
    """Gera o relatório de Demografia e População."""
    if not events_df:
        return None

    print("\n--- Gerando Relatório: Demografia e População ---")

    births = (
        events_df.filter(col("eventType") == "CHARACTER_BIRTH")
        .groupBy("payload.child.species")
        .agg(count("*").alias("total_births"))
    )

    deaths = (
        events_df.filter(col("eventType") == "CHARACTER_DEATH")
        .groupBy("payload.character.species")
        .agg(count("*").alias("total_deaths"))
    )

    report_df = (
        births.join(deaths, births["species"] == deaths["species"], "full_outer")
        .select(
            when(births["species"].isNotNull(), births["species"])
            .otherwise(deaths["species"])
            .alias("species"),
            col("total_births"),
            col("total_deaths"),
        )
        .fillna(0)
    )

    print("Resultado - Crescimento Populacional por Espécie:")
    report_df.show()
    return report_df


def analyze_combat(events_df: DataFrame):
    """Gera o relatório de Combate e Sobrevivência (K/D Ratio)."""
    if not events_df:
        return None

    print("\n--- Gerando Relatório: Combate e Sobrevivência ---")

    deaths_df = events_df.filter(
        (col("eventType") == "CHARACTER_DEATH")
        & (col("payload.reason") == "Morto em combate")
    )

    if deaths_df.count() == 0:
        print("Nenhum evento de morte em combate encontrado.")
        return None

    deaths_by_species = deaths_df.groupBy("payload.character.species").agg(
        count("*").alias("deaths")
    )
    kills_by_species = deaths_df.groupBy("payload.killed_by.species").agg(
        count("*").alias("kills")
    )

    report_df = (
        kills_by_species.join(
            deaths_by_species,
            kills_by_species["species"] == deaths_by_species["species"],
            "full_outer",
        )
        .select(
            when(kills_by_species["species"].isNotNull(), kills_by_species["species"])
            .otherwise(deaths_by_species["species"])
            .alias("species"),
            col("kills"),
            col("deaths"),
        )
        .fillna(0)
        .withColumn(
            "kd_ratio",
            when(col("deaths") > 0, col("kills") / col("deaths")).otherwise(
                col("kills")
            ),
        )
    )

    print("Resultado - K/D Ratio por Espécie:")
    report_df.show()
    return report_df


def analyze_socio_politics(events_df: DataFrame):
    """Gera o relatório Sócio-Político."""
    if not events_df:
        return None

    print("\n--- Gerando Relatório: Sócio-Política ---")

    alliances = (
        events_df.filter(col("eventType") == "ALLIANCE_FORMED")
        .select(col("payload.clanA.name").alias("clan_name"))
        .union(
            events_df.filter(col("eventType") == "ALLIANCE_FORMED").select(
                col("payload.clanB.name").alias("clan_name")
            )
        )
        .groupBy("clan_name")
        .agg(count("*").alias("alliances_formed"))
    )

    deaths = (
        events_df.filter(
            (col("eventType") == "CHARACTER_DEATH")
            & (col("payload.reason") == "Morto em combate")
        )
        .select("payload.character.clan.name", "payload.killed_by.clan.name")
        .withColumnRenamed("name", "victim_clan")
        .withColumnRenamed("name", "killer_clan")
    )

    war_casualties = deaths.groupBy("victim_clan", "killer_clan").agg(
        count("*").alias("total_casualties")
    )

    print("Resultado - Alianças Formadas por Clã:")
    alliances.show()
    print("Resultado - Baixas Totais entre Clãs:")
    war_casualties.show()
    return alliances


def analyze_geospatial(events_df: DataFrame):
    """Gera o relatório Geoespacial (Heatmap de Conflitos)."""
    if not events_df:
        return None

    print("\n--- Gerando Relatório: Geoespacial ---")

    combat_locations = events_df.filter(col("eventType") == "COMBAT_ACTION").select(
        "payload.location.x", "payload.location.y"
    )

    heatmap_df = (
        combat_locations.withColumn("grid_x", (col("x") / 50).cast("integer") * 50)
        .withColumn("grid_y", (col("y") / 50).cast("integer") * 50)
        .groupBy("grid_x", "grid_y")
        .agg(count("*").alias("conflict_intensity"))
    )

    print("Resultado - Heatmap de Zonas de Conflito:")
    heatmap_df.sort(col("conflict_intensity").desc()).show()
    return heatmap_df


def main():
    """Job principal de análise de dados do Orbis."""
    spark = setup_spark_session()

    events_df = load_data(spark, "events")

    population_report = analyze_population(events_df)
    write_report(population_report, "report_population_growth")

    combat_report = analyze_combat(events_df)
    write_report(combat_report, "report_combat_kd_ratio")

    socio_politics_report = analyze_socio_politics(events_df)
    write_report(socio_politics_report, "report_alliances_formed")

    geospatial_report = analyze_geospatial(events_df)
    write_report(geospatial_report, "report_conflict_heatmap")

    print("\nJob de Análise do Orbis concluído.")
    spark.stop()


if __name__ == "__main__":
    main()
