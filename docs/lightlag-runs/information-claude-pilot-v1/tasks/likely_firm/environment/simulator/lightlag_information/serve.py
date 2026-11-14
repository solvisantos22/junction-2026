"""Serve one information-choice episode via stdio or HTTP MCP."""

import argparse
import os
from pathlib import Path
import secrets
import signal
import sys

from .model import CONTEXTS
from .service import InformationService


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--context", choices=tuple(CONTEXTS), default=os.environ.get("INFORMATION_CONTEXT", "uncertain"))
    parser.add_argument("--seed", type=int, default=os.environ.get("INFORMATION_SEED"))
    parser.add_argument("--artifact-dir", default=os.environ.get("INFORMATION_ARTIFACT_DIR"))
    parser.add_argument("--token-file", default=os.environ.get("INFORMATION_TOKEN_FILE"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.seed is None:
        parser.error("a seed is required (--seed or INFORMATION_SEED)")
    token = None
    if args.transport == "http" and args.token_file:
        path = Path(args.token_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(32)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(token)
    from .server import build_server
    service = InformationService(seed=args.seed, context=args.context, artifact_dir=args.artifact_dir)
    server = build_server(service, token)

    def stop(signum, frame):
        service.finish()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        if args.transport == "stdio":
            server.run("stdio")
        else:
            server.run("streamable-http", host=args.host, port=args.port)
    finally:
        service.finish()
    return 0


if __name__ == "__main__":
    sys.exit(main())
