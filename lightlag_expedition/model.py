"""Published expedition constants and strict validation, without episode truth."""

from lightlag.model import decode_command as decode_rover_command


VERSION = "lightlag-expedition-v1"
HORIZON = 60
REGIONS = ("r1", "r2", "r3")
PRIORS = {"r1": 0.90, "r2": 0.35, "r3": 0.50}
QUALITY_MULTIPLIERS = {"poor": 0.2, "rich": 1.0}
INSPECTION_BUDGET = 2
INSPECTION_ENERGY = 2.0
INSPECTION_ACCURACY = 0.9
TARGET_REGIONS = {"t1": "r1", "t2": "r1", "t3": "r2", "t4": "r2",
                  "t5": "r3", "t6": "r3", "d1": "r2", "d2": "r3"}


def decode_command(command):
    if isinstance(command, dict) and command.get("action") == "inspect":
        if set(command) != {"action", "region"} or command["region"] not in REGIONS:
            raise ValueError("inspect requires exactly action and region (r1, r2 or r3)")
        return {"action": "inspect", "region": command["region"]}
    return decode_rover_command(command)


def validate_fixture(fixture, name):
    """Trusted local test fixtures must specify all regions; never a public tool input."""
    if fixture is None:
        return None
    if not isinstance(fixture, dict) or set(fixture) != set(REGIONS):
        raise ValueError(f"{name} must contain exactly r1, r2 and r3")
    if any(value not in ("poor", "rich") for value in fixture.values()):
        raise ValueError(f"{name} values must be poor or rich")
    return dict(fixture)
