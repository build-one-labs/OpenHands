---
name: commit-environment-changes
type: knowledge
version: 1.0.0
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
2. Clone that repository into the sandbox workspace.
3. Export the modified blueprint objects from the environment.
4. Commit and push them on a new branch for review.

When connected to an environment there is **no repository checked out in the
workspace** — the linked repository must always be cloned (Step 2).

It relies on two `B1_Blueprint` MCP tools:

| Tool | Role in this skill |
| --- | --- |
| `mcp__B1_Blueprint__get_application_info` | Fetch the linked repository identifier |
| `mcp__B1_Blueprint__export_modified_zip` | Export modified blueprint objects as a zip |

## Prerequisites

- The `gh` CLI is authenticated via the sandbox-injected token
  (`GH_TOKEN` / `GITHUB_TOKEN`). No interactive login is needed — and none is
  available inside the sandbox.
- Git identity is configured (`git config user.name` / `user.email`); set it if
  it is missing.
- The `B1_Blueprint` MCP server is reachable (the environment must be running).

## Workflow

### Step 1 — Resolve the linked repository

Call `mcp__B1_Blueprint__get_application_info`. Read the `repository` field — a
GitHub `owner/repo` identifier, e.g. `build-one-labs/vanguard`.

If `repository` is null or missing, stop and tell the user the environment has
no linked repository (the `REPOSITORY` env var is unset on the appserver).

### Step 2 — Clone the linked repository into the workspace

The workspace has no checkout, so clone the linked repository into the
conversation's working directory:

```bash
# Run from the workspace working directory (empty — no repo is checked out).
gh repo clone <repository> .
```

If the working directory is not empty, clone into a subdirectory instead
(`gh repo clone <repository> <repo-name>`) and run the remaining steps from
inside it.

`gh repo clone` configures the `origin` remote with the sandbox's `gh`
credentials. A fresh clone is checked out on the repository's default branch —
the new branch in Step 5 is created from it.

### Step 3 — Export modified blueprint objects

Call `mcp__B1_Blueprint__export_modified_zip`. The result has two parts:

- A text block with `{ success, fileCount, sizeBytes, filename }`.
- A resource block (`mimeType: application/zip`) whose blob is the base64 zip.

Handle the outcome:

- If `fileCount` is `0`, stop — there are no modified objects to commit.
- Otherwise, write the base64 blob to a file and unzip it into `src/data/`:

```bash
# Save the base64 blob returned by the tool to export.b64, then:
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

`git push` and `gh pr create` use the `origin` remote that `gh repo clone`
configured, so no further auth setup is needed.

After the push, report the branch name and its compare URL to the user, and
offer to open a pull request with `gh pr create`.

## Notes

- Never commit straight to the default branch — always use the new branch from
  Step 4 so changes go through review.
- `export_modified_zip` also writes the JSON files into the running appserver's
  local `APP_DATA_FOLDER` as a side effect; that is expected and harmless.
- Only `src/data/` is staged (`git add src/data/`), so unrelated workspace files
  are never committed.
- If `gh repo clone` or `git push` fails on authentication, the sandbox's `gh`
  token is missing or expired — report this to the user. There is no
  interactive login inside the sandbox, so do not attempt `gh auth login`.

## Key References

| Purpose | Location |
| --- | --- |
| `get_application_info` tool | `src/swat-app-server-ts/src/mcp/tools/application.tools.ts` |
| `export_modified_zip` tool | `src/swat-app-server-ts/src/mcp/tools/repository.tools.ts` (`exportModifiedBlueprintObjectsAsZip`) |
| Tool registration | `src/swat-app-server-ts/src/mcp/mcp-server.factory.ts` |
| Linked repository env var | `REPOSITORY` (set per environment in `.build/deploy/*.deployment.config.json`) |
