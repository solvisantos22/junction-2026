"""Monitor one frozen campaign; --follow permits only its qualified continuations.

Default: one remote read-only poll. Downloads happen only after every function
call has returned, following the wrapper's final volume commit. No final check,
model tuning, new campaign, automatic retry, or checkpoint-buffer download.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import gzip
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import time

from . import decide as decision


STAGES = ("pilot", "expanded", "extended")
TARGETS = (2048, 8192, 32768)
SEEDS = {17, 29, 43}
ALLOWED = re.compile(r"(?:report\.json|policy-(?:00000|00512|02048|08192|32768)\.json|validation-(?:00000|00512|02048|08192|32768)\.json\.gz)\Z")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def load_launcher(root, freeze):
    root = Path(root).resolve()
    for name, expected in freeze["source_sha256"].items():
        path = root / name
        decision.require(path.resolve().is_relative_to(root) and not path.is_symlink()
                         and decision.digest(path) == expected, "frozen source changed")
    path = root / "tools/learning_campaign/modal_job.py"
    spec = importlib.util.spec_from_file_location("_frozen_learning_campaign_launcher", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    decision.require(module.source_manifest(root) == freeze["source_sha256"], "frozen source closure changed")
    decision.require(freeze["resources"] == module.RESOURCES and freeze["runtime"] == module.RUNTIME
                     and freeze["required_profile"] == module.PROFILE, "frozen launcher configuration changed")
    return module


class Supervisor:
    def __init__(self, freeze_path, pilot_receipt, output, source_root, *, launcher=None, sdk=None, clock=time.time):
        self.freeze_path, self.output = Path(freeze_path).resolve(), Path(output).resolve()
        self.source_root, self.clock = Path(source_root).resolve(), clock
        self.freeze = decision.read(self.freeze_path)
        self.launcher = launcher or load_launcher(self.source_root, self.freeze)
        self.sdk = sdk  # Authentication is deferred until an actual read-only poll.
        self.operation = "initialize"
        self.state_path = self.output / "state.json"
        identity = {"freeze_sha256": decision.digest(self.freeze_path),
                    "pilot_receipt_sha256": decision.digest(pilot_receipt), "source_root": str(self.source_root),
                    "manager_sha256": decision.digest(__file__), "decision_tool_sha256": decision.digest(decision.__file__)}
        campaign = self.freeze["campaign"]
        decision.require(self.freeze["schema"] == "learning-campaign-freeze-v1"
                         and campaign["deadline_unix"] <= self.launcher.ABSOLUTE_DEADLINE,
                         "campaign deadline or schema differs")
        decision.require([s["name"] for s in campaign["stages"]] == list(STAGES), "three frozen stages required")
        for stage, target in zip(campaign["stages"], TARGETS):
            identities = [(j["algorithm"], j["seed"]) for j in stage["jobs"]]
            decision.require(len(identities) == 6 and set(identities) == {(a, s) for a in ("ppo", "replay") for s in SEEDS}
                             and all(j["episodes"] == target for j in stage["jobs"]), "frozen stage matrix differs")
        if self.state_path.exists():
            self.state = decision.read(self.state_path)
            decision.require(self.state["identity"] == identity, "supervisor resume identity changed")
        else:
            decision.require(not any(p.name != ".lock" for p in self.output.iterdir()), "output is not a new supervisor directory")
            path = self.output / "pilot/receipt.json"
            atomic_json(path, decision.read(pilot_receipt))
            self.validate_receipt(path, "pilot", {"ppo", "replay"})
            self.state = {"schema": "learning-campaign-supervisor-v1", "identity": identity,
                          "campaign_id": campaign["campaign_id"], "stage": "pilot", "status": "monitoring",
                          "receipts": {"pilot": {"path": "pilot/receipt.json", "sha256": decision.digest(path)}},
                          "decisions": {}, "launch_intent": None}
            self.save()
            self.event("initialized")

    def save(self):
        self.state["updated_unix"] = self.clock()
        atomic_json(self.state_path, self.state)

    def event(self, event, **details):
        with (self.output / "events.jsonl").open("a") as stream:
            stream.write(json.dumps({"unix": self.clock(), "event": event, "stage": self.state["stage"], **details},
                                    sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def validate_receipt(self, path, stage_name, algorithms):
        receipt = decision.read(path)
        stage = next(s for s in self.freeze["campaign"]["stages"] if s["name"] == stage_name)
        expected = [j for j in stage["jobs"] if j["algorithm"] in algorithms]
        actual = [{k: j[k] for k in ("run_id", "algorithm", "seed", "episodes")} for j in receipt["jobs"]]
        decision.require(receipt["schema"] == "learning-campaign-receipt-v1" and receipt["status"] == "submitted"
                         and receipt["stage"] == stage_name and receipt["campaign_id"] == self.freeze["campaign"]["campaign_id"]
                         and receipt["freeze_sha256"] == decision.digest(self.freeze_path)
                         and actual == expected and all(isinstance(j["call_id"], str) and j["call_id"] for j in receipt["jobs"]),
                         "receipt is incomplete or differs from the frozen selected stage")
        decision.require(receipt["reservation"]["jobs"] == expected
                         and receipt["reservation"]["deadline_unix"] <= self.freeze["campaign"]["deadline_unix"],
                         "receipt reservation differs")
        return receipt

    def recover_intent(self):
        intent = self.state["launch_intent"]
        if intent is None:
            return
        path = self.output / intent["stage"] / "receipt.json"
        # An intent without a complete submitted receipt is ambiguous: never retry.
        decision.require(path.exists(), "interrupted launch has no receipt; manual reconciliation required")
        self.validate_receipt(path, intent["stage"], set(intent["algorithms"]))
        self.state["stage"] = intent["stage"]
        self.state["receipts"][intent["stage"]] = {"path": str(path.relative_to(self.output)), "sha256": decision.digest(path)}
        self.state["launch_intent"], self.state["status"] = None, "monitoring"
        self.save()
        self.event("recovered_submitted_receipt")

    def download(self, receipt):
        self.operation = "download_terminal_artifacts"
        stage_root = self.output / receipt["stage"]
        manifest_path = stage_root / "download-manifest.json"
        if manifest_path.exists():
            manifest = decision.read(manifest_path)
            decision.require(manifest["receipt_sha256"] == self.state["receipts"][receipt["stage"]]["sha256"], "download receipt changed")
            for name, expected in manifest["files"].items():
                path = (stage_root / name).resolve()
                decision.require(path.is_relative_to(stage_root) and decision.digest(path) == expected, "downloaded artifact changed")
            return [stage_root / "runs" / j["run_id"] for j in receipt["jobs"]]
        volume = self.sdk.Volume.from_name(self.launcher.VOLUME_NAME)
        files = []
        for job in receipt["jobs"]:
            run_id = job["run_id"]
            decision.require(re.fullmatch(r"(?:ppo|replay)-(?:17|29|43)", run_id) is not None, "unexpected run directory")
            seen = set()
            for entry in volume.iterdir(run_id, recursive=False):
                relative = PurePosixPath(entry.path.lstrip("/"))
                if len(relative.parts) != 2 or relative.parts[0] != run_id or not ALLOWED.fullmatch(relative.name):
                    continue
                decision.require(str(relative) not in seen, "duplicate volume artifact")
                seen.add(str(relative))
                files.append((str(relative), stage_root / "runs" / run_id / relative.name))
            decision.require(f"{run_id}/report.json" in seen, "terminal run has no retained report")

        def fetch(pair):
            remote, local = pair
            local.parent.mkdir(parents=True, exist_ok=True)
            if not local.exists():
                temporary = local.with_suffix(local.suffix + ".partial")
                with temporary.open("wb") as stream:
                    for chunk in volume.read_file(remote):
                        stream.write(chunk)
                # A bad terminal read remains .partial; do not retry or publish it.
                raw = temporary.read_bytes()
                json.loads(gzip.decompress(raw) if local.suffix == ".gz" else raw)
                temporary.replace(local)
            else:
                decision.read(local)
            return str(local.relative_to(stage_root)), decision.digest(local)

        with ThreadPoolExecutor(max_workers=4) as pool:
            hashes = dict(pool.map(fetch, files))
        for job in receipt["jobs"]:
            report = decision.read(stage_root / "runs" / job["run_id"] / "report.json")
            decision.require(report["algorithm"] == job["algorithm"] and report["seed"] == job["seed"]
                             and report["episodes_target"] == job["episodes"] and report["smoke"] is False,
                             "downloaded report does not belong to this stage")
            require_pins = {n: h for n, h in self.freeze["uploaded_sha256"].items()}
            decision.require(report["source_sha256"] == require_pins, "downloaded report source differs from frozen upload")
        atomic_json(manifest_path, {"receipt_sha256": self.state["receipts"][receipt["stage"]]["sha256"], "files": hashes})
        self.event("terminal_artifacts_downloaded", files=len(hashes))
        return [stage_root / "runs" / j["run_id"] for j in receipt["jobs"]]

    def tick(self, follow=False):
        if self.state["status"] in ("error", "ready_for_final_evaluation", "stopped_marker", "campaign_deadline"):
            return self.state
        decision.require(decision.digest(self.freeze_path) == self.state["identity"]["freeze_sha256"], "freeze changed")
        self.recover_intent()
        if self.sdk is None:
            self.sdk = self.launcher.modal_sdk()
        stage = self.state["stage"]
        info = self.state["receipts"][stage]
        receipt_path = self.output / info["path"]
        decision.require(decision.digest(receipt_path) == info["sha256"], "stage receipt changed")
        receipt = decision.read(receipt_path)
        self.operation = "poll"
        status = self.launcher.status(receipt_path, sdk=self.sdk)
        atomic_json(self.output / stage / "status.json", status)
        decision.require(status["campaign_id"] == self.state["campaign_id"] and status["stage"] == stage,
                         "remote status identity differs")
        decision.require(len(status["jobs"]) == len(receipt["jobs"])
                         and {j["run_id"] for j in status["jobs"]} == {j["run_id"] for j in receipt["jobs"]},
                         "remote status jobs differ")
        decision.require(not any("error_type" in job for job in status["jobs"]), "remote function returned an error")
        pending = sum(bool(job.get("pending")) for job in status["jobs"])
        self.event("poll", pending=pending)
        if status["stop_marker"]:
            self.state["status"] = "stopped_marker"
        elif pending:
            self.state["status"] = "campaign_deadline" if self.clock() >= self.freeze["campaign"]["deadline_unix"] else "monitoring"
        else:
            decision.require(all(job.get("result", {}).get("status") in self.launcher.TERMINAL for job in status["jobs"]),
                             "returned function lacks a terminal result")
            decision.require(not any(job["result"]["status"] in ("training_error", "wrapper_error", "launch_error", "cancelled")
                                     for job in status["jobs"]), "stage contains a failed function; automatic continuation stopped")
            directories = self.download(receipt)
            if stage == "extended":
                self.state["status"] = "ready_for_final_evaluation"
                self.state["reason"] = "extended_stage_finished"
            else:
                self.operation = "decide"
                path = self.output / stage / "decision.json"
                previous = self.output / "pilot/decision.json" if stage == "expanded" else None
                result = decision.decide(directories, stage, previous)
                if path.exists():
                    decision.require(decision.read(path) == result, "retained staging decision changed")
                else:
                    atomic_json(path, result)
                self.state["decisions"][stage] = {"path": str(path.relative_to(self.output)), "sha256": decision.digest(path)}
                eligible = result["eligible_algorithms"]
                if not eligible or self.clock() >= self.freeze["campaign"]["deadline_unix"]:
                    self.state["status"] = "ready_for_final_evaluation"
                    self.state["reason"] = "no_qualified_continuation" if not eligible else "campaign_deadline"
                elif not follow:
                    self.state["status"] = "ready_for_continuation"
                    self.state["eligible_algorithms"] = eligible
                else:
                    next_stage = STAGES[STAGES.index(stage) + 1]
                    self.operation = "prepare_continuation"
                    plan = self.launcher.prepare(self.freeze_path, next_stage, root=self.source_root,
                                                 algorithms=eligible, now=self.clock())
                    self.state["launch_intent"] = {"stage": next_stage, "algorithms": eligible, "created_unix": self.clock()}
                    self.save()
                    self.event("launch_intent", next_stage=next_stage, algorithms=eligible)
                    self.operation = "launch_continuation"
                    self.launcher.launch(plan, self.output / next_stage / "receipt.json", root=self.source_root,
                                         sdk=self.sdk, now=self.clock())
                    self.recover_intent()
        self.save()
        return self.state


def manage(freeze, pilot_receipt, output, source_root, follow=False, *, launcher=None, sdk=None,
           clock=time.time, sleeper=time.sleep):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        supervisor = Supervisor(freeze, pilot_receipt, output, source_root, launcher=launcher, sdk=sdk, clock=clock)
        try:
            while True:
                result = supervisor.tick(follow=follow)
                if not follow or result["status"] != "monitoring":
                    return result
                sleeper(30)
        except KeyboardInterrupt:
            supervisor.event("interrupted", operation=supervisor.operation)
            raise
        except Exception as error:
            supervisor.state["status"] = "error"
            supervisor.state["error"] = {"type": type(error).__name__, "operation": supervisor.operation}
            supervisor.save()
            supervisor.event("error", **supervisor.state["error"])
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--pilot-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--follow", action="store_true")
    args = parser.parse_args()
    result = manage(**vars(args))
    print(json.dumps({key: result[key] for key in ("campaign_id", "stage", "status")}, indent=2))


if __name__ == "__main__":
    main()
