# pubcheck.base

What every part of the check shares: the time budget, private files, the settings and the event log.

**The budget.** Every lookup (`gh`, `acquaint`, `git`) runs inside one
[`Budget`](#pubcheck.base.Budget), so a check decides within its deadline instead of being killed by its
caller. Out of time, a lookup answers `None` (unknown), and the caller decides what
unknown means: presumed public for visibility, unavailable for the registry.

**Settings.** One mapping, read from `~/.config/pubcheck/config.toml`
(`$PUBCHECK_CONFIG` names another file), with environment variables over it, and keyword
arguments over both at each call site. The keys are in [`DFLT_SETTINGS`](#pubcheck.base.DFLT_SETTINGS).

**The log.** `~/.local/state/public-text-guard/events.jsonl` (mode 0600,
`$PUBLIC_TEXT_GUARD_STATE_DIR`), one JSON object per decision worth keeping: never the
text and never the matched terms, only the categories, the repo, the writer, a short hash
of the text (so two events about the same text can be paired), an error’s type, and an
override’s reason as its author wrote it.

```pycon
>>> b = Budget(0)
>>> b.run(["true"]) is None  # no time left: no subprocess at all
True
```

### Module Attributes

| [`FINISH_RESERVE`](#pubcheck.base.FINISH_RESERVE)   | Seconds a check keeps for itself after its lookups (deciding, logging, exiting), so a caller that kills it at its deadline gets an answer instead.   |
|-------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`SLOW_CHECK`](#pubcheck.base.SLOW_CHECK)       | A check slower than this (seconds) logs what its lookups cost, to find the slow one.                                                                 |
| [`REAP_SECONDS`](#pubcheck.base.REAP_SECONDS)     | Seconds to reap a killed lookup (its pipes may be held by a process outside its group).                                                              |
| [`DFLT_SETTINGS`](#pubcheck.base.DFLT_SETTINGS)    | The settings and their defaults.                                                                                                                     |
| [`SETTINGS_ENV`](#pubcheck.base.SETTINGS_ENV)     | config only).                                                                                                                                        |

### Functions

| [`cache_dir`](#pubcheck.base.cache_dir)()                             | Where the vocabulary and the companion answers are cached.                                                                    |
|------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| [`log_event`](#pubcheck.base.log_event)(\*\*fields)                   | Append one event to the private log; never raises.                                                                            |
| [`settings`](#pubcheck.base.settings)([overrides])                   | [`DFLT_SETTINGS`](#pubcheck.base.DFLT_SETTINGS), then the config file, then the environment, then `overrides`. |
| [`text_hash`](#pubcheck.base.text_hash)(\*texts)                      | A short hash of the texts: pairs log events and desk items without copying the text.                                          |
| [`write_private`](#pubcheck.base.write_private)(path, text, \*[, append]) | Write `text` to `path` with mode 0600, in a 0700 folder (atomically unless appending).                                        |

### Classes

| [`Budget`](#pubcheck.base.Budget)([seconds])   | One deadline shared by every lookup of a check, and a record of what each lookup cost.   |
|----------------------------------------------------------------------|------------------------------------------------------------------------------------------|

### *class* pubcheck.base.Budget(seconds=12.0)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One deadline shared by every lookup of a check, and a record of what each lookup cost.

`lookups` holds `(label, seconds, outcome)` per lookup, `outcome` one of `ok`,
`failed`, `timeout` or `skipped` (no time left); the label is the program’s
name only, never an argument (one could carry a path or the text).

#### left(cap=8.0)

Seconds a lookup may take: `cap`, or what is left of the budget when less.

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

#### report()

The lookups as JSON-ready rows `[label, seconds, outcome]`.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]

#### run(argv, , cap=8.0, stdin=None, env=None, cwd=None)

`subprocess.run` within the budget; `None` when out of time or on failure.

The lookup runs in its own process group, and running out of time kills the whole
group: a program that started helpers of its own leaves none behind, still holding
the machine, once the check has given up on it. The trade-off: a caller that kills the check
itself (rather than giving it a `--deadline`) does not reach a lookup in flight,
which runs on until its own end.

#### *property* strained *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

Whether a lookup ran out of time or was skipped for lack of it.

### pubcheck.base.DFLT_SETTINGS *= {'budget_seconds': 12.0, 'credential_scanner': None, 'hold_label': 'escalate', 'hold_repo': None, 'private_issues': None, 'private_owner': None, 'private_patterns': ()}*

The settings and their defaults. Everything that names the operator’s own repos or
folders is unset by default and lives in their config file, never in this code:

- `hold_repo`: the private repo where a held post becomes a desk item (unset: no item
  is filed; it must be private, or nothing is copied there);
- `hold_label`: the label the desk reads;
- `private_owner`: the account whose `<owner>/_<name>` repos are private companions
  (a reference to one is private, and a flag points at the target’s companion);
- `private_issues`: the private repo for context that has no companion;
- `private_patterns`: more regexes for private references (working folders, the
  layout of the operator’s machines), on top of this machine’s home folder;
- `credential_scanner`: an external secret scanner to run beside the built-in
  credential patterns, e.g. `betterleaks` (unset: none is run). See
  [`pubcheck.detectors.scanner_credential()`](pubcheck.detectors.html.md#pubcheck.detectors.scanner_credential).

### pubcheck.base.FINISH_RESERVE *= 1.0*

Seconds a check keeps for itself after its lookups (deciding, logging, exiting), so a
caller that kills it at its deadline gets an answer instead.

### pubcheck.base.REAP_SECONDS *= 0.2*

Seconds to reap a killed lookup (its pipes may be held by a process outside its group).

### pubcheck.base.SETTINGS_ENV *= {'budget_seconds': 'PUBCHECK_BUDGET_SECONDS', 'credential_scanner': 'PUBCHECK_CREDENTIAL_SCANNER', 'hold_label': 'PUBCHECK_HOLD_LABEL', 'hold_repo': 'PUBCHECK_HOLD_REPO', 'private_issues': 'PUBCHECK_PRIVATE_ISSUES', 'private_owner': 'PUBCHECK_PRIVATE_OWNER'}*

config only).

* **Type:**
  The environment variable that overrides each setting (`private_patterns`

### pubcheck.base.SLOW_CHECK *= 3.0*

A check slower than this (seconds) logs what its lookups cost, to find the slow one.

### pubcheck.base.cache_dir()

Where the vocabulary and the companion answers are cached.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### pubcheck.base.log_event(\*\*fields)

Append one event to the private log; never raises.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### pubcheck.base.settings(overrides=None)

[`DFLT_SETTINGS`](#pubcheck.base.DFLT_SETTINGS), then the config file, then the environment, then `overrides`.

```pycon
>>> settings({"hold_repo": "me/_desk"})["hold_repo"]
'me/_desk'
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### pubcheck.base.text_hash(\*texts)

A short hash of the texts: pairs log events and desk items without copying the text.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### pubcheck.base.write_private(path, text, , append=False)

Write `text` to `path` with mode 0600, in a 0700 folder (atomically unless appending).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)
