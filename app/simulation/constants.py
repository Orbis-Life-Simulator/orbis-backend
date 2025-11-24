"""
Este arquivo armazena todas as constantes de balanceamento e física da simulação.
Ele existe para quebrar a dependência circular entre engine.py e behavior_tree.py.
"""

# Aumentamos a visão (era 100). Agora eles veem o mapa quase todo.
VISION_RANGE: float = 150.0

# Aumentamos a velocidade (era 5.0). Eles correm para a briga.
MOVE_SPEED: float = 15.0

# Facilitamos o alcance do ataque
ATTACK_RANGE: float = 25.0
GATHER_RANGE: float = 15.0
GROUPING_DISTANCE: float = 50.0

# Reduzimos a fome para que eles não percam tempo comendo
HUNGER_INCREASE_RATE: float = 0.1
STARVATION_DAMAGE: int = 1

# Regeneração alta para que aguentem chegar na batalha
ENERGY_REGEN_RATE: int = 5
REST_ENERGY_REGEN_RATE: int = 10
WANDER_ENERGY_COST: float = 0.0  # Vagar não cansa
MOVE_ENERGY_COST: float = 0.5

# Custos de construção
HOUSE_WOOD_COST: int = 10
HOUSE_STONE_COST: int = 5

# Balanceamento de Vida (Ticks por ano)
# 10 ticks = 1 ano.
TICKS_PER_YEAR: int = 13

GATHER_AMOUNT: int = 6

REPRODUCTION_COOLDOWN_TICKS = 300
REPRODUCTION_HUNGER_COST = 50
REPRODUCTION_ENERGY_COST = 40

# Expectativa de vida (em anos)
SPECIES_LIFESPAN_YEARS: dict = {
    "humano": 90,
    "humans": 90,
    "elfo": 150,
    "elf": 150,
    "orc": 75,
    "orcs": 75,
    "fada": 140,
    "fadas": 140,
    "goblin": 60,
    "goblins": 60,
    "anao": 135,
    "anão": 135,
    "anaoes": 135,
    "troll": 95,
    "trolls": 95,
    "zumbi": None,
    "zombies": None,
    "zombie": None,
}
