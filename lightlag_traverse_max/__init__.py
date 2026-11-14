"""Lightlag Traverse with a normal map and a MAX map option (the max env's mechanics on the traverse).

    from lightlag_traverse_max.environment import make_env
    env = make_env(seed=7, option="max")

    python3 -m lightlag_traverse_max.play --seeds 1-24 --maps normal,max
    python3 -m lightlag_traverse_max.oneshot report     # the frozen model baseline (oneshot.py, sandbox.py)

Built on lightlag_traverse/ without changing it. See docs/lightlag-traverse-max.md.
"""
