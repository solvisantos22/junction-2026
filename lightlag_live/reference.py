"""Play a whole campaign with a controller written for one mission, through the public tools only.

Standard library only and no simulator import, so the Harbor task's solution can carry this
file as it is. `policy(tools)` is any single-mission controller, such as the team's
`lightlag_dynamic.controllers.POLICIES["kf_mpc"]`: it is started fresh at the beginning of
every mission and plays the mission in progress.
"""


def play_campaign(tools, policy, on_mission=None):
    """Run `policy` once per mission until the campaign is complete.

    `on_mission(number)` is called before each mission, for logging.
    """
    while True:
        campaign = tools.rules()["campaign"]
        if campaign["complete"]:
            return
        mission = campaign["mission"]
        if on_mission is not None:
            on_mission(mission)
        policy(tools)
        # A controller may return before its mission ends. The clock does not wait, so neither
        # do we: sit out the remaining ticks, then start again on the next map.
        while True:
            campaign = tools.rules()["campaign"]
            if campaign["complete"]:
                return
            if campaign["mission"] != mission:
                break
            if tools.advance(5)["campaign_complete"]:
                return
