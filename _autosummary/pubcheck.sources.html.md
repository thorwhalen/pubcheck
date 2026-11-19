# pubcheck.sources

What the check looks up: a repo’s visibility, the acquaint registry, private companions.

**Visibility** comes from a visibility cache shared with other tools on the machine
(`~/.cache/priv/repo_visibility/<sanitized remote>.json`, `$PRIV_VISIBILITY_CACHE_DIR`,
24 h; one JSON file per remote: `remote`, `slug`, `is_private`, `checked_at`). Every
fresh entry is read, whatever its remote spelling. A miss asks `gh repo view` and records
the answer in the same format. Unknown (offline, no `gh`, no such repo) is `None`,
which the check treats as public.

**The registry** is acquaint’s Do-not-identify vocabulary for a public audience
(`acquaint disclosure --audience '{"scope": "public"}' --json`), cached an hour in
`~/.cache/public-text-guard/` (`term` and `entity` only, mode 0600). A stale cache
serves when acquaint cannot be asked. `$PUBLIC_TEXT_GUARD_VOCAB_FILE` names a JSON list
to use instead (tests).

```pycon
>>> parse_slug("git@github.com:octo/app.git")
'octo/app'
>>> terms_for([{"term": "Ada Quill", "entity": "person:a"}, {"term": "AQ", "entity": "person:a"}], "o/r")
['Ada Quill']
```

### Functions

| [`cache_key`](#pubcheck.sources.cache_key)(remote_url)                             | The cache's file name for a remote.                                                                |
|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| [`cached_visibility`](#pubcheck.sources.cached_visibility)(\*[, now, directory])           | `{slug (lowercase): is_private}` from every fresh entry of the shared visibility cache.            |
| [`companion_exists`](#pubcheck.sources.companion_exists)(slug, cache, \*, budget)         | Whether `slug` exists (remembered a day); `None` when it cannot be asked.                          |
| [`gh_repo_view`](#pubcheck.sources.gh_repo_view)(slug, \*, budget)                    | `True` private, `False` public, `"missing"` no such repo, `None` unknown.                          |
| [`lookup_visibility`](#pubcheck.sources.lookup_visibility)(slug, cache, \*, budget[, ...]) | `True` private, `False` public, `None` unknown (does not exist, or offline).                       |
| [`origin`](#pubcheck.sources.origin)(directory, \*, budget)                     | `(slug, remote url)` of `directory`'s `origin`, or `(None, None)`.                                 |
| [`parse_slug`](#pubcheck.sources.parse_slug)(remote_url)                            | `owner/repo` from a github.com remote URL, else `None`.                                            |
| [`terms_for`](#pubcheck.sources.terms_for)(vocab, repo)                            | The terms to scan for when posting to `repo`.                                                      |
| [`vocabulary`](#pubcheck.sources.vocabulary)(\*, budget)                            | `(rows, available)`: acquaint's public-audience vocabulary `[{term, entity}]`, cached `VOCAB_TTL`. |
| [`write_visibility`](#pubcheck.sources.write_visibility)(slug, is_private[, remote])      | Record a verdict in the shared cache's format.                                                     |

### pubcheck.sources.cache_key(remote_url)

The cache’s file name for a remote.

### pubcheck.sources.cached_visibility(, now=None, directory=None)

`{slug (lowercase): is_private}` from every fresh entry of the shared visibility cache.

### pubcheck.sources.companion_exists(slug, cache, , budget)

Whether `slug` exists (remembered a day); `None` when it cannot be asked.

### pubcheck.sources.gh_repo_view(slug, , budget)

`True` private, `False` public, `"missing"` no such repo, `None` unknown.

### pubcheck.sources.lookup_visibility(slug, cache, , budget, remote=None)

`True` private, `False` public, `None` unknown (does not exist, or offline).

### pubcheck.sources.origin(directory, , budget)

`(slug, remote url)` of `directory`’s `origin`, or `(None, None)`.

### pubcheck.sources.parse_slug(remote_url)

`owner/repo` from a github.com remote URL, else `None`.

### pubcheck.sources.terms_for(vocab, repo)

The terms to scan for when posting to `repo`.

An org record that the target’s owner names is the target itself: all its terms go. A
person’s term equal to the owner goes alone. Short terms and common lowercase words go.

### pubcheck.sources.vocabulary(, budget)

`(rows, available)`: acquaint’s public-audience vocabulary `[{term, entity}]`, cached `VOCAB_TTL`.

When acquaint cannot answer, a copy up to `VOCAB_MAX_AGE` old serves. `available`
is False when there is nothing usable: no answer, no copy young enough, or an empty
vocabulary (records not synced to this machine check no name at all).

### pubcheck.sources.write_visibility(slug, is_private, remote=None)

Record a verdict in the shared cache’s format.
