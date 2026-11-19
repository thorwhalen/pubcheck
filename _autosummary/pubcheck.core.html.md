# pubcheck.core

The check: is this text fit for the repo it is about to be published to?

[`check()`](#pubcheck.core.check) is the one entry point every writer calls (the Claude Code hook through the
CLI, correspond’s `before_send`, hatchway through the CLI). It answers a [`Verdict`](#pubcheck.core.Verdict):

- `pass`: a private target (nothing is scanned), or nothing found;
- `flag`: a detector found something; the text must not be published as is;
- `unavailable`: the check could not be made. For an **unattended** writer (nobody
  reads the post before it goes out) that is a missing registry, a lookup out of time, or
  any error; such a writer must hold the text, never post it. An attended writer proceeds
  without the registry (the gap is logged), and only an error makes the check unavailable;
- `override`: found something, but the author gave a reason to publish anyway (the
  hook’s `# public-text-ok: <reason>`); logged with the reason.

An unknown visibility (offline, no `gh`, no such repo, no repo named) is public.

```pycon
>>> v = check("A neutral release note.", repo="o/r", public=True, log=False)
>>> v.decision, v.exit_code
('pass', 0)
>>> v = check("As the owner asked, we fixed it.", repo="o/r", public=True, log=False)
>>> v.decision, v.categories, v.exit_code
('flag', ['owner-relation'], 1)
>>> check("the owner asked", repo="o/r", public=False, log=False).decision
'pass'
```

### Module Attributes

| [`HINTS`](#pubcheck.core.HINTS)   | One line per category, for the author who has to reword.   |
|----------------------------------------------------------|------------------------------------------------------------|

### Functions

| [`check`](#pubcheck.core.check)(text, \*[, repo, title, more, ...])      | Check `text` (and `title`) for publication to `repo`; never raises.                  |
|-------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| [`destination`](#pubcheck.core.destination)(repo, cache, \*, budget[, config]) | Where the private context goes: the repo's private companion, else `private_issues`. |

### Classes

| [`Verdict`](#pubcheck.core.Verdict)(decision[, repo, visibility, ...])   | What the check decided about one text, and why; `to_json()` never holds the text.   |
|-----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|

### pubcheck.core.HINTS *= {'credential': 'carries a credential-shaped string (a token, a key, a password in a URL)', 'mention': '@mentions someone, which notifies them: posting it is messaging them', 'owner-relation': 'relays the owner\\'s own preferences, corrections or relations ("the operator stated", "my agents")', 'private-ref': 'points at a private repo, working folder or local path', 'registry': "names a person or org from the owner's acquaint records that a public reader may not see", 'session-link': 'carries a Claude session link (strip it)'}*

One line per category, for the author who has to reword.

### *class* pubcheck.core.Verdict(decision, repo='', visibility='unknown', findings=list(), registry='skipped', unattended=False, destination=None, reason=None, text_hash='')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What the check decided about one text, and why; [`to_json()`](#pubcheck.core.Verdict.to_json) never holds the text.

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

### pubcheck.core.check(text, , repo=None, title=None, more=(), unattended=False, public=None, surface='text', override=None, repo_dir=None, detectors=None, budget=None, writer='pubcheck', log=True, context=None)

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
  [`Verdict`](#pubcheck.core.Verdict)

### pubcheck.core.destination(repo, cache, , budget, config=None)

Where the private context goes: the repo’s private companion, else `private_issues`.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
