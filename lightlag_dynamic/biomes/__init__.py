"""Selectable Mars biomes for the Lightlag dynamic environment.

    python3 -m lightlag_dynamic.biomes --list
    python3 -m lightlag_dynamic.biomes --biome troy_crust --profile rush_noisy --seed 7 --delay 3 < script.jsonl
    python3 -m lightlag_dynamic.biomes.serve --biome relay_pass --profile rush --seed 7 --delay 3
    python3 -m lightlag_dynamic.biomes.trial --seeds 2000-2039        # which controller does best where

"main_mars" is today's environment, unchanged, and the default. The other biomes are named after
real rover events; each publishes its rule in rules() and its areas in map(). A sandbox option,
not a rules decision: see docs/lightlag-biomes.md. The environment is standard library only;
the trial needs numpy, like the Manh controllers it plays.
"""

from .catalog import BIOME_IDS, CATALOG, MAIN, parse_biome
from .environment import BiomeEnvironment, make_biome_env

__all__ = ["BIOME_IDS", "CATALOG", "MAIN", "BiomeEnvironment", "make_biome_env", "parse_biome"]
