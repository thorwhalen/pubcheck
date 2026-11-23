"""What every part of the check shares: the time budget, private files, the settings and the event log.

**The budget.** Every lookup (``gh``, ``acquaint``, ``git``) runs inside one
:class:`Budget`, so a check decides within its deadline instead of being killed by its
caller. Out of time, a lookup answers ``None`` (unknown), and the caller decides what
unknown means: presumed public for visibility, unavailable for the registry.

**Settings.** One mapping, read from ``~/.config/pubcheck/config.toml``
(``$PUBCHECK_CONFIG`` names another file), with environment variables over it, and keyword
arguments over both at each call site. The keys are in :data:`DFLT_SETTINGS`.

**The log.** ``~/.local/state/public-text-guard/events.jsonl`` (mode 0600,
``$PUBLIC_TEXT_GUARD_STATE_DIR``), one JSON object per decision worth keeping: never the
text and never the matched terms, only the categories, the repo, the writer, a short hash
of the text (so two events about the same text can be paired), an error's type, and an
override's reason as its author wrote it.

>>> b = Budget(0)
>>> b.run(["true"]) is None  # no time left: no subprocess at all
True
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

import tomllib

BUDGET_SECONDS = 12.0
MAX_TEXT = 70_000  # characters; GitHub caps a body at 65,536, and longer is not checked
LOOKUP_TIMEOUT = 8.0
#: Seconds a check keeps for itself after its lookups (deciding, logging, exiting), so a
#: caller that kills it at its deadline gets an answer instead.
FINISH_RESERVE = 1.0
#: A check slower than this (seconds) logs what its lookups cost, to find the slow one.
SLOW_CHECK = 3.0
#: Seconds to reap a killed lookup (its pipes may be held by a process outside its group).
REAP_SECONDS = 0.2
CACHE_DIR_ENV = "PUBLIC_TEXT_GUARD_CACHE_DIR"
CACHE_DIR = "~/.cache/public-text-guard"
STATE_DIR_ENV = "PUBLIC_TEXT_GUARD_STATE_DIR"
STATE_DIR = "~/.local/state/public-text-guard"
CONFIG_ENV = "PUBCHECK_CONFIG"
CONFIG_FILE = "~/.config/pubcheck/config.toml"

#: The settings and their defaults. Everything that names the operator's own repos or
#: folders is unset by default and lives in their config file, never in this code:
#:
#: - ``hold_repo``: the private repo where a held post becomes a desk item (unset: no item
#:   is filed; it must be private, or nothing is copied there);
#: - ``hold_label``: the label the desk reads;
#: - ``private_owner``: the account whose ``<owner>/_<name>`` repos are private companions
#:   (a reference to one is private, and a flag points at the target's companion);
#: - ``private_issues``: the private repo for context that has no companion;
#: - ``private_patterns``: more regexes for private references (working folders, the
#:   layout of the operator's machines), on top of this machine's home folder;
#: - ``credential_scanner``: an external secret scanner to run beside the built-in
#:   credential patterns, e.g. ``betterleaks`` (unset: none is run). See
#:   :func:`pubcheck.detectors.scanner_credential`.
DFLT_SETTINGS = {
    "hold_repo": None,
    "hold_label": "escalate",
    "budget_seconds": BUDGET_SECONDS,
    "private_owner": None,
    "private_issues": None,
    "private_patterns": (),
    "credential_scanner": None,
}
#: The environment variable that overrides each setting (``private_patterns``: config only).
SETTINGS_ENV = {
    "hold_repo": "PUBCHECK_HOLD_REPO",
    "hold_label": "PUBCHECK_HOLD_LABEL",
    "budget_seconds": "PUBCHECK_BUDGET_SECONDS",
    "private_owner": "PUBCHECK_PRIVATE_OWNER",
    "private_issues": "PUBCHECK_PRIVATE_ISSUES",
    "credential_scanner": "PUBCHECK_CREDENTIAL_SCANNER",
}


class Budget:
    """One deadline shared by every lookup of a check, and a record of what each lookup cost.

    ``lookups`` holds ``(label, seconds, outcome)`` per lookup, ``outcome`` one of ``ok``,
    ``failed``, ``timeout`` or ``skipped`` (no time left); the label is the program's
    name only, never an argument (one could carry a path or the text).
    """

    def __init__(self, seconds: float | None = BUDGET_SECONDS):
        self.deadline = None if seconds is None else time.monotonic() + seconds
        self.lookups: list[tuple[str, float, str]] = []

    def left(self, cap: float = LOOKUP_TIMEOUT) -> float:
        """Seconds a lookup may take: ``cap``, or what is left of the budget when less."""
        if self.deadline is None:
            return cap
        return min(cap, self.deadline - time.monotonic())

    def run(
        self,
        argv,
        *,
        cap: float = LOOKUP_TIMEOUT,
        stdin: str | None = None,
        env: Mapping | None = None,
        cwd: str | None = None,
    ):
        """``subprocess.run`` within the budget; ``None`` when out of time or on failure.

        The lookup runs in its own process group, and running out of time kills the whole
        group: a program that started helpers of its own leaves none behind, still holding
        the machine, once the check has given up on it. The trade-off: a caller that kills the check
        itself (rather than giving it a ``--deadline``) does not reach a lookup in flight,
        which runs on until its own end.
        """
        label = _lookup_label(argv)
        left = self.left(cap)
        if left <= 0.05:
            self.lookups.append((label, 0.0, "skipped"))
            return None
        started = time.monotonic()

        def note(outcome):
            self.lookups.append((label, round(time.monotonic() - started, 2), outcome))

        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL if stdin is None else subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=cwd,
                start_new_session=True,
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            note("failed")
            return None
        try:
            out, err = proc.communicate(stdin, timeout=left)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            note("timeout")
            return None
        except (OSError, ValueError, subprocess.SubprocessError):
            _kill_group(proc)
            note("failed")
            return None
        note("ok")
        return subprocess.CompletedProcess(argv, proc.returncode, out, err)

    def report(self) -> list[list]:
        """The lookups as JSON-ready rows ``[label, seconds, outcome]``."""
        return [list(row) for row in self.lookups]

    @property
    def strained(self) -> bool:
        """Whether a lookup ran out of time or was skipped for lack of it."""
        return any(outcome in ("timeout", "skipped") for _, _, outcome in self.lookups)


def _lookup_label(argv) -> str:
    """``gh``, ``acquaint``, ``git``: the program's name only, as an argument may be a path."""
    return Path(str(argv[0])).name if len(argv) else "?"


def _kill_group(proc) -> None:
    """Kill ``proc`` and every process of its group, then reap it; never raises."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.communicate(timeout=REAP_SECONDS)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass


def write_private(path, text: str, *, append: bool = False) -> None:
    """Write ``text`` to ``path`` with mode 0600, in a 0700 folder (atomically unless appending)."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        if append:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a") as f:
                f.write(text)
            return
        tmp = path.with_name(path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(text)
        tmp.replace(path)
    except OSError:
        pass


def cache_dir() -> Path:
    """Where the vocabulary and the companion answers are cached."""
    return Path(os.environ.get(CACHE_DIR_ENV) or CACHE_DIR).expanduser()


def settings(overrides: Mapping | None = None) -> dict:
    """:data:`DFLT_SETTINGS`, then the config file, then the environment, then ``overrides``.

    >>> settings({"hold_repo": "me/_desk"})["hold_repo"]
    'me/_desk'
    """
    out = dict(DFLT_SETTINGS)
    path = Path(os.environ.get(CONFIG_ENV) or CONFIG_FILE).expanduser()
    if path.is_file():
        try:
            data = tomllib.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        out.update(data)  # unknown keys are kept: a detector may read its own settings
    for key, var in SETTINGS_ENV.items():
        if os.environ.get(var):
            out[key] = os.environ[var]
    out.update({k: v for k, v in (overrides or {}).items() if v is not None})
    out["budget_seconds"] = float(out["budget_seconds"])
    out["private_patterns"] = tuple(out["private_patterns"] or ())
    return out


def text_hash(*texts: str) -> str:
    """A short hash of the texts: pairs log events and desk items without copying the text."""
    digest = hashlib.sha256("\x00".join(t or "" for t in texts).encode()).hexdigest()
    return digest[:16]


def log_event(**fields) -> None:
    """Append one event to the private log; never raises."""
    d = Path(os.environ.get(STATE_DIR_ENV) or STATE_DIR).expanduser()
    record = {"v": 2, "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **fields}
    write_private(d / "events.jsonl", json.dumps(record) + "\n", append=True)
