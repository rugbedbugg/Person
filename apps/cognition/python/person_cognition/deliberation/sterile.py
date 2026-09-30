"""The sterile process a provider CLI runs in (ADR 0020 rule 6, C2).

A provider may see the instruction and the one context it is sent, and
nothing else of this machine. The operator's home, the repository, Person's
evidence and every other configuration stay out of reach, in layers:

1. provider-native tool removal (each adapter's flags);
2. a fresh, empty HOME and provider configuration directory holding only the
   single authentication file the CLI needs, bind-mounted, never copied, so
   a token the CLI refreshes is refreshed in place;
3. an OS sandbox (bubblewrap) with no view of `/home`, the repository or
   `/tmp`, a minimal read-only system, and a cleared environment.

A profile has a version. Changing it, a CLI version or an invocation flag
makes the backend unverified until its sterility probe passes again. Nothing
here reads, hashes or records credential contents.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

PROFILE_VERSION = "sterile-v1"
SANDBOX_HOME = "/sandbox/home"
SANDBOX_WORK = "/sandbox/work"

#: Read-only system paths a provider CLI needs, and nothing personal.
SYSTEM_BINDS: tuple[str, ...] = ("/usr", "/opt", "/etc/ssl", "/etc/ca-certificates")
SYSTEM_FILES: tuple[str, ...] = (
    "/etc/resolv.conf",
    "/etc/hosts",
    "/etc/nsswitch.conf",
    "/etc/localtime",
)
SYMLINKS: tuple[tuple[str, str], ...] = (
    ("usr/bin", "/bin"),
    ("usr/bin", "/sbin"),
    ("usr/lib", "/lib"),
    ("usr/lib", "/lib64"),
)


class SterilityError(RuntimeError):
    """The sterile boundary could not be built. The backend must not run."""


@dataclass(frozen=True, slots=True)
class Credential:
    """One authentication file, and where the CLI expects it inside HOME."""

    source: Path
    #: Relative to the sandbox HOME, e.g. `.claude/.credentials.json`.
    target: str


@dataclass(frozen=True, slots=True)
class Sandbox:
    """One prepared sandbox: the argv prefix and environment to run under."""

    root: Path
    prefix: tuple[str, ...]
    environment: Mapping[str, str]

    def popen(self, argv: Sequence[str]) -> subprocess.Popen[str]:
        """An interactive process in the sandbox, for line protocols."""
        return subprocess.Popen(
            [*self.prefix, *argv],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(self.environment),
            bufsize=1,
        )

    def run(
        self, argv: Sequence[str], *, stdin: str, timeout_s: float
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*self.prefix, *argv],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=dict(self.environment),
            check=False,
        )


def bubblewrap() -> str:
    found = shutil.which("bwrap")
    if found is None:
        raise SterilityError("bubblewrap (bwrap) is not installed; no sterile backend can run")
    return found


@contextmanager
def sterile(
    credentials: Sequence[Credential],
    *,
    extra_environment: Mapping[str, str] | None = None,
    base: Path | None = None,
) -> Iterator[Sandbox]:
    """A fresh sandbox for one call, removed afterwards."""
    for credential in credentials:
        if not credential.source.is_file():
            raise SterilityError(f"missing authentication file for {credential.target}")
    root = Path(tempfile.mkdtemp(prefix="person-sterile-", dir=base))
    try:
        home = root / "home"
        work = root / "work"
        work.mkdir(parents=True)
        home.mkdir(mode=0o700)
        prefix: list[str] = [
            bubblewrap(),
            "--unshare-all",
            "--share-net",
            "--die-with-parent",
            "--new-session",
            "--clearenv",
            # The machine's name is the operator's, not the provider's.
            "--hostname",
            "person-sandbox",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
        ]
        for path in SYSTEM_BINDS:
            if Path(path).exists():
                prefix += ["--ro-bind", path, path]
        for path in SYSTEM_FILES:
            if Path(path).exists():
                prefix += ["--ro-bind", str(Path(path).resolve()), path]
        for source, link in SYMLINKS:
            prefix += ["--symlink", source, link]
        prefix += ["--bind", str(home), SANDBOX_HOME, "--bind", str(work), SANDBOX_WORK]
        for credential in credentials:
            target = Path(SANDBOX_HOME) / credential.target
            (home / credential.target).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            (home / credential.target).touch(mode=0o600)
            prefix += ["--bind", str(credential.source), str(target)]
        prefix += ["--chdir", SANDBOX_WORK]
        environment = {
            "HOME": SANDBOX_HOME,
            "PATH": "/usr/bin",
            "LANG": "C.UTF-8",
            "TMPDIR": "/tmp",
            **(extra_environment or {}),
        }
        for key, value in environment.items():
            prefix += ["--setenv", key, value]
        yield Sandbox(root=root, prefix=tuple(prefix), environment={"PATH": "/usr/bin"})
    finally:
        shutil.rmtree(root, ignore_errors=True)


def self_check(credentials: Sequence[Credential]) -> dict[str, object]:
    """Deterministic, model-free proof of what a sandbox can and cannot see.

    Runs a shell in exactly the sandbox a provider gets and reports what it
    finds. Costs no quota; run before any provider call.
    """
    real_home = os.environ.get("HOME", "")
    repository = str(Path(__file__).resolve().parents[5])
    probe = (
        f"for p in {real_home!r} {repository!r} /home /root /run/user; do "
        '[ -e "$p" ] && echo "VISIBLE $p"; done; '
        'echo "HOST $(cat /proc/sys/kernel/hostname)"; '
        "echo HOME_ENTRIES; find /sandbox/home -mindepth 1 | sort; "
        "echo ENV; env | cut -d= -f1 | sort"
    )
    with sterile(credentials) as sandbox:
        done = sandbox.run(["/usr/bin/sh", "-c", probe], stdin="", timeout_s=30)
    lines = done.stdout.splitlines()
    visible = [line.removeprefix("VISIBLE ") for line in lines if line.startswith("VISIBLE ")]
    home_at = lines.index("HOME_ENTRIES") if "HOME_ENTRIES" in lines else len(lines)
    env_at = lines.index("ENV") if "ENV" in lines else len(lines)
    host = next((line.removeprefix("HOST ") for line in lines if line.startswith("HOST ")), None)
    return {
        "profile": PROFILE_VERSION,
        "exit": done.returncode,
        "hostname": host,
        "visible": visible,
        "home_entries": lines[home_at + 1 : env_at],
        "environment": lines[env_at + 1 :],
    }
