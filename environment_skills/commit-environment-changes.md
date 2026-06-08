---
name: commit-environment-changes
type: knowledge
version: 1.1.0
agent: CodeActAgent
triggers:
- commit environment changes
- commit blueprint changes to the repo
- export environment changes to git
- push my blueprint changes
- sync the environment to its repository
---

# Commit Environment Changes

## Purpose

Blueprint objects edited in a running B1 environment live only in the database
until they are exported to JSON files and committed to the environment's linked
source repository. This skill automates that round trip from inside the
OpenHands sandbox:

1. Resolve the linked repository from the running environment.
2. Make sure the linked repository is checked out in the sandbox workspace
   (reuse an existing checkout; only clone when there is none).
3. Export the modified blueprint objects from the environment.
4. Commit and push them on a new branch for review.

The sandbox workspace **may already contain a checkout** of the linked
repository (with its own `.git` directory and `origin` remote). When it does,
reuse it — fetch and reset to the default branch instead of deleting `.git` and
re-cloning. Only clone when no checkout exists (Step 2).

It relies on two `B1_Blueprint` MCP tools:

| Tool | Role in this skill |
| --- | --- |
| `mcp__B1_Blueprint__get_application_info` | Fetch the linked repository identifier |
| `mcp__B1_Blueprint__export_modified_zip` | Export modified blueprint objects as a zip |

> ⚠️ Do **not** use `mcp__B1_Blueprint__export_objects` in this workflow. It
> writes to the appserver and clears the "modified" flag, breaking
> `export_modified_zip`. See the warning in Step 3.

## Prerequisites

- The `gh` CLI must see a GitHub token. The sandbox may inject it under any of a
  few names, so resolve it explicitly **before any `gh` or `git` call** (see
  Step 0). No interactive login is needed — and none is available inside the
  sandbox.
- Git identity is configured (`git config user.name` / `user.email`); set it if
  it is missing.
- The `B1_Blueprint` MCP server is reachable (the environment must be running).

## Workflow

### Step 0 — Resolve GitHub auth

`gh` reads `GH_TOKEN`/`GITHUB_TOKEN`, but the sandbox sometimes injects the
secret under a dash-cased name (`github-token`) that the shell cannot expand as
`$github-token`. Resolve all three sources in one shot, then stop guessing:

```bash
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-$(printenv github-token 2>/dev/null)}}"
test -n "$GH_TOKEN" || { echo "No GitHub token found in GH_TOKEN, GITHUB_TOKEN, or github-token"; exit 1; }
```

If `$GH_TOKEN` is empty after this, the secret was not injected — report that to
the user and stop. **Do not** spend calls probing with `gh auth status`,
`env | grep`, or `printenv ... | wc -c`; the one command above is the complete
check.

### Step 1 — Resolve the linked repository

Call `mcp__B1_Blueprint__get_application_info`. Read the `repository` field — a
GitHub `owner/repo` identifier, e.g. `build-one-labs/vanguard`.

If `repository` is null or missing, stop and tell the user the environment has
no linked repository (the `REPOSITORY` env var is unset on the appserver).

### Step 2 — Ensure the linked repository is checked out

The workspace may or may not already contain the checkout. Detect which case
you are in and reuse an existing checkout — **never `rm -rf .git` and re-clone**
just to get a clean state.

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  # Existing checkout — make sure it points at the linked repo, then refresh it.
  git remote set-url origin "https://github.com/<repository>.git"
  DEFAULT_BRANCH="$(git remote show origin | sed -n 's/.*HEAD branch: //p')"
  git fetch origin "$DEFAULT_BRANCH"
  # -f discards any stale local changes; -B resets the branch onto origin.
  git checkout -f -B "$DEFAULT_BRANCH" "origin/$DEFAULT_BRANCH"
else
  # No checkout — clone into the working directory.
  gh repo clone <repository> .
fi
```

If the working directory is non-empty but is *not* a git checkout, clone into a
subdirectory instead (`gh repo clone <repository> <repo-name>`) and run the
remaining steps from inside it.

Either way you end up on the repository's default branch with `origin`
configured against the linked repo — the new branch in Step 5 is created from
it. `gh`/`git` authenticate with the `$GH_TOKEN` resolved in Step 0.

### Step 3 — Export modified blueprint objects

> ⚠️ **Use `export_modified_zip` — never `export_objects` first.**
> There is a second, similarly named tool, `mcp__B1_Blueprint__export_objects`
> (`action: "export"`), that looks like the right thing to reach for. It is
> **not.** It writes JSON to the *appserver's* filesystem and **clears the
> "modified" flag** on the objects as a side effect. If you call it before
> `export_modified_zip`, the export then returns `fileCount: 0` because the
> modified state is already gone — and you cannot get it back without re-editing
> the objects. `export_modified_zip` is read-only with respect to that flag, so
> reach for it directly and **do not call `export_objects` anywhere in this
> workflow.**

Call `mcp__B1_Blueprint__export_modified_zip`. The result has two parts:

- A text block with `{ success, fileCount, sizeBytes, filename }`.
- A resource block (`mimeType: application/zip`) whose blob is the base64 zip.

**The base64 blob in the tool result is the only source of the exported files
that exists inside the sandbox.** The tool also writes the JSON into the
appserver's `APP_DATA_FOLDER`, but that folder lives on the *appserver*
container, not the sandbox filesystem — so do **not** `find / -name
'modified-objects-*.zip'` or otherwise search disk for it (you will find
nothing), and do **not** reconstruct the JSON by hand via `get_object` or SQL.
Decode the blob from the tool result directly.

Handle the outcome:

- If `fileCount` is `0`, stop — there are no modified objects to commit.
- Otherwise, write the base64 blob to a file and unzip it into `src/data/`:

```bash
# Save the base64 blob from the tool's resource block to export.b64, then:
base64 -d export.b64 > export.zip
unzip -o export.zip -d src/data/
rm export.b64 export.zip
```

The zip entries are paths like `repository/<module>/<object>.json` (relative to
the appserver's `APP_DATA_FOLDER`). In the repository these files live under
`src/data/`, so they extract to `src/data/repository/<module>/<object>.json`.

### Step 4 — Derive a branch name from the changes

Inspect what changed and name the branch after it:

```bash
git status --porcelain src/data/
```

Derive a short kebab-case branch name from the changed files under
`src/data/repository/`:

- Single object changed → `blueprint/update-<object-name>`
- Multiple objects in one module → `blueprint/update-<module>-<count>-objects`
- Multiple modules → `blueprint/update-environment-<count>-objects`

Lowercase everything; keep the name under ~50 characters.

### Step 5 — Commit and push on a new branch

```bash
git checkout -b <branch-name>
git add src/data/
git commit -m "$(cat <<'EOF'
Export modified blueprint objects from environment

<one line per changed object, e.g. "- Update CustomerScreen (Samples)">

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin <branch-name>
```

`git push` and `gh pr create` use the `origin` remote and the `$GH_TOKEN`
resolved in Step 0, so no further auth setup is needed.

### Step 6 — Offer to open the pull request (optional, one path only)

Opening a PR is **optional** — do not create one automatically. After the push,
report the branch name and its compare URL, then **ask the user whether they
want a pull request**. Only run `gh pr create` if they say yes.

When they do, base the PR title and body on the actual committed changes — the
same per-object summary used in the commit message — not a generic title:

```bash
# Title: name the object(s) changed, e.g. "Update SalesTourScreen (Samples)"
# for a single object, or "Update 3 blueprint objects (Samples)" for several.
# Body: one bullet per changed object, derived from `git status`/`git log` over
# the files under src/data/repository/.
gh pr create \
  --title "<title from the committed changes>" \
  --body "$(cat <<'EOF'
<one bullet per changed object, e.g. "- Update SalesTourScreen (Samples)">
EOF
)"
```

Use **exactly one** PR-creation path — `gh pr create`. Do not also create a PR
through any other path (e.g. an MCP PR tool); creating it twice opens duplicate
PRs and wastes calls. Report the resulting PR URL to the user.

## Notes

- Never commit straight to the default branch — always use the new branch from
  Step 4 so changes go through review.
- **`export_objects` is a trap, not a step.** It is a separate MCP tool that
  writes to the appserver and clears the "modified" flag; calling it before
  `export_modified_zip` makes the export return `fileCount: 0` and the change is
  effectively lost. Never call it in this workflow — use `export_modified_zip`.
- `export_modified_zip` also writes the JSON files into the running appserver's
  local `APP_DATA_FOLDER`, but that folder is on the appserver container, not the
  sandbox. The base64 blob in the tool result is the only sandbox-side source —
  never search the sandbox filesystem for the exported zip/JSON.
- Only `src/data/` is staged (`git add src/data/`), so unrelated workspace files
  are never committed.
- If `gh`/`git` fails on authentication, the GitHub token resolved in Step 0 is
  missing or expired — report this to the user. There is no interactive login
  inside the sandbox, so do not attempt `gh auth login`.

## Key References

| Purpose | Location |
| --- | --- |
| `get_application_info` tool | `src/swat-app-server-ts/src/mcp/tools/application.tools.ts` |
| `export_modified_zip` tool | `src/swat-app-server-ts/src/mcp/tools/repository.tools.ts` (`exportModifiedBlueprintObjectsAsZip`) |
| `export_objects` tool (avoid — clears modified flag) | `src/swat-app-server-ts/src/mcp/tools/repository.tools.ts` |
| Tool registration | `src/swat-app-server-ts/src/mcp/mcp-server.factory.ts` |
| Linked repository env var | `REPOSITORY` (set per environment in `.build/deploy/*.deployment.config.json`) |
