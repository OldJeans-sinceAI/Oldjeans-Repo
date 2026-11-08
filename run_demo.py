#!/usr/bin/env python3
"""Start the reference site and its own isolated local Yext mock."""

import argparse
import fcntl
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


def port_free(port):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def main():
    load_dotenv(ROOT / ".env", override=False)
    gemini_env = os.getenv("GEMINI_ENV_FILE")
    if gemini_env:
        load_dotenv((ROOT / gemini_env).resolve(), override=False)
    p = argparse.ArgumentParser()
    p.add_argument(
        "--mode", choices=["mock", "sandbox"], default=os.getenv("APP_MODE", "mock")
    )
    p.add_argument("--host", default=os.getenv("APP_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "8000")))
    p.add_argument("--mock-port", type=int, default=int(os.getenv("MOCK_PORT", "8787")))
    p.add_argument("--now", default=os.getenv("APP_NOW", "2026-11-06T10:00:00+02:00"))
    p.add_argument("--real-clock", action="store_true")
    p.add_argument(
        "--presentation", action="store_true",
        help="Fixed Next-button rehearsal using its own mock state; manual sandbox stays separate.",
    )
    p.add_argument(
        "--with-sandbox",
        action="store_true",
        help="Enable the team's real Yext workspace at /sandbox; owner approval is still required.",
    )
    p.add_argument("--state-dir", default=os.getenv("STATE_DIR", str(ROOT / "runtime")))
    a = p.parse_args()
    if a.presentation and (a.mode != "mock" or a.real_clock):
        p.error("--presentation requires mock mode and the frozen demo clock.")
    if a.presentation:
        a.now = "2026-11-06T10:00:00+02:00"
    sandbox_key = os.getenv("YEXT_API_KEY")
    sandbox_target = os.getenv("YEXT_ENTITY_ID")
    if a.with_sandbox and (a.mode != "mock" or not sandbox_key or not sandbox_target):
        p.error(
            "--with-sandbox requires mock mode plus configured team Yext credentials."
        )
    if a.host not in ("127.0.0.1", "localhost"):
        p.error(
            "This reference operator app binds only to loopback. Public hosting requires real operator authentication."
        )
    if not port_free(a.port) or (
        a.mode == "mock" and (a.port == a.mock_port or not port_free(a.mock_port))
    ):
        p.error(
            "Port is in use. Choose another --port / --mock-port; existing processes are left running."
        )
    base_state = Path(a.state_dir).resolve()
    base_state.mkdir(parents=True, exist_ok=True)
    os.chmod(base_state, 0o700)
    state = base_state / "presentation" if a.presentation else base_state
    state.mkdir(parents=True, exist_ok=True)
    os.chmod(state, 0o700)
    # Both launch modes share this lock, including their optional sandbox workspace.
    lock = (base_state / "app.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        p.error("Another application is using this state directory.")
    mock = None
    server = None
    stop = threading.Event()
    try:
        if a.mode == "mock":
            env = os.environ.copy()
            env.pop("YEXT_API_KEY", None)
            env.pop("GEMINI_API_KEY", None)
            env.update(
                CONNECT_MOCK_STATE=str(state / "mock-state.json"),
                MOCK_QUIET="1",
                PYTHONDONTWRITEBYTECODE="1",
            )
            mock = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "app.mock_runner",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(a.mock_port),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
            )
            os.environ["YEXT_BASE_URL"] = f"http://127.0.0.1:{a.mock_port}"
            os.environ["YEXT_API_KEY"] = "local-demo"
            for _ in range(100):
                if mock.poll() is not None:
                    raise RuntimeError("Owned mock API failed to start.")
                try:
                    with socket.create_connection(
                        ("127.0.0.1", a.mock_port), timeout=0.2
                    ):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Owned mock API did not become ready.")
        from app.service import Service
        from app.server import WebServer

        service = Service(ROOT, state, mode=a.mode, now=None if a.real_clock else a.now)
        service.presentation_mode = a.presentation
        if a.presentation:
            from app.replies import OwnerReplies
            from app.teammate.reply_engine import ReplyEngine
            service.replies = OwnerReplies(engine=ReplyEngine(api_key=""))
        sandbox_service = None
        if a.with_sandbox:
            from examples.yext_client import YextClient

            sandbox_service = Service(
                ROOT,
                base_state / "sandbox",
                mode="sandbox",
                now=None,
                source_id=os.getenv("SANDBOX_SOURCE_ENTITY_ID", "FI-D0001"),
                target_id=sandbox_target,
                allow_writes=True,
                client=YextClient(
                    base_url="https://sbx-api.yextapis.com",
                    api_key=sandbox_key,
                    v=os.getenv("YEXT_API_VERSION", "20261106"),
                ),
            )
        server = WebServer((a.host, a.port), service, sandbox_service=sandbox_service)
        service.tick()
        if sandbox_service:
            sandbox_service.tick()

        def timer():
            while not stop.wait(20):
                try:
                    service.tick()
                    if sandbox_service:
                        sandbox_service.tick()
                except Exception as e:
                    print("Scheduler needs attention:", type(e).__name__, flush=True)

        threading.Thread(target=timer, daemon=True).start()
        print(f"Connect Suggests: http://127.0.0.1:{a.port}", flush=True)
        print(
            f"Mode: {a.mode}; contact: SIMULATED; clock: {'REAL' if a.real_clock else a.now}",
            flush=True,
        )
        print("Ctrl+C stops only the servers started by this command.", flush=True)
        if sandbox_service:
            print(
                f"Team sandbox workspace: /sandbox/ → {sandbox_service.target_id}; explicit owner approval required.",
                flush=True,
            )
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Startup failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        stop.set()
        if server:
            server.fleet.close()
            server.server_close()
        if mock and mock.poll() is None:
            mock.terminate()
            try:
                mock.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mock.kill()
                mock.wait()
        lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
