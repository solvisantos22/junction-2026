"""The dependency boundary shared by trusted controller implementations."""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class PublicTools:
    """Five public callbacks, with no evaluator or simulator state members.

    This is an auditable interface for trusted code, not a security sandbox
    against Python introspection. A policy receives an instance of this class
    rather than an Environment or evaluator-owned episode inputs.
    """

    __slots__ = ("rules", "map", "telemetry_log", "uplink", "advance")

    rules: Callable[[], dict]
    map: Callable[[], dict]
    telemetry_log: Callable[[], list]
    uplink: Callable[[list], list]
    advance: Callable[..., dict]
