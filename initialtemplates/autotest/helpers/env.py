"""The suite's configuration — the ONLY module that reads test/.env.

Everything that differs between one run and another lives in test/.env (git-ignored) and nowhere else: pointing
the suite at another project — a staging copy, a customer's tenant, a fresh import — is editing that file, never
the code. A literal host, realm or client anywhere else in the suite is a test that silently keeps testing the old
project after .env moved.

Nothing in this folder may contain a real password. The suite signs in with ONE author account and builds every
other identity it needs through the application itself; a scenario that needs a genuinely DIFFERENT person (an
approver who must not be the initiator) uses an optional persona account — PERSONA_<NAME>_USER /
PERSONA_<NAME>_PASSWORD — that the project's owner creates and writes into .env.

WHERE A VALUE COMES FROM. The keys that say WHICH project and WHO signs in — BASE_URL, API_BASE_URL, AUTH_USER,
AUTH_PASSWORD, PGDSN, API_KEY and every PERSONA_* — are read from test/.env ONLY. A variable of the same name
exported in the shell (another tool's AUTH_USER, a BASE_URL left over from yesterday) is ignored: otherwise it
silently wins and the suite tests the wrong project as the wrong person while .env looks right. The knobs of one
run — HEADLESS, SLOW_MO_MS, the timeouts, DEFAULT_LOCALE — come from .env too, but the shell may override them for
a single run: `HEADLESS=0 SLOW_MO_MS=250 ./start.sh -k <name>`.

Loading never fails: an import of this module must work on a machine with no .env at all, so the suite's code can
be checked offline. A run that needs the project calls CONFIG.require() first — the session fixtures do — and stops
with a sentence saying what to fill in.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

from dotenv import dotenv_values

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, ".env")
_FILE = {k: (v or "") for k, v in dotenv_values(ENV_FILE).items()} if os.path.isfile(ENV_FILE) else {}

PERSONA_PREFIX = "PERSONA_"
# The public API lives on the platform's own host, not under the project's path (doc 32).
PUBLIC_API_PATH = "/public-api/v1"


def _identity(name: str) -> str:
    """A key that says which project or which person: test/.env only, never the shell."""
    return _FILE.get(name, "").strip()


def _knob(name: str, default: str = "") -> str:
    """A setting of one run: test/.env, overridable from the shell."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        value = _FILE.get(name, "")
    return value.strip() or default


def _int(name: str, default: int) -> int:
    try:
        return int(_knob(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Persona:
    """A second sign-in for the scenarios that need another person, e.g. `approver`."""
    name: str
    user: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class Config:
    base_url: str
    auth_user: str
    # repr=False on every secret: an accidental print(CONFIG) or a failing assertion must not leak one.
    auth_password: str = field(repr=False)
    default_locale: str = "en_US"
    headless: bool = True
    slow_mo_ms: int = 0
    timeout_ms: int = 30000
    grid_timeout_ms: int = 45000
    pgdsn: str = field(default="", repr=False)
    api_key: str = field(default="", repr=False)
    api_base_url: str = ""
    personas: dict = field(default_factory=dict, repr=False)

    @property
    def realm_client(self) -> str:
        """`/<realm>/<client>` — the path every page of the project hangs on."""
        return urlparse(self.base_url).path.rstrip("/")

    def url(self, path: str = "") -> str:
        """An address inside the project: CONFIG.url("settings") -> <BASE_URL>/settings."""
        path = path.lstrip("/")
        return f"{self.base_url}/{path}" if path else self.base_url

    def api_url(self, path: str = "") -> str:
        """An address of the public API: CONFIG.api_url("<slug>/items") -> <root>/public-api/v1/<slug>/items.

        API_BASE_URL when .env sets it (a project served on a domain of its own still answers the API on the
        platform's host — doc 32), else the installation root of BASE_URL (everything before /<realm>/<client>).
        """
        base = self.api_base_url
        if not base:
            if not self.base_url:
                raise RuntimeError("BASE_URL is empty in test/.env — the API address is derived from it "
                                   "(or set API_BASE_URL)")
            parsed = urlparse(self.base_url)
            root_path = "/".join(parsed.path.rstrip("/").split("/")[:-2])
            base = f"{parsed.scheme}://{parsed.netloc}{root_path}{PUBLIC_API_PATH}"
        path = path.lstrip("/")
        return f"{base.rstrip('/')}/{path}" if path else base.rstrip("/")

    def require(self) -> "Config":
        """Stop before a browser opens when .env cannot point the suite at a project."""
        missing = [name for name, value in (("BASE_URL", self.base_url), ("AUTH_USER", self.auth_user),
                                            ("AUTH_PASSWORD", self.auth_password)) if not value]
        if missing:
            raise RuntimeError(
                "test/.env is not filled in: " + ", ".join(missing) + ". Copy test/.env.example to test/.env if "
                "it does not exist, then fill it in. BASE_URL is always <root>/<realm>/<client> — never the bare "
                "installation root, which bounces to …/auth;jsessionid=… and renders none of the project.")
        if len(self.realm_client.strip("/").split("/")) < 2:
            raise RuntimeError(
                f"BASE_URL={self.base_url!r} has no /<realm>/<client> path. Point it at the PROJECT "
                "(<root>/<realm>/<client>), not at the installation.")
        return self

    def persona(self, name: str) -> Persona | None:
        """The persona account `name` (case-insensitive), or None when .env does not provide it."""
        return self.personas.get(name.strip().lower())


def _personas() -> dict:
    found = {}
    for key, user in _FILE.items():
        if not (key.startswith(PERSONA_PREFIX) and key.endswith("_USER")):
            continue
        name = key[len(PERSONA_PREFIX):-len("_USER")].lower()
        password = _FILE.get(f"{PERSONA_PREFIX}{name.upper()}_PASSWORD", "")
        if name and user.strip() and password:
            found[name] = Persona(name=name, user=user.strip(), password=password)
    return found


def load_config() -> Config:
    return Config(
        base_url=_identity("BASE_URL").rstrip("/"),
        auth_user=_identity("AUTH_USER"),
        auth_password=_FILE.get("AUTH_PASSWORD", ""),
        default_locale=_knob("DEFAULT_LOCALE", "en_US"),
        headless=_knob("HEADLESS", "1") not in ("0", "false", "False", "no"),
        slow_mo_ms=_int("SLOW_MO_MS", 0),
        timeout_ms=_int("DEFAULT_TIMEOUT_MS", 30000),
        grid_timeout_ms=_int("GRID_TIMEOUT_MS", 45000),
        pgdsn=_identity("PGDSN"),
        api_key=_identity("API_KEY"),
        api_base_url=_identity("API_BASE_URL").rstrip("/"),
        personas=_personas(),
    )


CONFIG = load_config()
