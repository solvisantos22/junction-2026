import json, math, random, heapq, sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, PHYSICS, TERRAIN_CODES

# Reuse check_energy_paths logic quickly with better SA
from check_energy_paths import nodes, N, modes_dummy if False else compute_apsp, target_info, solar_gain
