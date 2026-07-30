---
name: commit-environment-changes
type: knowledge
version: 2.0.0
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
OpenHands sandbox in **three turns**:

1. Export the modified objects and resolve the linked repository (two parallel
   tool calls).
2. Run ONE bash script that downloads the export over HTTP, refreshes a shallow
   checkout, commits, pushes, and (when requested) opens the PR.
3. Report the result.

Do not add steps. The deterministic work (auth, checkout, unzip, commit, push,
PR) is all inside the script — your only decisions are the branch name and the
commit/PR text.

It relies on two `B1_Blueprint` MCP tools:

| Tool | Role in this skill |
| --- | --- |
| `mcp__B1_Blueprint__get_application_info` | Fetch the linked repository identifier |
| `mcp__B1_Blueprint__export_modified_zip` | Export modified objects + stage a downloadable zip |

> ⚠️ Do **not** use `mcp__B1_Blueprint__export_objects` in this workflow — it
> clears the "modified" state without staging anything downloadable.

## Prerequisites

- The sandbox injects `github-token` (GitHub) and `buildone-token` (B1
  environment) secrets. Both are dash-cased env names, so read them with
  `printenv`, not `$github-token`. No interactive login exists in the sandbox —
  never run `gh auth login`.
- The `B1_Blueprint` MCP server is reachable (the environment must be running).

## Step 1 — Export and resolve the repository (one turn, two parallel calls)

Call **in parallel**:

- `mcp__B1_Blueprint__get_application_info` → read `repository`
  (`owner/repo`, e.g. `build-one-labs/vanguard`). If null/missing, stop and
  tell the user the environment has no linked repository.
- `mcp__B1_Blueprint__export_modified_zip` → the text payload contains
  `fileCount`, `files` (the exported `repository/<module>/<object>.json`
  entries), `filename`, and download coordinates (`downloadUrl` or
  `downloadPath` + `curlExample`).

Interpret the export result:

- `fileCount > 0` → proceed; use `files` to write the branch name, commit
  message, and PR text.
- `fileCount: 0` **with** `latestStagedZip` → a previous export already staged
  the changes (the zip is still downloadable). Proceed with that filename.
- `fileCount: 0` without `latestStagedZip` → nothing to commit. Stop and tell
  the user.

If the result has only `downloadPath` (no absolute `downloadUrl`), prefix it
with the environment URL you are connected to.

> The zip is staged **on the appserver** and served over HTTP. Never search the
> sandbox filesystem for it (`find /` finds nothing), never rebuild the JSON
> via `query_blueprint` SQL or `get_object` — if anything is lost, just curl
> the download endpoint again; it is non-destructive and repeatable.

## Step 2 — One script: download, commit, push, PR (one turn)

Fill ONLY the variables at the top, then run the whole block as a single
terminal command. Derive `BRANCH` from the changed objects
(`blueprint/update-<object-name>` for one object,
`blueprint/update-<module>-<count>-objects` for several in one module,
`blueprint/update-environment-<count>-objects` across modules; lowercase,
under ~50 chars). Set `PR_TITLE` empty to stop after the push (when the user
did not ask for a PR); set `DRAFT='--draft'` when they asked for a draft PR.

```bash
set -euo pipefail
# ---- fill these ----
REPO='<owner/repo from get_application_info>'
DOWNLOAD_URL='<downloadUrl from export_modified_zip>'
ZIP_NAME='<filename or latestStagedZip from export_modified_zip>'
BRANCH='blueprint/<derived-branch-name>'
COMMIT_MSG='Export modified blueprint objects from environment

<one line per changed object, e.g. "- Update customerScreen (Samples)">'
PR_TITLE='<title from the changes, or empty to skip the PR>'
PR_BODY='<one bullet per changed object>'
DRAFT=''   # set to --draft for a draft PR
# ---- verbatim from here ----
export GIT_TERMINAL_PROMPT=0
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-$(printenv github-token 2>/dev/null)}}"
test -n "$GH_TOKEN" || { echo "No GitHub token in GH_TOKEN, GITHUB_TOKEN, or github-token"; exit 1; }
B1_TOKEN="$(printenv buildone-token 2>/dev/null)"
test -n "$B1_TOKEN" || { echo "No buildone-token secret found"; exit 1; }
cd /workspace/project

curl -fS --max-time 60 -X POST "$DOWNLOAD_URL" \
  -H "Authorization: Bearer $B1_TOKEN" -H "Content-Type: application/json" \
  -d "{\"filename\":\"$ZIP_NAME\"}" -o /tmp/modified-objects.zip
unzip -l /tmp/modified-objects.zip

git init -q .
git config user.name  "Build.One Agent"
git config user.email "agents@build.one"
git remote remove origin 2>/dev/null || true
git remote add origin "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git"
BASE="$(gh repo view "$REPO" --json defaultBranchRef -q .defaultBranchRef.name)"
git sparse-checkout set --cone src/data
git fetch -q --depth=1 --filter=blob:none origin "$BASE"
git checkout -qf -B "$BRANCH" "origin/$BASE"

unzip -oq /tmp/modified-objects.zip -d src/data
git add src/data
git commit -q -m "$COMMIT_MSG"
git push -q -u origin "$BRANCH"
if [ -n "$PR_TITLE" ]; then
  gh pr create --repo "$REPO" --base "$BASE" --head "$BRANCH" \
    --title "$PR_TITLE" --body "$PR_BODY" $DRAFT
else
  echo "Pushed. Compare: https://github.com/${REPO}/compare/${BASE}...${BRANCH}"
fi
```

Why the script looks like this — do not "improve" these away:

- `GIT_TERMINAL_PROMPT=0` + the token embedded in the remote URL: git does
  **not** read `GH_TOKEN` (only `gh` does). Without both, `git fetch` prompts
  `Username for 'https://github.com':` and hangs until the terminal timeout.
- `gh repo view` for the default branch — never `git remote show origin`,
  which makes an interactive-prone network call.
- Sparse cone `src/data` + `--depth=1 --filter=blob:none`: the commit only
  touches `src/data/repository/**`, so nothing else needs to be materialized.
  If the fetch fails oddly, retry once without `--filter=blob:none`.
- `git init` is idempotent: it adopts the empty repo the sandbox starts with
  and is a no-op on an existing checkout. Never `rm -rf .git` or re-clone.

If the download returns 404, the staging was cleared (e.g. appserver
restart): re-run `export_modified_zip`; if that also reports nothing, fall
back to POST `<environment-url>/service/swat/server-actions/repository/modified-objects/download-local-files-as-zip`
(same auth header, no body) — on standalone stacks it streams the previously
exported files.

## Step 3 — Report (one turn)

Report the PR URL printed by `gh pr create` (or the compare URL after a
push-only run), plus the per-object summary from `files`.

## Notes

- Never commit straight to the default branch.
- Use **exactly one** PR-creation path — `gh pr create` inside the script. Do
  not also call an MCP PR tool; that opens duplicate PRs.
- Only `src/data/` is staged, so unrelated workspace files are never committed.
- On auth failure, the relevant secret is missing or expired — report it; do
  not probe with `gh auth status`, `env | grep`, or repeated retries.

## Key References

| Purpose | Location (vanguard) |
| --- | --- |
| `get_application_info` tool | `src/swat-app-server-ts/src/mcp/tools/application.tools.ts` |
| `export_modified_zip` tool (stages the zip) | `src/swat-app-server-ts/src/mcp/tools/repository.tools.ts` |
| `download-staged-zip` endpoint | `src/swat-app-server-ts/src/server-actions/repository/modified-objects.controller.ts` |
| Staging folder | `EXPORT_STAGING_FOLDER` (default `os.tmpdir()/b1-modified-object-zips`) |
