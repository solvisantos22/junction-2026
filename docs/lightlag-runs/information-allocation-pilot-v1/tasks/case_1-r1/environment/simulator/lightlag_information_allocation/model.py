"""Public parameters for allocating one inspection between two unknowns."""

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType

INITIAL_ENERGY = 10
HORIZON = 30
DELAY = 1
SIGNAL_ACCURACY = .9
PENALTY_PER_TICK = .25
NORMALIZATION = 10
MAX_BATCH_SIZE = 5
MAX_ADVANCE_TICKS = 5
UNCERTAIN_ROUTES = ("a", "b")


@dataclass(frozen=True)
class Context:
    id: str
    prior_a: float
    prior_b: float
    value_a: float
    value_b: float
    probe_energy: float = 1

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("context id must be a nonempty string")
        for name, maximum in (("prior_a", 1), ("prior_b", 1),
                              ("value_a", NORMALIZATION), ("value_b", NORMALIZATION),
                              ("probe_energy", INITIAL_ENERGY)):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not isfinite(value) or not 0 <= value <= maximum):
                raise ValueError(f"{name} must be finite and between 0 and {maximum}")


def route_specs(context):
    return {
        "a": {"target_value": context.value_a, "duration": 2,
              "energy": {"firm": 4, "soft": 12}},
        "b": {"target_value": context.value_b, "duration": 2,
              "energy": {"firm": 4, "soft": 12}},
        "detour": {"target_value": 6, "duration": 6,
                   "energy": {"firm": 8, "soft": 8}},
    }


# Fixed development contexts are supplied before any episode study/model call.
CONTEXTS = MappingProxyType({
    "case_1": Context("case_1", .5, .2, 10, 10),
    "case_2": Context("case_2", .2, .5, 10, 10),
    "case_3": Context("case_3", .65, .55, 10, 9),
    "case_4": Context("case_4", .55, .65, 9, 10),
    "case_5": Context("case_5", .95, .6, 10, 10),
    "case_6": Context("case_6", .6, .95, 10, 10),
})
