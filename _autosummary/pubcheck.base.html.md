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

| [`DFLT_SETTINGS`](#pubcheck.base.DFLT_SETTINGS)   | The settings and their defaults.   |
|------------------------------------------------------------------|------------------------------------|
| [`SETTINGS_ENV`](#pubcheck.base.SETTINGS_ENV)    | config only).                      |

### Functions

| [`cache_dir`](#pubcheck.base.cache_dir)()                             | Where the vocabulary and the companion answers are cached.                                                                    |
|------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| [`log_event`](#pubcheck.base.log_event)(\*\*fields)                   | Append one event to the private log; never raises.                                                                            |
| [`settings`](#pubcheck.base.settings)([overrides])                   | [`DFLT_SETTINGS`](#pubcheck.base.DFLT_SETTINGS), then the config file, then the environment, then `overrides`. |
| [`text_hash`](#pubcheck.base.text_hash)(\*texts)                      | A short hash of the texts: pairs log events and desk items without copying the text.                                          |
| [`write_private`](#pubcheck.base.write_private)(path, text, \*[, append]) | Write `text` to `path` with mode 0600, in a 0700 folder (atomically unless appending).                                        |

### Classes

| [`Budget`](#pubcheck.base.Budget)([seconds])   | One deadline shared by every lookup of a check.   |
|----------------------------------------------------------------------|---------------------------------------------------|

### *class* pubcheck.base.Budget(seconds=12.0)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One deadline shared by every lookup of a check.

#### left(cap=8.0)

Seconds a lookup may take: `cap`, or what is left of the budget when less.

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

#### run(argv, , cap=8.0, stdin=None)

`subprocess.run` within the budget; `None` when out of time or on failure.

### pubcheck.base.DFLT_SETTINGS *= {'budget_seconds': 12.0, 'hold_label': 'escalate', 'hold_repo': None, 'private_issues': None, 'private_owner': None, 'private_patterns': ()}*

The settings and their defaults. Everything that names the operator’s own repos or
folders is unset by default and lives in their config file, never in this code:

- `hold_repo`: the private repo where a held post becomes a desk item (unset: no item
  is filed; it must be private, or nothing is copied there);
- `hold_label`: the label the desk reads;
- `private_owner`: the account whose `<owner>/_<name>` repos are private companions
  (a reference to one is private, and a flag points at the target’s companion);
- `private_issues`: the private repo for context that has no companion;
- `private_patterns`: more regexes for private references (working folders, the
  layout of the operator’s machines), on top of this machine’s home folder.

### pubcheck.base.SETTINGS_ENV *= {'budget_seconds': 'PUBCHECK_BUDGET_SECONDS', 'hold_label': 'PUBCHECK_HOLD_LABEL', 'hold_repo': 'PUBCHECK_HOLD_REPO', 'private_issues': 'PUBCHECK_PRIVATE_ISSUES', 'private_owner': 'PUBCHECK_PRIVATE_OWNER'}*

config only).

* **Type:**
  The environment variable that overrides each setting (`private_patterns`

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
