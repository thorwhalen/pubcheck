# pubcheck

pubcheck: one publication check for every writer.

Is this text fit for the repository it is about to be published to? A private target
passes; a public (or unknown) one is scanned for names from the owner’s acquaint records,
the owner’s own matters (“the operator stated”), private references, session links,
credentials, and, for an unattended writer, @mentions. An unattended writer fails closed.

```pycon
>>> from pubcheck import check
>>> check("Fixed the parser.", repo="octo/app", public=True, log=False).decision
'pass'
```

Three ways in, one check: [`check()`](#pubcheck.check) in Python, `public-text-guard check` on the
command line (exit 0 pass, 1 flag, 2 unavailable), and
`pubcheck.correspond:before_send` as correspond’s `before_send`.

### Functions

| [`check`](#pubcheck.check)(text, \*[, repo, title, more, ...])          | Check `text` (and `title`) for publication to `repo`; never raises.                 |
|-----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| [`file_hold`](#pubcheck.file_hold)(verdict, \*, target, text[, title, ...]) | File (or find) the desk item for a held post; `{"filed": bool, "url"?, "reason"?}`. |
| [`findings`](#pubcheck.findings)(texts, ctx, \*[, detectors])              | `[(category, term)]`, each once, found by `detectors` in any of `texts`.            |

### Classes

| [`Verdict`](#pubcheck.Verdict)(decision[, repo, visibility, ...])   | What the check decided about one text, and why; `to_json()` never holds the text.   |
|-----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|

### *class* pubcheck.Verdict(decision, repo='', visibility='unknown', findings=list(), registry='skipped', unattended=False, destination=None, reason=None, text_hash='')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What the check decided about one text, and why; [`to_json()`](#pubcheck.Verdict.to_json) never holds the text.

#### *property* categories *: [list](https://docs.python.org/3/builtins/stdtypes.html#list)[[str](https://docs.python.org/3/builtins/stdtypes.html#str)]*

The categories found, sorted, each once.

#### *property* exit_code *: [int](https://docs.python.org/3/builtins/functions.html#int)*

0 pass (or override), 1 flag, 2 unavailable.

#### explain()

For the author: what was found, by category, and where the private context goes.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

#### *property* held *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

Whether a writer must hold the text instead of publishing it.

#### to_json(, terms=False)

The verdict as JSON: categories, never the text; the matched terms only on request.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### pubcheck.check(text, , repo=None, title=None, more=(), unattended=False, public=None, surface='text', override=None, repo_dir=None, detectors=None, budget=None, writer='pubcheck', log=True, context=None)

Check `text` (and `title`) for publication to `repo`; never raises.

`more` are other strings published with it (labels, a category, file names, the
people a post notifies as `@login`). `public` skips the visibility lookup when the
caller already knows (correspond’s audience). `repo_dir` names a checkout whose
`origin` is the target when `repo` is not given. `detectors` defaults by
`unattended`. `override` is ignored when `unattended`: nobody is there to give a
reason. `context` adds fields to the log event (a session id, a tool name), never text.

An unattended check asks GitHub for the visibility instead of trusting a cached
“private” (a repo made public today must not pass unscanned), and holds a text longer
than `MAX_TEXT` as unavailable.

* **Return type:**
  [`Verdict`](pubcheck.core.html.md#pubcheck.core.Verdict)

### pubcheck.file_hold(verdict, , target, text, title=None, more=(), config=None, budget=None)

File (or find) the desk item for a held post; `{"filed": bool, "url"?, "reason"?}`. Never raises.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### pubcheck.findings(texts, ctx, \*, detectors=(<function registry>, <function owner_relation>, <function private_ref>, <function session_link>, <function credential>))

`[(category, term)]`, each once, found by `detectors` in any of `texts`.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]

### Modules

| [`base`](pubcheck.base.html.md#module-pubcheck.base)             | What every part of the check shares: the time budget, private files, the settings and the event log.   |
|----------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| [`core`](pubcheck.core.html.md#module-pubcheck.core)             | The check: is this text fit for the repo it is about to be published to?                               |
| [`correspond`](pubcheck.correspond.html.md#module-pubcheck.correspond) | correspond's `before_send` check: the publication check for every write correspond makes.              |
| [`detectors`](pubcheck.detectors.html.md#module-pubcheck.detectors)   | The detectors: what in a text a public reader may not see.                                             |
| [`hold`](pubcheck.hold.html.md#module-pubcheck.hold)             | A held post becomes a desk item: an issue in a private repo, labelled for the desk.                    |
| [`sources`](pubcheck.sources.html.md#module-pubcheck.sources)       | What the check looks up: a repo's visibility, the acquaint registry, private companions.               |
