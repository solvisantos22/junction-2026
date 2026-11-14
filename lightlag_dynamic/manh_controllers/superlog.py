"""Super logger: where a controller fails and where it prevails (needs numpy).

Per decision (Manh controllers): the predicted state at the slot the command will execute,
its covariance, the plan, what was sent, and the chance of being inside the radius when a
sample was sent. After the episode it is compared with the truth at that tick.

Per packet (Manh controllers): estimate vs truth: position error, NEES, heading bias error,
slip errors, filter spread.

Per episode (every controller, from the evaluator's replay): score, home, death, every
sample attempt, deadlines, discoveries, safety stops, and failure labels:

  DEAD               battery ran out
  NOT_HOME           alive, outside the base radius at the horizon
  CRASH              the controller raised (e.g. an uplink the rules reject)
  MISS_CONFIDENT     a sample failed although the controller was >= 90% sure
  MISS_TRY           a sample failed that was sent below 90% (a deliberate try)
  MISS_UNLOGGED      a sample failed (controller without logging)
  RETRIED_OK         a missed target was sampled later
  SAFETY_STOP        hit a hazard or the map edge
  LATE_SAMPLE        sampled after its deadline (late fraction only)
  DISCOVERY_MISSED   a discovered target was never sampled
  SKIPPED_WITH_ENERGY  targets left unsampled while >= 15 energy remained (too cautious?)
  ENERGY_LIMITED     targets left unsampled and < 15 energy remained
  FILTER_OVERCONFIDENT  mean NEES > 4 (2 is consistent)
  BIAS_LOST          final heading-bias error > 3 degrees
  PERFECT            every target, home
"""

import math

import numpy as np


def _wrap_deg(a):
    return (a + 180.0) % 360.0 - 180.0


class SuperLogger:
    def __init__(self, env, keep_decisions=True):
        self.env = env
        self.keep = keep_decisions
        self.estimates = []
        self.decisions = []
        self.by_execute = {}

    # ---- hooks ------------------------------------------------------------------------------
    def estimate(self, ctrl, packet):
        f = ctrl.filter
        t = packet["tick"]
        truth = self.env._truth[t]
        tx, ty = truth["position"]
        m, P = f.mean, f.cov
        ex, ey = tx - m[0], ty - m[1]
        a, b, c = P[0][0], P[0][1], P[1][1]
        det = a * c - b * b
        nees = (ex * ex * c - 2 * ex * ey * b + ey * ey * a) / det if det > 1e-14 else float("nan")
        bias_true = self._bias_at(t)
        row = {"tick": t, "err": math.hypot(ex, ey), "nees": nees,
               "sd": math.sqrt(max(a + c, 0.0) / 2),
               "bias_err_deg": abs(_wrap_deg(math.degrees(m[2]) - bias_true)) if bias_true is not None else None,
               "slip_err": {tr: abs(f.slip(tr) - self.env._slip[tr]) for tr in f.terrains},
               "slip_sd": {tr: f.slip_sigma(tr) for tr in f.terrains}}
        self.estimates.append(row)

    def _bias_at(self, tick):
        if not self.env._sensing:
            return None
        bias = self.env._initial_heading_bias
        for e in self.env._heading_errors:
            if e["tick"] <= tick:
                bias = e["bias_deg"]
        return bias

    def pre_decide(self, ctrl):
        slot = ctrl.next_slot()
        if slot > ctrl.horizon:
            return None
        st = ctrl.predict(slot)
        return {"now": ctrl.tick, "slot": slot, "x": st["x"], "y": st["y"],
                "sd": math.sqrt(max(st["cov"][0][0] + st["cov"][1][1], 0) / 2) if "cov" in st else None,
                "battery": st["battery"], "sampled": sorted(st["sampled"]), "state": st}

    def post_decide(self, ctrl, pre, sent):
        if pre is None or not sent:
            return
        from lightlag_dynamic.kf_mpc import inside_probability
        st = pre.pop("state")
        plan = [t["id"] for t in (getattr(ctrl, "plan", None) or [])]
        actions = [a["command"]["action"] for a in sent]
        row = dict(pre, plan=plan, actions=actions,
                   execute=[a["execute_tick"] for a in sent],
                   confirm=getattr(ctrl, "confirm_tick", None))
        if "sample" in actions and plan:
            t = ctrl.targets.get(plan[0])
            if t is not None:
                point = (t["x"], t["y"])
                if actions == ["sample"] and "cov" in st:
                    row["chance"] = inside_probability((st["x"], st["y"]), st["cov"], point, ctrl.radius)
                else:
                    hop = ctrl.leg((st["x"], st["y"]), point)
                    if hop is not None and hasattr(ctrl, "_end_inside"):
                        row["chance"] = ctrl._end_inside(hop, ctrl.radius)
                row["target"] = plan[0]
        for a in sent:
            if a["command"]["action"] == "sample":
                self.by_execute[a["execute_tick"]] = row
        if self.keep:
            self.decisions.append(row)

    # ---- episode summary ----------------------------------------------------------------------
    def summary(self, replay, crash=None):
        return summarize(replay, self, crash)


def summarize(replay, log=None, crash=None):
    r = replay["result"]
    states = replay["states"]
    final = states[-1]
    base = replay["world"]["base"]
    share = r["raw_score"] / r["max_available_value"] if r["max_available_value"] else 0.0
    labels = []
    out = {"score": r["raw_score"], "max": r["max_available_value"], "share": share,
           "alive": r["alive"], "at_base": r["at_base"],
           "home_dist": math.hypot(final["position"][0] - base[0], final["position"][1] - base[1]),
           "battery_end": final["battery"], "crash": crash}
    if not r["alive"]:
        labels.append("DEAD")
    elif not r["at_base"]:
        labels.append("NOT_HOME")
    if crash:
        labels.append("CRASH")
    taken, failed, stops, discovered, late = [], [], 0, [], 0
    for s in states:
        for e in s.get("events", []):
            if e["type"] == "sample_taken":
                taken.append((s["tick"], e.get("target_id")))
                if e.get("on_time") is False:
                    late += 1
            elif e["type"] == "sample_failed":
                failed.append((s["tick"], e.get("reason")))
            elif e["type"] == "safety_stop":
                stops += 1
            elif e["type"] == "target_discovered":
                discovered.append(e.get("target", {}).get("id") or e.get("target_id"))
    out.update(samples_taken=len(taken), samples_failed=len(failed), safety_stops=stops, late=late)
    conf = tries = 0
    for tick, reason in failed:
        if reason != "no_unsampled_target_in_range":
            continue
        row = log.by_execute.get(tick) if log is not None else None
        if row is None or row.get("chance") is None:
            labels.append("MISS_UNLOGGED") if "MISS_UNLOGGED" not in labels else None
        elif row["chance"] >= 0.9:
            conf += 1
        else:
            tries += 1
    out.update(miss_confident=conf, miss_try=tries)
    if conf:
        labels.append("MISS_CONFIDENT")
    if tries:
        labels.append("MISS_TRY")
    if failed and taken and any(ft < tt for ft, _ in failed for tt, _ in taken):
        labels.append("RETRIED_OK")
    if stops:
        labels.append("SAFETY_STOP")
    if late:
        labels.append("LATE_SAMPLE")
    sampled = set(r["sampled_targets"])
    if any(d and d not in sampled for d in discovered):
        labels.append("DISCOVERY_MISSED")
    unsampled = [t for t in replay["world"]["targets"] if t["id"] not in sampled]
    if unsampled and r["alive"]:
        labels.append("SKIPPED_WITH_ENERGY" if final["battery"] >= 15 else "ENERGY_LIMITED")
    if share >= 0.999 and r["at_base"] and r["alive"]:
        labels.append("PERFECT")
    if log is not None and log.estimates:
        est = log.estimates
        errs = [e["err"] for e in est]
        nees = [e["nees"] for e in est if e["nees"] == e["nees"]]
        out["pos_rmse"] = float(np.sqrt(np.mean(np.square(errs))))
        out["pos_err_max"] = max(errs)
        out["nees_mean"] = float(np.mean(nees)) if nees else None
        last = est[-1]
        out["bias_err_final"] = last["bias_err_deg"]
        out["slip_err_final"] = last["slip_err"]
        early = est[: max(1, len(est) // 3)]
        out["slip_err_early"] = {k: float(np.mean([e["slip_err"][k] for e in early])) for k in last["slip_err"]}
        if out["nees_mean"] is not None and out["nees_mean"] > 4:
            labels.append("FILTER_OVERCONFIDENT")
        if last["bias_err_deg"] is not None and last["bias_err_deg"] > 3:
            labels.append("BIAS_LOST")
        # prediction under delay: predicted state for the execution slot vs the truth there
        perr = []
        for d in log.decisions:
            t = d["slot"] - 1
            if 0 <= t < len(states):
                tx, ty = states[t]["position"]
                perr.append(math.hypot(tx - d["x"], ty - d["y"]))
        out["pred_err_mean"] = float(np.mean(perr)) if perr else None
        out["decisions"] = len(log.decisions)
    out["labels"] = labels
    return out
