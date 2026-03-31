#!/usr/bin/env python3
"""Normalize Bench-80 queue issue titles by removing slot prefixes."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

BENCH_TITLE_RE = re.compile(r"^\s*\[Bench-80\]\[(\d+)\]\s*(.+?)\s*$")


def run_gh(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["gh", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("gh CLI is required", file=sys.stderr)
        raise SystemExit(1)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or str(exc), file=sys.stderr)
        raise SystemExit(exc.returncode)
    return completed.stdout


def detect_repo(explicit: str) -> str:
    if explicit:
        return explicit
    return run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()


def fetch_open_queue_issues(repo: str) -> list[dict]:
    output = run_gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,title,labels,createdAt",
        ]
    )
    issues = json.loads(output)
    queue = []
    for issue in issues:
        labels = {label["name"] for label in issue.get("labels", [])}
        if "codex:queue" in labels:
            queue.append(issue)
    queue.sort(key=lambda i: i.get("createdAt", ""))
    return queue


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize Bench-80 queue issue titles.")
    parser.add_argument("--repo", default="", help="owner/repo")
    parser.add_argument("--apply", action="store_true", help="Apply title updates")
    args = parser.parse_args()

    repo = detect_repo(args.repo.strip())
    if not repo:
        print("Repository not found. pass --repo owner/repo.", file=sys.stderr)
        return 1

    queue_issues = fetch_open_queue_issues(repo)
    candidates = []
    for issue in queue_issues:
        match = BENCH_TITLE_RE.match(issue["title"])
        if not match:
            continue
        new_title = match.group(2).strip()
        if not new_title:
            continue
        if new_title == issue["title"].strip():
            continue
        candidates.append((issue["number"], issue["title"], new_title))

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] repo={repo} candidates={len(candidates)}")

    updated = 0
    for number, old_title, new_title in candidates:
        print(f"#{number}: {old_title} -> {new_title}")
        if not args.apply:
            continue
        run_gh(["issue", "edit", str(number), "--repo", repo, "--title", new_title])
        updated += 1

    if args.apply:
        print(f"updated={updated}")
    else:
        print("updated=0 (dry-run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
