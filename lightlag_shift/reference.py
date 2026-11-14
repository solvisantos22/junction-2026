"""A reference for the rule-change mission: prepare for the worst entry on the published menu.

It does not work out which change happened. It reads the menu in `rules()["rule_change"]`
and plans from the first tick as if the costliest published turning rule were already in
force, on top of Manh's controller 36 (unchanged), which already measures slip, bridges gaps
in telemetry and keeps an energy reserve. Only public information is used: the five tools and
the published menu.

Needs numpy, like every controller in `lightlag_dynamic.manh_controllers`.

    from lightlag_shift.reference import play
    play(tools)          # tools: anything with rules/map/telemetry_log/uplink/advance
"""

BASE_CONTROLLER = 36


class Prepared:
    """The five tools, with rules() saying what the worst case on the menu would say."""

    def __init__(self, tools):
        self._tools = tools

    def rules(self):
        rules = dict(self._tools.rules())
        menu = (rules.get("rule_change") or {}).get("one_of") or {}
        if "turning" in menu:
            rules["turn_cost_per_degree"] = menu["turning"]["energy_per_degree"][1]
        return rules

    def __getattr__(self, name):
        return getattr(self._tools, name)


def play(tools, env=None):
    """Play one mission. `env` is only passed through to the base controller's logger hook."""
    from lightlag_dynamic.manh_controllers import controllers as zoo

    name = next(n for n in zoo.REGISTRY if zoo.number(n) == BASE_CONTROLLER)
    zoo.Current.logger = None
    zoo.REGISTRY[name]["play"](Prepared(tools), env)
