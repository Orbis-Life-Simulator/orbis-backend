"""
Este arquivo armazena todas as constantes de balanceamento e física da simulação.
Ele existe para quebrar a dependência circular entre engine.py e behavior_tree.py.
"""

VISION_RANGE: float = 100.0
MOVE_SPEED: float = 5.0
ATTACK_RANGE: float = 10.0
GATHER_RANGE: float = 15.0
GROUPING_DISTANCE: float = 50.0
HUNGER_INCREASE_RATE: float = 0.5
STARVATION_DAMAGE: int = 2
ENERGY_REGEN_RATE: int = 1
REPRODUCTION_FOOD_COST: int = 100
