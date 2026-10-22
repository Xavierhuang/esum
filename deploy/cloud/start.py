"""Runs all of esum in one LingCode Cloud hosted-app container.

The platform gives one web process, DATABASE_URL, PORT and the backend's vault secrets. This launcher answers on $PORT
at once with a status page, migrates the database, creates the owner on first start, starts the broker, worker,
scheduler, browser and its egress proxy on localhost, then hands $PORT to the api. A background service that stops is
restarted. If start-up fails, the status page stays up and says which step failed (with secrets blanked out).

Vault secrets it reads: OPA_BROKER_KEK (required to store keys and account sign-ins), and optionally OPA_OWNER_EMAIL and
OPA_OWNER_PASSWORD (to create a first account; people can also sign up, which is on unless OPA_SIGNUP_ENABLED=false), OPA_ANTHROPIC_API_KEY and the Google/Notion/GitHub
OAuth settings. The disk is read-only apart from /tmp, so uploaded files and exports last until the next restart.
"""
from __future__ import annotations

import asyncio
import collections
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
PY = sys.executable
SECRET_NAMES = ("OPA_BROKER_KEK", "OPA_OWNER_PASSWORD", "OPA_ANTHROPIC_API_KEY", "OPA_GOOGLE_CLIENT_SECRET",
                "OPA_NOTION_CLIENT_SECRET", "OPA_GITHUB_CLIENT_SECRET", "OPA_INTERNAL_TOKEN")

BOOTSTRAP = """
import asyncio, sys
from sqlalchemy import select
from opa.api.auth import hash_password
from opa.db.engine import get_sessionmaker
from opa.db.models import Owner

async def main():
    async with get_sessionmaker()() as db, db.begin():
        if await db.scalar(select(Owner.id).limit(1)):
            print("owner exists")
            return
        db.add(Owner(email=sys.argv[1], password_hash=hash_password(sys.argv[2])))
        print("owner created for " + sys.argv[1])

asyncio.run(main())
"""


def log(msg: str) -> None:
    print(f"[esum] {msg}", flush=True)


class Status:
    """What the status page shows while the api is not serving."""

    def __init__(self) -> None:
        self.state, self.step, self.detail = "starting", "booting", ""
        self.secrets: list[str] = []

    def redact(self, text: str) -> str:
        for s in self.secrets:
            if s and len(s) >= 6:
                text = text.replace(s, "[secret]")
        return text

    def fail(self, step: str, detail: str) -> None:
        self.state, self.step, self.detail = "failed", step, self.redact(detail)[-6000:]
        log(f"start-up failed at {step}")


STATUS = Status()


class StatusPage(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = {"esum": STATUS.state, "step": STATUS.step}
        if STATUS.state == "failed":
            body["detail"] = STATUS.detail
        data = json.dumps(body, indent=2).encode()
        # Always 200: a slow first migration must not look like a crash, and after a failed start the platform
        # must keep this page up (rather than restart into the same failure) so the reason stays readable.
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_HEAD = do_GET

    def log_message(self, *_: object) -> None:
        pass


class StatusServer:
    def __init__(self, port: int) -> None:
        self.port = port
        self.httpd: ThreadingHTTPServer | None = None

    def start(self) -> None:
        if self.httpd is None:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), StatusPage)
            threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


class Service:
    def __init__(self, name: str, cmd: list[str], env: dict[str, str]) -> None:
        self.name, self.cmd, self.env = name, cmd, env
        self.proc: subprocess.Popen | None = None
        self.tail: collections.deque[str] = collections.deque(maxlen=60)
        self.restarts: list[float] = []
        self.given_up = False

    def start(self) -> None:
        self.proc = subprocess.Popen(self.cmd, env=self.env, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        threading.Thread(target=self._pump, args=(self.proc,), daemon=True).start()
        log(f"started {self.name}")

    def _pump(self, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            self.tail.append(line.rstrip())
            print(f"[{self.name}] {line.rstrip()}", flush=True)

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def output(self) -> str:
        return "\n".join(self.tail)

    def stop(self) -> None:
        if self.alive():
            assert self.proc is not None
            self.proc.terminate()


def asyncpg_url(raw: str) -> str:
    """postgres://…?sslmode=require  ->  postgresql+asyncpg://…?ssl=require"""
    parts = urlsplit(raw)
    query = []
    for k, v in parse_qsl(parts.query):
        if k == "sslmode":
            query.append(("ssl", v))
        elif k in ("ssl", "options", "application_name", "host", "port"):
            query.append((k, v))
    return urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), ""))


async def inspect_database(url: str) -> dict:
    """Who the app connects as and what it may do: create schemas or tables, bypass row-level security, see the version."""
    import asyncpg

    parts = urlsplit(url.replace("postgresql+asyncpg", "postgresql"))
    query = dict(parse_qsl(parts.query))
    ssl = query.pop("ssl", None)
    dsn = urlunsplit(("postgresql", parts.netloc, parts.path, urlencode(query), ""))
    conn = await asyncpg.connect(dsn, ssl=ssl if ssl and ssl != "disable" else None)
    try:
        row = await conn.fetchrow("""
            select current_user as role, current_schema() as schema,
                   has_database_privilege(current_database(), 'CREATE') as can_create_schema,
                   has_schema_privilege(current_schema(), 'CREATE') as can_create_tables,
                   (select rolbypassrls or rolsuper from pg_roles where rolname = current_user) as bypasses_rls,
                   to_regclass('alembic_version') is not null as has_version_table""")
        info = dict(row)
        info["version"] = await conn.fetchval("select version_num from alembic_version limit 1") if info["has_version_table"] else None
    finally:
        await conn.close()
    return info


def run_step(step: str, cmd: list[str], env: dict[str, str]) -> bool:
    STATUS.step = step
    log(step)
    r = subprocess.run(cmd, env=env, cwd=ROOT, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if out:
        print(STATUS.redact(out), flush=True)
    if r.returncode != 0:
        STATUS.fail(step, out)
        return False
    return True


def hold() -> int:
    """Keep the status page up after a failed start, so the reason can be read at the app's address."""
    while True:
        time.sleep(3600)


def main() -> int:
    port = int(os.environ.get("PORT", "8080"))
    status_server = StatusServer(port)
    status_server.start()

    raw = os.environ.get("DATABASE_URL") or os.environ.get("LINGCODE_DB_URL") or os.environ.get("OPA_DATABASE_URL")
    if not raw:
        STATUS.fail("configuration", "no DATABASE_URL: this must run on a LingCode Cloud hosted app (or set OPA_DATABASE_URL)")
        return hold()
    STATUS.secrets = [os.environ.get(n, "") for n in SECRET_NAMES] + [urlsplit(raw).password or ""]
    url = raw if raw.startswith("postgresql+asyncpg://") else asyncpg_url(raw)
    internal = {"broker": port + 1, "browser": port + 2, "proxy": port + 49}  # localhost only
    tmp = Path("/tmp/esum")
    for d in ("artifacts", "exports"):
        (tmp / d).mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env.update({
        "OPA_DATABASE_URL": url, "OPA_MODE": env.get("OPA_MODE", "live"), "OPA_MODEL_PROVIDER": env.get("OPA_MODEL_PROVIDER", "anthropic"),
        "OPA_INTERNAL_TOKEN": secrets.token_hex(24),  # new each start; only these processes share it
        "OPA_BIND_HOST": "127.0.0.1", "OPA_BIND_PORT": str(port),
        "OPA_BROKER_URL": f"http://127.0.0.1:{internal['broker']}", "OPA_BROKER_BIND_PORT": str(internal["broker"]),
        "OPA_BROWSER_URL": f"http://127.0.0.1:{internal['browser']}", "OPA_BROWSER_BIND_PORT": str(internal["browser"]),
        "OPA_WEB_PROXY_URL": f"http://127.0.0.1:{internal['proxy']}",
        "OPA_WEB_DIST_DIR": str(ROOT / "web-dist"), "OPA_ARTIFACT_DIR": str(tmp / "artifacts"), "OPA_EXPORT_DIR": str(tmp / "exports"),
        "OPA_SECURE_COOKIES": env.get("OPA_SECURE_COOKIES", "true"),
        "OPA_SIGNUP_ENABLED": env.get("OPA_SIGNUP_ENABLED", "true"),  # a hosted esum lets people create their own accounts "PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1",
    })
    STATUS.secrets.append(env["OPA_INTERNAL_TOKEN"])
    for name in ("DATABASE_URL", "LINGCODE_DB_URL"):
        env.pop(name, None)  # services read OPA_DATABASE_URL only
    if not env.get("OPA_BROKER_KEK"):
        log("OPA_BROKER_KEK is not set in the backend's secrets: saving API keys and account sign-ins will fail until it is")

    STATUS.step = "connecting to the database"
    try:
        db = asyncio.run(inspect_database(url))
    except Exception as e:  # noqa: BLE001 - shown on the status page
        STATUS.fail("connecting to the database", f"{e.__class__.__name__}: {e}")
        return hold()
    log("database: " + ", ".join(f"{k}={v}" for k, v in db.items()))
    env["OPA_BROKER_SCHEMA"] = env.get("OPA_BROKER_SCHEMA") or ("broker" if db["can_create_schema"] else db["schema"])
    log(f"broker tables in schema {env['OPA_BROKER_SCHEMA']!r}")

    if db["can_create_tables"]:
        if not run_step("migrating the database", [PY, "-m", "opa.cli", "migrate"], env):
            return hold()
    else:
        # A managed database (LingCode Cloud): tables are created by the platform's migration tool, not by the app.
        sys.path.insert(0, str(ROOT))
        from opa.db.migrate import current_head

        head = current_head()
        if db["version"] != head:
            hint = ("the app's database role cannot see esum's rows (row-level security is on and the role does not bypass it)"
                    if db["has_version_table"] and db["version"] is None and not db["bypasses_rls"] else
                    "apply the schema from deploy/cloud with the platform's migration tool")
            STATUS.fail("checking the database schema", f"role {db['role']}: schema version {db['version']!r}, esum needs {head!r}: {hint}")
            return hold()
        log(f"schema is current ({head}); the platform manages migrations")
    email, password = env.get("OPA_OWNER_EMAIL"), env.get("OPA_OWNER_PASSWORD")
    if email and password:
        if not run_step("creating the owner", [PY, "-c", BOOTSTRAP, email, password], env):
            return hold()
    else:
        log("OPA_OWNER_EMAIL / OPA_OWNER_PASSWORD are not set: no owner is created on this start")

    background = [
        Service("proxy", [PY, "-m", "opa.cli", "proxy", "--policy", "public-web", "--listen", f"127.0.0.1:{internal['proxy']}"], env),
        Service("browser", [PY, "-m", "opa.cli", "browser"], env),
        Service("broker", [PY, "-m", "opa.cli", "broker"], env),
        Service("worker", [PY, "-m", "opa.cli", "worker"], env),
        Service("scheduler", [PY, "-m", "opa.cli", "scheduler"], env),
    ]
    STATUS.step = "starting services"
    for s in background:
        s.start()
    time.sleep(4)
    dead = [s for s in background if not s.alive()]
    if dead:
        STATUS.fail(f"starting {dead[0].name}", dead[0].output())
        return hold()

    api = Service("api", [PY, "-m", "opa.cli", "api"], dict(env, OPA_BIND_HOST="0.0.0.0"))  # the only public listener
    status_server.stop()
    api.start()

    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        time.sleep(2)
        if not api.alive():
            STATUS.fail("running the api", api.output())
            for s in background:
                s.stop()
            status_server.start()
            return hold()
        for s in background:
            if s.alive() or s.given_up:
                continue
            now = time.time()
            s.restarts = [t for t in s.restarts if now - t < 600] + [now]
            log(f"{s.name} stopped (exit {s.proc.returncode if s.proc else '?'}); restart {len(s.restarts)} of 5 in 10 minutes")
            if len(s.restarts) > 5:
                log(f"{s.name} keeps stopping; leaving it off. Last output:\n{STATUS.redact(s.output())}")
                s.given_up = True
                continue
            s.start()
    for s in [api, *background]:
        s.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
