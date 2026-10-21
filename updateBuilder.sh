#!/bin/sh
# Refresh ./builder from GitHub - plain files, in place, with no git binding inside it.
#
# This file SHIPS IN the library and is meant to be copied OUT of it, next to the project you
# are building (`cp builder/updateBuilder.sh .`), exactly like prmpt.txt: it replaces ./builder,
# so it can never live inside the folder it replaces.
#
# ⛔ THE COPY YOU HAVE IS NEVER DELETED BEFORE THE NEW ONE IS IN HAND. The download, the unpack
# and the checks all happen in a staging folder beside this script; the swap at the end is two
# renames on one filesystem, and the previous copy is only removed once the new one stands in
# its place. A 404, a dead network, a renamed repo or an archive that does not look like the
# library aborts with ./builder untouched - which matters, because losing mrjun.py mid-build
# leaves nothing to validate, pack or import with. It is the same reason the library's own
# one-liner downloads to a FILE and not through a pipe.
#
#   ./updateBuilder.sh              # refresh from main
#   ./updateBuilder.sh v2           # or any branch, tag or commit sha
#   BUILDER_REPO=owner/repo ./updateBuilder.sh
set -e
SELF=$(basename "$0")
cd "$(dirname "$0")"

REPO="${BUILDER_REPO:-nct-platform/builder}"
REF="${1:-main}"
STAGE=".builder-update.$$"

# ⛔ Run it from the PROJECT folder, never from inside the library: here `./builder` is the thing
# being replaced, and a copy still sitting in the library would refresh `builder/builder`.
if [ -f tools/mrjun.py ] && [ -f system_prompt.txt ]; then
  echo "updateBuilder: this copy is INSIDE the library - copy it out first," >&2
  echo "               'cp builder/updateBuilder.sh .', and run it from the project folder" >&2
  exit 1
fi

trap 'rm -rf "$STAGE"' EXIT HUP INT TERM
rm -rf "$STAGE"
mkdir "$STAGE"

printf '→ %s @ %s\n' "$REPO" "$REF"
curl -fsSL "https://github.com/$REPO/archive/$REF.tar.gz" -o "$STAGE/builder.tgz"
printf '  %s bytes\n' "$(wc -c < "$STAGE/builder.tgz" | tr -d ' ')"
tar xzf "$STAGE/builder.tgz" -C "$STAGE"
rm -f "$STAGE/builder.tgz"

# GitHub names the unpacked folder <repo>-<ref> and flattens slashes, so FIND it rather than
# predict it - and refuse anything that is not exactly one folder.
if [ "$(find "$STAGE" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')" != 1 ]; then
  echo "updateBuilder: the archive did not unpack to a single folder - ./builder untouched" >&2
  exit 1
fi
NEW=$(find "$STAGE" -mindepth 1 -maxdepth 1 -type d)

# ⛔ The guard that makes the swap safe: it must BE the library before it may replace one.
for f in tools/mrjun.py README.md GETTING-STARTED.md system_prompt.txt; do
  if [ ! -f "$NEW/$f" ]; then
    echo "updateBuilder: not the builder library ($f missing) - ./builder untouched" >&2
    exit 1
  fi
done
# ⛔ -B, and it is not cosmetic: without it this very check COMPILES the copy it is checking and
# leaves __pycache__/*.pyc inside the library before it is installed - files the archive does not
# have, that embed their own build path, and that then read as "changed" in every later
# comparison. -E keeps the surrounding PYTHON* environment out of the check.
if ! python3 -BE "$NEW/tools/mrjun.py" --help >/dev/null 2>&1; then
  echo "updateBuilder: the downloaded mrjun.py does not run - ./builder untouched" >&2
  exit 1
fi
find "$NEW" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

# No git binding in the folder. A GitHub tarball carries none; a clone, or a change in how the
# library is packaged, would - and a repository inside the project is exactly what the library's
# layout rules out. Its OWN .gitignore and .github stay: they are its content, not a remote.
rm -rf "$NEW/.git" "$NEW/.gitmodules"

[ -e builder ] && mv builder "$STAGE/previous"
if ! mv "$NEW" builder; then
  [ -d "$STAGE/previous" ] && mv "$STAGE/previous" builder
  echo "updateBuilder: could not put the new copy in place - the previous one is back" >&2
  exit 1
fi

# What arrived, read off the copy that is about to be thrown away - the only moment both exist.
printf '✓ builder refreshed - %s files, no .git\n' "$(find builder -type f | wc -l | tr -d ' ')"
if [ -d "$STAGE/previous" ]; then
  diff -rq "$STAGE/previous" builder > "$STAGE/diff" 2>&1 || true
  printf '  changed %s · new %s · dropped %s\n' \
    "$(grep -c '^Files ' "$STAGE/diff" || true)" \
    "$(grep -c "^Only in builder" "$STAGE/diff" || true)" \
    "$(grep -c "^Only in $STAGE/previous" "$STAGE/diff" || true)"
  grep "^Only in builder" "$STAGE/diff" | sed 's|^Only in |  + |' || true
  grep "^Only in $STAGE/previous" "$STAGE/diff" | sed "s|^Only in $STAGE/previous|  - builder|" || true
fi

# The one file a refresh cannot refresh is this one. Say so; never overwrite it silently.
if [ -f builder/updateBuilder.sh ] && [ -f "$SELF" ] && ! cmp -s builder/updateBuilder.sh "$SELF"; then
  printf '  ! this script is older than the library copy - cp builder/updateBuilder.sh %s\n' "$SELF"
fi
