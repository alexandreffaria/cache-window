#!/usr/bin/env bash
# Checks every file a branch adds, in any of its commits, for the mechanical
# items of .github/REVIEW_CHECKLIST.md: size, binaries, data and secret files,
# token-shaped strings. A file added and deleted later in the same branch
# still counts, since a merge commit keeps it in history.
#
#   scripts/pr-guard.sh [base] [head]    # defaults: origin/main HEAD
#
# Exits 1 and lists each problem when something fails. CI runs it on every PR
# (.github/workflows/pr-guard.yml).
set -euo pipefail

base=${1:-origin/main}
head=${2:-HEAD}
max_bytes=$((1024 * 1024))

# Binary files these extensions may be; anything else must be text
binary_ok='\.(png|jpe?g|gif|webp|ico|woff2?|ttf|otf)$'
# Credentials, databases, builds (exe, add-on zip) and .blend files
forbidden='(^|/)\.env($|\.)|\.(pem|key|p12|pfx|db|sqlite3?|exe|dll|so|dylib|zip|blend[0-9]*)$|(^|/)id_(rsa|ed25519|ecdsa)$'
# Token shapes worth a hard stop; the reviewer reads for the rest
secrets='-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}|sk-ant-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[abprs]-[A-Za-z0-9-]{10,}'

problems=()
sample_file=$(mktemp)
trap 'rm -f "$sample_file"' EXIT

# Every blob the branch introduces, with its path: "sha size path"
while read -r type sha size path; do
  [ "$type" = blob ] || continue
  [ -n "$path" ] || continue
  if [ "$size" -gt "$max_bytes" ]; then
    problems+=("$path: $((size / 1024)) KB, over the 1 MB limit")
  fi
  if [[ "$path" =~ $forbidden ]]; then
    problems+=("$path: data, credential or binary file; keep it out of git")
    continue
  fi
  if ! [[ "$path" =~ $binary_ok ]]; then
    # Read through a process substitution: head stops early, and the SIGPIPE
    # git gets would otherwise fail a pipeline under pipefail (exit 141)
    head -c 8000 < <(git cat-file blob "$sha") >"$sample_file"
    sample=$(wc -c <"$sample_file")
    text=$(tr -d '\000' <"$sample_file" | wc -c)
    if [ "$sample" -ne "$text" ]; then
      problems+=("$path: binary file; only images and fonts may be binary")
    fi
  fi
done < <(git rev-list --objects "$head" "^$base" |
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)')

# Added lines in any commit of the branch
while IFS= read -r line; do
  problems+=("token-shaped string added, starting ${line:0:6}… (not printed in full)")
done < <(git log -p --format= "$base..$head" | grep -E '^\+' | grep -oE -- "$secrets" || true)

if [ ${#problems[@]} -gt 0 ]; then
  printf 'PR guard found %d problem(s):\n' "${#problems[@]}"
  printf '  - %s\n' "${problems[@]}"
  exit 1
fi
echo "PR guard: no large, binary, data or secret files in $base..$head"
