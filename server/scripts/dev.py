"""Run the whole app locally with one command: `npm run dev` (or `node scripts/dev.mjs`) from the repository root.

Starts an embedded PostgreSQL, applies migrations, creates a local sign-in the first time, and runs the
api, broker, worker, scheduler, web proxy, and browser service. Stop with Ctrl-C.

Demo mode (the default) uses sample data and scripted replies and never contacts real providers or the
Claude API. Live mode (OPA_MODE=live in server/.env, with OPA_ANTHROPIC_API_KEY and the Google OAuth
client) uses your real accounts and Claude; its data is kept apart from the demo's (server/data/dev-pg-live).
A broker key for stored credentials is created once in server/data/dev-broker-kek unless OPA_BROKER_KEK is set.

Environment: PORT or OPA_BIND_PORT (default 8080; the other services use the next ports),
OPA_DEV_EMAIL and OPA_DEV_PASSWORD (the sign-in created on first run). Every service also reads server/.env.
"""
from __future__ import annotations

import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
DATA = SERVER / "data"
LOGS = DATA / "dev-logs"
OPA = str(SERVER / ".venv" / "bin" / "opa")
PY = str(SERVER / ".venv" / "bin" / "python")
DIST = SERVER.parent / "web" / "dist"
PIDS = DATA / "dev-pids"


def clear_leftovers() -> None:
    """Stop services a previous run left behind (for example, if the launcher itself was killed)."""
    if not PIDS.is_file():
        return
    for line in PIDS.read_text().split():
        try:
            pid = int(line)
            cmd = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout
            if str(SERVER / ".venv" / "bin" / "opa") in cmd:
                os.kill(pid, signal.SIGINT)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    time.sleep(2)
    PIDS.unlink(missing_ok=True)


def dotenv(path: Path) -> dict[str, str]:
    """KEY=VALUE lines of server/.env, the file every service reads (pydantic-settings)."""
    out: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                out[key.strip()] = value.strip().strip("'\"")
    return out


def broker_kek() -> str:
    """A local key for encrypting provider credentials, created once and kept with the dev data."""
    path = DATA / "dev-broker-kek"
    if not path.is_file():
        path.write_text(subprocess.run([OPA, "generate-kek"], check=True, capture_output=True, text=True).stdout.strip())
        path.chmod(0o600)
    return path.read_text().strip()


def free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main() -> int:
    import pgserver  # dev dependency (uv sync --extra dev)

    DATA.mkdir(parents=True, exist_ok=True)
    clear_leftovers()
    port = int(os.environ.get("PORT") or os.environ.get("OPA_BIND_PORT") or 8080)
    broker, browser, proxy = port + 1, port + 2, port + 49  # 8081, 8082, 8129 by default
    busy = [p for p in (port, broker, browser, proxy) if not free(p)]
    if busy:
        print(f"Port(s) {', '.join(map(str, busy))} are already in use. Stop the other copy of the app, or set PORT to another value.")
        return 1
    if not (DIST / "index.html").is_file():
        print("web/dist is missing: build the web app first (npm run build in web/).")
        return 1
    cfg = {**dotenv(SERVER / ".env"), **{k: v for k, v in os.environ.items() if k.startswith("OPA_")}}
    mode = cfg.get("OPA_MODE") or "demo"
    live = mode == "live"
    provider = cfg.get("OPA_MODEL_PROVIDER") or ("anthropic" if live else "scripted")
    if mode not in ("demo", "live"):
        print(f"OPA_MODE must be demo or live, not {mode!r}.")
        return 1
    if not live and provider != "scripted":
        print("Demo mode never calls Claude. To use your API key, set OPA_MODE=live in server/.env (see docs/OPERATIONS.md).")
        return 1
    if live and provider == "anthropic" and not cfg.get("OPA_ANTHROPIC_API_KEY"):
        print("Live mode needs your Claude API key: set OPA_ANTHROPIC_API_KEY in server/.env (see server/.env.example).")
        return 1
    email = os.environ.get("OPA_DEV_EMAIL", "demo@example.com")
    password = os.environ.get("OPA_DEV_PASSWORD", "demo-password-123")

    LOGS.mkdir(parents=True, exist_ok=True)
    print("Starting the database…", flush=True)
    db = pgserver.get_server(str(DATA / ("dev-pg-live" if live else "dev-pg")))
    url = db.get_uri().replace("postgresql://", "postgresql+asyncpg://")
    base = f"http://127.0.0.1:{port}"
    suffix = "-live" if live else ""
    env = dict(os.environ, OPA_DATABASE_URL=url, OPA_MODE=mode, OPA_MODEL_PROVIDER=provider, OPA_BIND_PORT=str(port),
               OPA_WEB_DIST_DIR=str(DIST), OPA_PUBLIC_BASE_URL=cfg.get("OPA_PUBLIC_BASE_URL") or base, OPA_BROKER_URL=f"http://127.0.0.1:{broker}",
               OPA_BROKER_BIND_PORT=str(broker), OPA_BROWSER_URL=f"http://127.0.0.1:{browser}", OPA_BROWSER_BIND_PORT=str(browser),
               OPA_WEB_PROXY_URL=f"http://127.0.0.1:{proxy}", OPA_ARTIFACT_DIR=str(DATA / f"artifacts{suffix}"), OPA_EXPORT_DIR=str(DATA / f"exports{suffix}"))
    if provider == "scripted" and not cfg.get("OPA_SCRIPTED_MODEL_PATH"):
        env["OPA_SCRIPTED_MODEL_PATH"] = str(SERVER / "opa" / "worker" / "demo_script.yaml")
    if not cfg.get("OPA_BROKER_KEK"):
        env["OPA_BROKER_KEK"] = broker_kek()  # sealed website sign-ins need it in demo mode too
    notes = []
    if live and not (cfg.get("OPA_GOOGLE_CLIENT_ID") and cfg.get("OPA_GOOGLE_CLIENT_SECRET")):
        notes.append("Google is not set up (OPA_GOOGLE_CLIENT_ID and OPA_GOOGLE_CLIENT_SECRET), so Gmail and Calendar cannot be connected yet.")
    if not live and cfg.get("OPA_ANTHROPIC_API_KEY"):
        notes.append("Found OPA_ANTHROPIC_API_KEY, but this is demo mode. Set OPA_MODE=live in server/.env to use it.")
    env["OPA_INTERNAL_TOKEN"] = secrets.token_hex(16)  # new each run; only these processes share it
    env.pop("PORT", None)
    procs: list[tuple[str, subprocess.Popen]] = []

    def stop(*_: object) -> None:
        for _name, p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
        for _name, p in procs:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        PIDS.unlink(missing_ok=True)
        db.cleanup()

    try:
        subprocess.run([OPA, "migrate"], env=env, check=True, capture_output=True)
        subprocess.run([PY, "-c", _BOOTSTRAP, email, password], env=env, check=True)
        commands = {
            "api": [OPA, "api"], "broker": [OPA, "broker"], "worker": [OPA, "worker"], "scheduler": [OPA, "scheduler"],
            "web-proxy": [OPA, "proxy", "--policy", "public-web", "--listen", f"127.0.0.1:{proxy}"], "browser": [OPA, "browser"],
        }
        for name, cmd in commands.items():
            log = open(LOGS / f"{name}.log", "w")  # noqa: SIM115 - kept open for the child's lifetime
            procs.append((name, subprocess.Popen(cmd, env=env, cwd=SERVER, stdout=log, stderr=subprocess.STDOUT)))
        PIDS.write_text("\n".join(str(p.pid) for _n, p in procs))
        deadline = time.time() + 40
        while True:
            try:
                urllib.request.urlopen(f"{base}/healthz", timeout=1)
                break
            except Exception:
                if time.time() > deadline or procs[0][1].poll() is not None:
                    print(f"The app did not start. See {LOGS / 'api.log'}")
                    return 1
                time.sleep(0.3)
        from opa.core.settings import Settings

        model = cfg.get("OPA_MODEL_ID") or Settings.model_fields["model_id"].default
        about = (f"Live mode: your real accounts, model {model}." if live else
                 "Demo mode: sample data, scripted replies. For the real assistant, see docs/OPERATIONS.md (Use your real accounts).")
        extra = "".join(f"\n  Note: {n}" for n in notes)
        print(f"\n  Open  {base}\n  Sign in with {email} / {password}\n  {about}{extra}\n  Logs: {LOGS}\n  Stop with Ctrl-C.\n", flush=True)
        signal.signal(signal.SIGTERM, _interrupt)  # a launcher's Stop button sends SIGTERM
        parent = os.getppid()
        while True:
            if os.getppid() != parent:  # whatever started us is gone: shut down rather than linger
                return 0
            for name, p in procs:
                if p.poll() is not None:
                    print(f"{name} stopped (exit {p.returncode}). See {LOGS / (name + '.log')}")
                    return 1
            time.sleep(1)
    except KeyboardInterrupt:
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Setup failed: {' '.join(map(str, e.cmd[:2]))}\n{(e.stderr or b'').decode(errors='replace')[-2000:]}")
        return 1
    finally:
        stop()


def _interrupt(*_: object) -> None:
    raise KeyboardInterrupt


_BOOTSTRAP = """
import asyncio, sys
from sqlalchemy import select
from opa.api.auth import hash_password
from opa.db.engine import get_sessionmaker
from opa.db.models import Owner
async def go():
    async with get_sessionmaker()() as db, db.begin():
        if not (await db.execute(select(Owner.id))).first():
            db.add(Owner(email=sys.argv[1], password_hash=hash_password(sys.argv[2])))
asyncio.run(go())
"""

if __name__ == "__main__":
    sys.exit(main())
