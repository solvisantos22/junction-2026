"""What an agent is told about an episode in a biome or without a trustworthy position fix.

lightlag_mcp's tool descriptions are everything an agent is told about how to act, and they
describe today's telemetry: a position in every packet. That is untrue without a fix and
misleading with a very noisy one, and they say nothing of a biome's extra map layers. This
module holds the sentences that make them true again, built from the episode's own rules():

    tool_wording(rules)     {constant of lightlag_mcp.server: (text to find, text to put)}
    patched(server, rules)  context manager: the constants patched while a server is built
    brief(rules)            the same facts as Markdown, for a task's instruction.md

Every sentence states what telemetry reports, never what to do with it. Nothing here edits a
file of lightlag_mcp: the constants are swapped in the serving process only, as
lightlag_dynamic.realtime does for its clock, and the swap fails loudly if that wording
changes. Standard library only.
"""

import contextlib

HEADING_ERROR = ("The rover does not drive exactly the commanded heading: `rules` describes the hidden heading "
                 "error, and its `navigation` section gives the noise of every reading.")
BEACON = "the distance to a radio beacon at the base (beacon_range_m)"
BEACONS = ("the distance to each radio beacon listed in `map` (beacon_ranges_m, in the order of `map`'s beacons, "
           "the base first)")
UNHEARD = "an entry is null when that beacon was not heard"
COMPASS = "the heading actually driven, measured by a sun compass (sun_heading_deg)"
GYRO = ("how far that heading turned since the previous executed drive, measured by a gyroscope (gyro_turn_deg)")
WHEELS = ("The wheels are a hidden few percent bigger or smaller than nominal (`rules`, navigation.wheel_scale): a "
          "drive of M commanded metres covers M x wheel_scale x (1 - slip) of ground, so a drive can also overshoot. "
          "wheel_odometry reports the commanded wheel metres, visual_odometry the ground covered.")


def _navigation(rules):
    nav = rules.get("navigation")
    if not nav:
        return None
    noise = nav.get("position_noise_m")
    if noise is None:
        position = "After the launch briefing, telemetry does not say where the rover is: position is null."
        field = "position (null after the tick-0 briefing: there is no position fix)"
    else:
        position = ("Telemetry reports a position, but only coarsely: each fix is the true position plus noise of "
                    "{:g} m per axis (`rules`, navigation.position_noise_m).".format(noise))
        field = "position [x, y] (a noisy fix, see `rules`)"
    several, gyro, wheels = nav.get("beacons", 1) > 1, nav.get("gyro_noise_deg") is not None, "wheel_scale" in nav
    unheard = nav.get("beacon_hear_chance", 1.0) < 1
    beacon = (BEACONS + ("; " + UNHEARD if unheard else "")) if several else BEACON
    driven = COMPASS + (", and " + GYRO if gyro else "")
    fields = field + ", beacon_range_m (measured distance to the base{})".format(", or null when not heard" if unheard else "")
    if several:
        fields += ", beacon_ranges_m (measured distance to each beacon of `map`{})".format(
            ", null when not heard" if unheard else "")
    fields += ", sun_heading_deg (measured heading of the drive executed in that tick, or null)"
    if gyro:
        fields += ", gyro_turn_deg (measured turn of that heading since the previous executed drive, or null)"
    return {
        "paragraph": "Position: {} Every packet reports {}; the packet of an executed drive also reports {}. {}{}"
                     .format(position, beacon, driven, HEADING_ERROR, " " + WHEELS if wheels else ""),
        "fields": fields + ", heading_deg (commanded heading)",
        "map": " `beacons` lists the radio beacons whose ranges telemetry reports." if several else "",
        "bullets": [position,
                    "Every packet reports {}.".format(beacon),
                    "The packet of an executed drive also reports {}.".format(driven),
                    HEADING_ERROR] + ([WHEELS] if wheels else []),
    }


def _biome(rules):
    biomes = rules.get("biome")
    if not biomes:
        return None
    names = " + ".join(entry["name"] for entry in biomes)
    return {
        "paragraph": "Biome: this episode is set in {}. `rules` states under `biome` what is different there, "
                     "and `map` lists the areas it adds.".format(names),
        "map": " A biome can add layers to this map (crust_regions, rock_fields with rough_cells, dune_faces); "
               "`rules` explains each under `biome`.",
        "bullets": ["This episode is set in {}. `rules()[\"biome\"]` states what is different there, and "
                    "`map()` lists the areas it adds.".format(names)]
                   + ["{}: {}.".format(entry["name"], entry["rule"]) for entry in biomes],
    }


def tool_wording(rules):
    """{constant name in lightlag_mcp.server: [(old, new), ...]} for this episode; {} when nothing differs."""
    navigation, biome = _navigation(rules), _biome(rules)
    changes = {}
    paragraphs = [part["paragraph"] for part in (biome, navigation) if part]
    if paragraphs:
        start = "Start with `rules` and `map`."
        changes["INSTRUCTIONS"] = [(start, "\n\n".join(paragraphs) + "\n\n" + start)]
    if navigation:
        changes["TELEMETRY_DESCRIPTION"] = [("position [x, y], heading_deg (commanded heading)", navigation["fields"])]
        changes["RULES_DESCRIPTION"] = [("and command limits.",
                                         "command limits, and under `navigation` what telemetry reports about the "
                                         "rover's position and how noisy each reading is.")]
    layers = (biome["map"] if biome else "") + (navigation["map"] if navigation else "")
    if layers:
        old = "Everything not sand is bedrock."
        changes["MAP_DESCRIPTION"] = [(old, old + layers)]
    if biome:
        rule = ("and command limits.", "command limits, and under `biome` the rules of the biome this episode is set in.")
        if navigation:
            old, new = changes["RULES_DESCRIPTION"][0]
            changes["RULES_DESCRIPTION"] = [(old, new[:-1] + ", and under `biome` the rules of the biome this "
                                                             "episode is set in.")]
        else:
            changes["RULES_DESCRIPTION"] = [rule]
    return changes


def reworded(server_module, rules):
    """The patched texts, {constant: text}, without touching `server_module`. Fails if the wording moved."""
    out = {}
    for name, pairs in tool_wording(rules).items():
        text = getattr(server_module, name)
        for old, new in pairs:
            if text.count(old) != 1:
                raise RuntimeError("lightlag_mcp's tool wording changed; update lightlag_dynamic.biomes.wording: "
                                   + repr(old))
            text = text.replace(old, new)
        out[name] = text
    return out


@contextlib.contextmanager
def patched(server_module, rules):
    """Swap the tool texts of `server_module` for this episode's while a server is being built."""
    new = reworded(server_module, rules)
    saved = {name: getattr(server_module, name) for name in new}
    try:
        for name, text in new.items():
            setattr(server_module, name, text)
        yield new
    finally:
        for name, text in saved.items():
            setattr(server_module, name, text)


def brief(rules):
    """Markdown for a task's instruction.md: the same facts the tool texts state, as bullets. '' if none."""
    sections = []
    biome, navigation = _biome(rules), _navigation(rules)
    if biome:
        sections.append("## Where this mission is set\n\n" + "\n".join("- " + line for line in biome["bullets"]))
    if navigation:
        sections.append("## Where the rover is\n\n" + "\n".join("- " + line for line in navigation["bullets"]))
    return "\n\n".join(sections)
