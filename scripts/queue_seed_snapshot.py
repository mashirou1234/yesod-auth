#!/usr/bin/env python3
"""Snapshot open codex:queue inventory for Bench-80 slot health."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from github_fallback import detect_repo, list_open_issues

BENCH_TITLE_RE = re.compile(r"^\s*\[Bench-80\]\[(\d+)\]\s*(.+?)\s*$")


@dataclass
class BenchIssue:
    number: int
    slot: int
    title: str
    url: str


def fetch_open_queue_issues(repo: str) -> list[dict[str, Any]]:
    issues = list_open_issues(repo)
    queue_issues = []
    for issue in issues:
        labels = {label["name"] for label in issue.get("labels", [])}
        if "codex:queue" in labels:
            queue_issues.append(issue)
    queue_issues.sort(key=lambda x: x.get("createdAt", ""))
    return queue_issues


def analyze(issues: list[dict[str, Any]]) -> dict[str, Any]:
    bench_issues: list[BenchIssue] = []
    for issue in issues:
        match = BENCH_TITLE_RE.match(issue["title"])
        if not match:
            continue
        bench_issues.append(
            BenchIssue(
                number=issue["number"],
                slot=int(match.group(1)),
                title=issue["title"],
                url=issue["url"],
            )
        )

    used_slots = sorted({item.slot for item in bench_issues if 1 <= item.slot <= 20})
    unexpected_by_slot: dict[int, list[BenchIssue]] = defaultdict(list)
    duplicates_by_slot: dict[int, list[BenchIssue]] = defaultdict(list)
    grouped: dict[int, list[BenchIssue]] = defaultdict(list)

    for item in bench_issues:
        grouped[item.slot].append(item)
        if item.slot < 1 or item.slot > 20:
            unexpected_by_slot[item.slot].append(item)

    for slot, members in grouped.items():
        if len(members) > 1:
            duplicates_by_slot[slot].extend(members)

    return {
        "queue_count": len(issues),
        "bench_count": len(bench_issues),
        "used_slots": used_slots,
        "unexpected_slots": {
            str(slot): [item.number for item in members]
            for slot, members in sorted(unexpected_by_slot.items())
        },
        "duplicate_slots": {
            str(slot): [item.number for item in members]
            for slot, members in sorted(duplicates_by_slot.items())
        },
    }


def to_markdown(repo: str, summary: dict[str, Any]) -> str:
    lines = [
        f"# Queue Snapshot ({repo})",
        "",
        f"- queue_count: `{summary['queue_count']}`",
        f"- bench_count: `{summary['bench_count']}`",
        f"- used_slots: `{summary['used_slots']}`",
    ]

    unexpected = summary["unexpected_slots"]
    if unexpected:
        rendered = [f"[{slot}] #{' #'.join(str(n) for n in numbers)}" for slot, numbers in unexpected.items()]
        lines.append(f"- unexpected_slots: `{rendered}`")
    else:
        lines.append("- unexpected_slots: `[]`")

    duplicate = summary["duplicate_slots"]
    if duplicate:
        rendered = [f"[{slot}] #{' #'.join(str(n) for n in numbers)}" for slot, numbers in duplicate.items()]
        lines.append(f"- duplicate_slots: `{rendered}`")
    else:
        lines.append("- duplicate_slots: `[]`")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot Bench-80 queue slot health.")
    parser.add_argument("--repo", default="", help="owner/repo. Defaults to current gh repo.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()

    repo = detect_repo(args.repo.strip())
    if not repo:
        print("Repository not found. pass --repo owner/repo.", file=sys.stderr)
        return 1

    summary = analyze(fetch_open_queue_issues(repo))
    if args.format == "markdown":
        print(to_markdown(repo, summary))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
