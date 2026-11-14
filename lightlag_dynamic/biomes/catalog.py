"""The biome catalog: what each biome is, the real rover event behind it, and its published settings.

A biome is a named setting of the dynamic environment. "Main Mars" is the environment as it is
today. Every other biome changes published parameters only: it never adds a new physical system,
and the delay, battery, slip and safety-stop rules stay the team's. Each one is modelled on a
place or a routine where a real Mars rover got stuck, damaged or slowed.

Kinds:
  "main"       today's environment, unchanged
  "terrain"    a terrain unit: ground that behaves differently inside a published area
  "situation"  an operating condition that holds everywhere (the sky, or onboard fault protection)

Settings are the published defaults. They were chosen on development seeds 0-19 by a keep rule
written down before the sweep, and are a sandbox proposal, not a rules decision
(docs/lightlag-biomes.md, "How the settings were chosen").
"""

MAIN = "main_mars"

CATALOG = {
    "main_mars": {
        "name": "Main Mars",
        "kind": "main",
        "modelled_on": "the team's current Lightlag environment",
        "rule": "the dynamic environment as published: nothing is added or changed",
        "decision": "the mission itself: which targets, in what order, and when to turn for home",
        "settings": {},
    },
    "relay_pass": {
        "name": "Relay Pass Schedule",
        "kind": "situation",
        "modelled_on": ("Mars orbiter relay passes: rovers send and receive most data through orbiters "
                        "(Mars Reconnaissance Orbiter, Mars Odyssey, MAVEN, Trace Gas Orbiter) a few "
                        "times per sol, not continuously"),
        "rule": ("the link is open only during relay passes: open_ticks ticks at the start of every "
                 "period_ticks ticks. An uplink sent between passes is stored and transmitted when the "
                 "next pass opens; a telemetry packet that would arrive between passes arrives when the "
                 "next pass opens; map() lists a discovered target from the tick its packet arrives"),
        "decision": "what to queue before the pass closes",
        "settings": {"period_ticks": 8, "open_ticks": 4},
    },
    "hidden_valley": {
        "name": "Hidden Valley",
        "kind": "situation",
        "modelled_on": ("Curiosity backing out of the sand of Hidden Valley, Gale crater (2014), after "
                        "its drives slipped more than planned: the rovers measure slip on board and "
                        "stop a drive when it is too high"),
        "rule": ("onboard fault protection: if a drive step slips more than the limit, the rover stops "
                 "that drive and discards every queued command; telemetry reports safety_stop with "
                 "reason slip_limit"),
        "decision": "cross the sand and risk a stop that empties the queue, or go around",
        # The lab kept 0.40-0.42 on the 50-tick rush profiles only, and 0.45 everywhere.
        "settings": {"limit": 0.40, "limit_long_missions": 0.45, "long_mission_ticks": 60},
    },
    "bagnold_dunes": {
        "name": "Bagnold Dunes",
        "kind": "terrain",
        "modelled_on": ("Curiosity's crossing and study of the active Bagnold Dunes, Gale crater "
                        "(2015-16), and Opportunity stuck for about five weeks in Purgatory Dune, "
                        "Meridiani Planum (2005)"),
        "rule": ("every sand patch on the map is a dune field, cut into dune faces, each with a slope "
                 "listed in map(); extra dune fields, if the settings ask for any, are listed in map() "
                 "and are also in its sand list. On a "
                 "dune face slip = sand coefficient + slip_per_degree * slope_deg (plus the usual "
                 "per-drive noise, clipped as usual). The sand coefficient is the hidden per-seed value "
                 "in slip_ranges; slip_per_degree is a second hidden per-seed value inside its "
                 "published range. Where faces overlap, the steeper one applies"),
        "decision": "measure slip at two slopes before trusting a steep face, or go around the dunes",
        # fields 0: the dunes are the sand already on the map. A dune field across a route
        # (fields 1, field_size_m [3, 5]) is available but did not pass the keep rule.
        "settings": {"fields": 0, "field_size_m": [3.0, 5.0], "face_width_m": 2.0,
                     "slope_deg": [0.0, 20.0], "slip_per_degree": [0.01, 0.03], "base_clearance_m": 1.5},
    },
    "troy_crust": {
        "name": "Troy Crust",
        "kind": "terrain",
        "modelled_on": ("Spirit breaking through a crust into soft sand at Troy, Gusev crater (2009), "
                        "where its mission ended"),
        "rule": ("map() lists crust regions. Inside one, the ground is mapped as bedrock, but each "
                 "cell_m square is soft sand underneath with probability soft_rate, fixed by the seed "
                 "and not listed. A soft cell behaves exactly like sand (slip and energy), and the "
                 "telemetry terrain field reports sand while the rover stands on one"),
        "decision": "probe the edge of a crust region, or route around it",
        "settings": {"regions": 2, "region_size_m": [5.0, 8.0], "soft_rate": 0.10, "cell_m": 1.0,
                     "base_clearance_m": 1.5},
    },
    "gale_rock_field": {
        "name": "Gale Rock Field",
        "kind": "terrain",
        "modelled_on": ("the punctures sharp rocks tore in Curiosity's wheels in Gale crater (2013), "
                        "after which its routes were replanned over softer ground"),
        "rule": ("map() lists rock fields and the rough cells inside them. Entering a rough cell jolts "
                 "the rover and can spin its wheels (see terrain_roughness) and adds one to wheel_wear, "
                 "which every telemetry packet reports. Once wheel_wear exceeds budget_cells, a drive "
                 "covers at most worn_max_metres: a longer command is cut to that length and telemetry "
                 "reports drive_limited"),
        "decision": "straight across the rocks, or a longer smooth route",
        "settings": {"fields": 2, "field_size_m": [5.0, 8.0], "rough_share": 0.3, "budget_cells": 4,
                     "worn_max_metres": 2.5, "base_clearance_m": 1.5},
    },
    "meridiani_ripples": {
        "name": "Meridiani Ripple Plains",
        "kind": "terrain",
        "modelled_on": "Opportunity's long drives across the sand ripples of Meridiani Planum",
        "rule": ("visual odometry is less reliable on uniform sand: its relative noise is published "
                 "per terrain in sensing.visual_odometry_noise_by_terrain, and a drive that starts and "
                 "ends on different terrains gets the average. The sensing model of the noisy profiles "
                 "is on in this biome, also on a profile that is otherwise noiseless"),
        "decision": "take extra measurements where the sensor is weak",
        "settings": {"visual_odometry_noise_by_terrain": {"bedrock": 0.03, "sand": 0.2}},
    },
}

BIOME_IDS = tuple(CATALOG)

# Pairs that cannot be mixed: the rough-ground drive loop does not run the onboard slip check.
INCOMPATIBLE = (frozenset({"gale_rock_field", "hidden_valley"}),)


def parse_biome(biome):
    """'troy_crust' or 'troy_crust+relay_pass' -> a tuple of ids, checked."""
    if isinstance(biome, str):
        ids = tuple(part.strip() for part in biome.split("+") if part.strip())
    else:
        ids = tuple(biome)
    if not ids:
        raise ValueError("no biome given; use one of " + ", ".join(BIOME_IDS))
    for name in ids:
        if name not in CATALOG:
            raise ValueError(f"unknown biome {name!r}; use one of {', '.join(BIOME_IDS)}")
    if len(set(ids)) != len(ids):
        raise ValueError("a biome can be chosen only once")
    if MAIN in ids and len(ids) > 1:
        raise ValueError("main_mars is the unchanged environment and cannot be mixed with another biome")
    for pair in INCOMPATIBLE:
        if pair <= set(ids):
            raise ValueError("these biomes cannot be mixed: " + " + ".join(sorted(pair)))
    return ids


def biome_settings(ids, overrides=None):
    """Published settings per chosen biome, with optional overrides {biome_id: {name: value}}."""
    overrides = dict(overrides or {})
    unknown = set(overrides) - set(ids)
    if unknown:
        raise ValueError(f"settings given for biomes that are not chosen: {sorted(unknown)}")
    out = {}
    for name in ids:
        merged = dict(CATALOG[name]["settings"])
        extra = dict(overrides.get(name) or {})
        bad = set(extra) - set(merged)
        if bad:
            raise ValueError(f"unknown {name} settings: {sorted(bad)}")
        merged.update(extra)
        out[name] = merged
    return out


def describe(ids):
    """The public description of the chosen biome(s), as it appears in rules()['biome']."""
    return [{"id": name, "name": CATALOG[name]["name"], "kind": CATALOG[name]["kind"],
             "modelled_on": CATALOG[name]["modelled_on"], "rule": CATALOG[name]["rule"]} for name in ids]
