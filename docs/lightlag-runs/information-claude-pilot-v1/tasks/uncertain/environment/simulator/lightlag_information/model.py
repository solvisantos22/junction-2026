"""Frozen public parameters for the small route-choice experiment."""

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

ROUTES = {
    "shortcut": {"target_value": 10, "duration": 2,
                 "energy": {"firm": 4, "soft": 12}},
    "detour": {"target_value": 6, "duration": 6,
               "energy": {"firm": 8, "soft": 8}},
}


@dataclass(frozen=True)
class Context:
    id: str
    prior_firm: float
    probe_energy: float

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("context id must be a nonempty string")
        for name, maximum in (("prior_firm", 1), ("probe_energy", INITIAL_ENERGY)):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not isfinite(value) or not 0 <= value <= maximum):
                raise ValueError(f"{name} must be finite and between 0 and {maximum}")


CONTEXTS = MappingProxyType({
    "uncertain": Context("uncertain", .5, 1),
    "likely_firm": Context("likely_firm", .95, 1),
    "likely_soft": Context("likely_soft", .05, 1),
    "costly_probe": Context("costly_probe", .5, 3),
})
