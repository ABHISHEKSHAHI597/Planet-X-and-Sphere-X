#!/usr/bin/env bash
# Publish ParallaX Lite (frontend/dist-lite, built per docs/deploy.md §8) to the `gh-pages` branch of `origin`.
# GitHub Pages serves that branch at https://<owner>.github.io/<repository>/ (enable it once under
# Settings → Pages → "Deploy from a branch" → gh-pages / root, if the repository does not do so on its own).
#
#   scripts/publish_lite.sh            commit the copy on gh-pages and push it
#   scripts/publish_lite.sh --dry-run  commit locally, do not push
#
# The branch holds only the built copy (no history of main, no source). Each run replaces its content.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/frontend/dist-lite"
[ -f "$SRC/index.html" ] && [ -f "$SRC/lite/index.json" ] || {
  echo "no complete copy in $SRC: run docs/deploy.md §8 steps 1–3 first" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'git -C "$ROOT" worktree remove --force "$WORK" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

cd "$ROOT"
if git ls-remote --exit-code --heads origin gh-pages >/dev/null 2>&1; then
  git fetch -q origin gh-pages
  git worktree add -q -B gh-pages "$WORK" origin/gh-pages
else
  git branch -D gh-pages >/dev/null 2>&1 || true   # a local branch left by an earlier --dry-run
  git worktree add -q --detach "$WORK"
  git -C "$WORK" checkout -q --orphan gh-pages
fi
git -C "$WORK" rm -rqf --ignore-unmatch . >/dev/null
cp -a "$SRC"/. "$WORK"/
touch "$WORK/.nojekyll"                # serve files as they are (no Jekyll processing)
git -C "$WORK" add -A
if git -C "$WORK" diff --cached --quiet; then echo "gh-pages already up to date"; exit 0; fi
git -C "$WORK" commit -q -m "ParallaX Lite: frozen copy of the pinned demo views ($(date -u +%Y-%m-%d))"
if [ "${1:-}" = "--dry-run" ]; then echo "committed on local gh-pages; not pushed (dry run)"; exit 0; fi
git -C "$WORK" push -q origin gh-pages
echo "pushed gh-pages: https://$(git remote get-url origin | sed -E 's#.*[:/]([^/]+)/([^/.]+)(\.git)?$#\L\1\E.github.io/\2#')/"
