#!/usr/bin/env python3
"""Small GitHub helpers with gh-first and REST fallback behavior."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from typing import Any


def _token() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def gh_available() -> bool:
    return shutil.which("gh") is not None


def run_gh(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["gh", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("gh CLI is not installed; using GitHub REST fallback when possible.", file=sys.stderr)
        raise
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or str(exc), file=sys.stderr)
        raise SystemExit(exc.returncode)
    return completed.stdout


def api_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    token = _token()
    if not token:
        print(
            "gh CLI is unavailable and GH_TOKEN/GITHUB_TOKEN is not set; GitHub API fallback cannot authenticate.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "yesod-auth-codex-automation",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"https://api.github.com{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"GitHub API request failed: HTTP {exc.code} {detail}", file=sys.stderr)
        raise SystemExit(1)
    except urllib.error.URLError as exc:
        print(f"GitHub API request failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if not body:
        return None
    return json.loads(body)


def detect_repo(explicit: str = "") -> str:
    candidates = [
        explicit.strip(),
        os.environ.get("GH_REPO", "").strip(),
        os.environ.get("GITHUB_REPOSITORY", "").strip(),
    ]
    for candidate in candidates:
        if candidate:
            return candidate

    remote = _git_remote_repo()
    if remote:
        return remote

    if gh_available():
        return run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()

    print(
        "Repository not found. Pass --repo owner/repo, set GH_REPO/GITHUB_REPOSITORY, or configure git remote origin.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _git_remote_repo() -> str:
    try:
        completed = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""

    url = completed.stdout.strip()
    patterns = [
        r"github\.com[:/](?P<repo>[^/]+/[^/.]+)(?:\.git)?$",
        r"https://github\.com/(?P<repo>[^/]+/[^/.]+)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group("repo")
    return ""


def list_open_issues(repo: str) -> list[dict[str, Any]]:
    if gh_available():
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
                "number,title,url,createdAt,labels",
            ]
        )
        return json.loads(output)

    issues: list[dict[str, Any]] = []
    encoded_repo = urllib.parse.quote(repo, safe="/")
    page = 1
    while True:
        response = api_json(
            "GET",
            f"/repos/{encoded_repo}/issues?state=open&per_page=100&page={page}",
        )
        page_items = [item for item in response if "pull_request" not in item]
        issues.extend(
            {
                "number": item["number"],
                "title": item["title"],
                "url": item["html_url"],
                "createdAt": item["created_at"],
                "labels": [{"name": label["name"]} for label in item.get("labels", [])],
            }
            for item in page_items
        )
        if len(response) < 100:
            break
        page += 1
    return issues


def edit_issue_title(repo: str, number: int, title: str) -> None:
    if gh_available():
        run_gh(["issue", "edit", str(number), "--repo", repo, "--title", title])
        return

    encoded_repo = urllib.parse.quote(repo, safe="/")
    api_json("PATCH", f"/repos/{encoded_repo}/issues/{number}", {"title": title})
