import errno, json, os, socket
from pathlib import Path
def play(tools):
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    denied = {}
    for name in ("/forbidden-write", "/app/policy.py", "/app/worker.py"):
        try:
            with open(name, "ab") as stream: stream.write(b"x")
            denied[name] = False
        except OSError: denied[name] = True
    with open("/tmp/probe", "w") as stream: stream.write("temporary")
    sock = socket.socket()
    sock.settimeout(1)
    unreachable = sock.connect_ex(("192.0.2.1", 9)) in (errno.ENETUNREACH, errno.EHOSTUNREACH)
    sock.close()
    checks = {"nonroot": os.getuid() == 65534 and os.getgid() == 65534,
      "no_capabilities": int(status["CapEff"].strip(), 16) == 0,
      "no_new_privileges": status["NoNewPrivs"].strip() == "1",
      "network_unreachable": unreachable,
      "no_up_external_interfaces": all(name == "lo" or not int(Path("/sys/class/net", name, "flags").read_text(), 16) & 1 for _, name in socket.if_nameindex()),
      "read_only_files": all(denied.values()), "temporary_write": Path("/tmp/probe").read_text() == "temporary",
      "only_two_app_files": sorted(os.listdir("/app")) == ["policy.py", "worker.py"],
      "no_project_packages": not any(Path(p).exists() for p in ("/repo", "/workspace", "/evaluator", "/var/run/docker.sock")),
      "memory_limit": Path("/sys/fs/cgroup/memory.max").read_text().strip() == "268435456",
      "pids_limit": Path("/sys/fs/cgroup/pids.max").read_text().strip() == "64",
      "cpu_limit": Path("/sys/fs/cgroup/cpu.max").read_text().strip() == "100000 100000",
      "clean_environment": set(os.environ) <= {"PATH","HOSTNAME","LANG","GPG_KEY","PYTHON_VERSION","PYTHON_SHA256","PYTHONHASHSEED","PYTHONDONTWRITEBYTECODE","HOME"}}
    print("ISOLATION:" + json.dumps(checks, sort_keys=True))
