#!/usr/bin/env python3
"""Approve and squash green PRs from a trusted Woodpecker cron (dry-run by default)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPOSITORY = "mashirou1234/yesod-auth"
CHECK_CONTEXT = "ci/woodpecker/pr/woodpecker"
BASE_BRANCHES = {"main", "master"}


class APIError(RuntimeError):
    def __init__(self, status: int):
        # Never print response bodies, request headers or tokens.
        super().__init__(f"GitHub API returned HTTP {status}")
        self.status = status


class GitHub:
    def __init__(self, token: str):
        self.token = token

    def request(self, method: str, path: str, payload=None):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "yesod-auth-woodpecker",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = Request("https://api.github.com" + path, data, headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            raise APIError(exc.code) from None
        except URLError:
            raise RuntimeError("GitHub API connection failed") from None

    def pages(self, path: str, key: str | None = None):
        separator = "&" if "?" in path else "?"
        page = 1
        while True:
            response = self.request("GET", f"{path}{separator}per_page=100&page={page}")
            items = response[key] if key else response
            yield from items
            if len(items) < 100:
                return
            page += 1


def eligible(pr: dict, bot: str | None) -> bool:
    return (
        pr.get("state") == "open"
        and pr.get("draft") is False
        and pr.get("base", {}).get("repo", {}).get("full_name") == REPOSITORY
        and pr.get("base", {}).get("ref") in BASE_BRANCHES
        and pr.get("user", {}).get("login") != bot
        and bool(re.fullmatch(r"[0-9a-f]{40}", pr.get("head", {}).get("sha", "")))
    )


def checks_green(api: GitHub, sha: str) -> bool:
    root = f"/repos/{REPOSITORY}/commits/{sha}"
    status = api.request("GET", root + "/status")
    if status.get("state") != "success" or not any(
        item.get("context") == CHECK_CONTEXT and item.get("state") == "success"
        for item in status.get("statuses", [])
    ):
        return False
    return all(
        check.get("status") == "completed"
        and check.get("conclusion") in {"success", "neutral", "skipped"}
        for check in api.pages(root + "/check-runs", key="check_runs")
    )


def has_approval(api: GitHub, root: str, bot: str, sha: str) -> bool:
    reviews = [
        review
        for review in api.pages(root + "/reviews")
        if review.get("user", {}).get("login") == bot and review.get("state") != "COMMENTED"
    ]
    latest = max(reviews, key=lambda review: review["id"], default={})
    return latest.get("state") == "APPROVED" and latest.get("commit_id") == sha


def process_pr(api: GitHub, number: int, bot: str | None, apply: bool) -> str:
    root = f"/repos/{REPOSITORY}/pulls/{number}"
    pr = api.request("GET", root)
    if not eligible(pr, bot):
        return "skip: closed, draft, unsupported base or authored by the bot"
    sha = pr["head"]["sha"]
    if not checks_green(api, sha):
        return "wait: current head checks are not successful"
    if not apply:
        return "dry-run: eligible for approval; merge requires GitHub branch rules to pass"

    # Recheck after reading statuses; approval is explicitly attached to the tested SHA.
    current = api.request("GET", root)
    if not eligible(current, bot) or current["head"]["sha"] != sha:
        return "wait: PR changed before approval"
    if not has_approval(api, root, bot, sha):
        api.request("POST", root + "/reviews", {"event": "APPROVE", "commit_id": sha})

    current = api.request("GET", root)
    if not eligible(current, bot) or current["head"]["sha"] != sha:
        return "wait: PR changed after approval"
    # Includes required reviews, required checks, conflicts and branch rules.
    # GitHub may need time to recalculate this; the next cron will retry.
    if current.get("mergeable") is not True or current.get("mergeable_state") != "clean":
        return "wait: GitHub merge requirements are not satisfied"
    if not checks_green(api, sha):
        return "wait: checks changed after approval"
    try:
        result = api.request("PUT", root + "/merge", {"merge_method": "squash", "sha": sha})
    except APIError as exc:
        if exc.status in {405, 409}:
            return "wait: GitHub rejected merge (PR or requirements changed)"
        raise
    if result.get("merged") is not True:
        raise RuntimeError("GitHub did not confirm the merge")
    return "merged tested head with squash"


def validate_apply_environment(env: dict) -> None:
    if (
        env.get("CI_PIPELINE_EVENT") != "cron"
        or env.get("CI_COMMIT_BRANCH") not in BASE_BRANCHES
        or env.get("CI_REPO") != REPOSITORY
    ):
        raise RuntimeError("--apply requires a trusted main/master Woodpecker cron")
    if not env.get("PR_AUTOMATION_TOKEN"):
        raise RuntimeError("Configure the cron-only pr_automation_token secret in Woodpecker")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Enable approval and squash writes")
    parser.add_argument("--pull-request", type=int, help="Inspect only this PR (default: all open)")
    args = parser.parse_args()
    if args.pull_request is not None and args.pull_request < 1:
        parser.error("--pull-request must be positive")
    try:
        if args.apply:
            validate_apply_environment(os.environ)
        api = GitHub(os.environ.get("PR_AUTOMATION_TOKEN", ""))
        # A dedicated bot-user PAT is supported; do not use the PR author's token.
        bot = api.request("GET", "/user")["login"] if api.token else None
        numbers = (
            [args.pull_request]
            if args.pull_request
            else [pr["number"] for pr in api.pages(f"/repos/{REPOSITORY}/pulls?state=open")]
        )
        errors = False
        for number in numbers:
            try:
                print(f"PR #{number}: {process_pr(api, number, bot, args.apply)}", flush=True)
            except (RuntimeError, KeyError, ValueError, TypeError) as exc:
                # Keep API errors concise; malformed responses must never authorize writes.
                message = str(exc) if isinstance(exc, RuntimeError) else "unexpected API response"
                print(f"PR #{number}: {message}", file=sys.stderr)
                errors = True
        return int(errors)
    except (RuntimeError, KeyError, ValueError, TypeError) as exc:
        message = str(exc) if isinstance(exc, RuntimeError) else "unexpected API response"
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
