"""PR automation contracts; all GitHub calls are mocked, including writes."""

import copy
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "woodpecker_pr_automation.py"
spec = importlib.util.spec_from_file_location("pr_automation", SCRIPT)
automation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(automation)

SHA = "a" * 40
PR = {
    "state": "open",
    "draft": False,
    "base": {"ref": "main", "repo": {"full_name": automation.REPOSITORY}},
    "head": {"sha": SHA},
    "user": {"login": "developer"},
    "mergeable": True,
    "mergeable_state": "clean",
}
GREEN = {
    "state": "success",
    "statuses": [{"context": automation.CHECK_CONTEXT, "state": "success"}],
}


class FakeGitHub:
    def __init__(self):
        self.prs = [copy.deepcopy(PR) for _ in range(3)]
        self.statuses = [copy.deepcopy(GREEN) for _ in range(2)]
        self.checks = []
        self.reviews = []
        self.writes = []
        self.merge_error = None

    def request(self, method, path, payload=None):
        if method == "GET":
            if path.endswith("/status"):
                return self.statuses.pop(0)
            return self.prs.pop(0)
        self.writes.append((method, path, payload))
        if method == "PUT":
            if self.merge_error:
                raise self.merge_error
            return {"merged": True}
        return {}

    def pages(self, path, key=None):
        return iter(self.reviews if path.endswith("/reviews") else self.checks)


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeGitHub()

    def run_pr(self, apply=True):
        return automation.process_pr(self.api, 838, "automation-bot", apply)

    def test_green_pr_approves_and_merges_exact_tested_commit(self):
        self.assertIn("merged", self.run_pr())
        approve, merge = self.api.writes
        self.assertEqual(approve[2], {"event": "APPROVE", "commit_id": SHA})
        self.assertEqual(merge[2], {"merge_method": "squash", "sha": SHA})

    def test_dry_run_never_writes(self):
        self.assertIn("dry-run", self.run_pr(apply=False))
        self.assertEqual(self.api.writes, [])

    def test_ineligible_prs_never_write(self):
        cases = [
            ("draft", True),
            ("state", "closed"),
            ("user", {"login": "automation-bot"}),
            ("head", {"sha": "invalid"}),
            ("base", {"ref": "release", "repo": {"full_name": automation.REPOSITORY}}),
            ("base", {"ref": "main", "repo": {"full_name": "someone/else"}}),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.api = FakeGitHub()
                self.api.prs[0][key] = value
                self.assertIn("skip", self.run_pr())
                self.assertEqual(self.api.writes, [])

    def test_master_base_is_supported(self):
        for pr in self.api.prs:
            pr["base"]["ref"] = "master"
        self.assertIn("merged", self.run_pr())

    def test_missing_pending_or_failed_woodpecker_blocks_writes(self):
        cases = [
            {"state": "success", "statuses": []},
            {"state": "pending", "statuses": GREEN["statuses"]},
            {"state": "failure", "statuses": GREEN["statuses"]},
            {"state": "success", "statuses": [{"context": "another-ci", "state": "success"}]},
            {
                "state": "success",
                "statuses": [{"context": automation.CHECK_CONTEXT, "state": "pending"}],
            },
        ]
        for status in cases:
            with self.subTest(status=status):
                self.api = FakeGitHub()
                self.api.statuses[0] = status
                self.assertIn("wait", self.run_pr())
                self.assertEqual(self.api.writes, [])

    def test_check_runs_must_finish_successfully(self):
        for status, conclusion in [
            ("queued", None),
            ("in_progress", None),
            ("completed", "failure"),
            ("completed", "cancelled"),
        ]:
            with self.subTest(status=status, conclusion=conclusion):
                self.api = FakeGitHub()
                self.api.checks = [{"status": status, "conclusion": conclusion}]
                self.assertIn("wait", self.run_pr())
                self.assertEqual(self.api.writes, [])

    def test_sha_changed_before_approval_blocks_all_writes(self):
        self.api.prs[1]["head"]["sha"] = "b" * 40
        self.assertIn("before approval", self.run_pr())
        self.assertEqual(self.api.writes, [])

    def test_draft_change_before_approval_blocks_all_writes(self):
        self.api.prs[1]["draft"] = True
        self.assertIn("before approval", self.run_pr())
        self.assertEqual(self.api.writes, [])

    def test_sha_changed_after_approval_blocks_merge(self):
        self.api.prs[2]["head"]["sha"] = "b" * 40
        self.assertIn("after approval", self.run_pr())
        self.assertEqual([write[0] for write in self.api.writes], ["POST"])

    def test_changed_checks_after_approval_block_merge(self):
        self.api.statuses[1]["state"] = "failure"
        self.assertIn("checks changed", self.run_pr())
        self.assertEqual([write[0] for write in self.api.writes], ["POST"])

    def test_blocked_conflicting_or_unknown_merge_state_waits(self):
        for state in ["blocked", "dirty", "unknown", None]:
            with self.subTest(state=state):
                self.api = FakeGitHub()
                self.api.prs[2]["mergeable_state"] = state
                self.assertIn("requirements", self.run_pr())
                self.assertEqual([write[0] for write in self.api.writes], ["POST"])

    def test_current_approval_is_not_duplicated(self):
        self.api.reviews = [
            {"id": 1, "user": {"login": "automation-bot"}, "state": "APPROVED", "commit_id": SHA},
            {"id": 2, "user": {"login": "automation-bot"}, "state": "COMMENTED", "commit_id": SHA},
        ]
        self.assertIn("merged", self.run_pr())
        self.assertEqual([write[0] for write in self.api.writes], ["PUT"])

    def test_old_or_dismissed_approval_is_replaced(self):
        for state, sha in [("APPROVED", "b" * 40), ("DISMISSED", SHA)]:
            with self.subTest(state=state, sha=sha):
                self.api = FakeGitHub()
                self.api.reviews = [
                    {"id": 1, "user": {"login": "automation-bot"}, "state": state, "commit_id": sha}
                ]
                self.assertIn("merged", self.run_pr())
                self.assertEqual([write[0] for write in self.api.writes], ["POST", "PUT"])

    def test_merge_race_is_deferred(self):
        for code in [405, 409]:
            with self.subTest(code=code):
                self.api = FakeGitHub()
                self.api.merge_error = automation.APIError(code)
                self.assertIn("rejected merge", self.run_pr())

    def test_permission_failure_is_not_reported_as_success(self):
        self.api.merge_error = automation.APIError(403)
        with self.assertRaises(automation.APIError):
            self.run_pr()

    def test_api_pagination_includes_later_check_runs(self):
        api = automation.GitHub("")
        first = [{"status": "completed", "conclusion": "success"}] * 100
        with patch.object(
            api,
            "request",
            side_effect=[GREEN, {"check_runs": first}, {"check_runs": [{"status": "queued"}]}],
        ) as request:
            self.assertFalse(automation.checks_green(api, SHA))
            self.assertTrue(request.call_args.args[1].endswith("page=2"))

    def test_apply_requires_cron_protected_branch_repo_and_secret(self):
        valid = {
            "CI_PIPELINE_EVENT": "cron",
            "CI_COMMIT_BRANCH": "main",
            "CI_REPO": automation.REPOSITORY,
            "PR_AUTOMATION_TOKEN": "test-only",
        }
        automation.validate_apply_environment(valid)
        for key, value in [
            ("CI_PIPELINE_EVENT", "pull_request"),
            ("CI_PIPELINE_EVENT", "push"),
            ("CI_COMMIT_BRANCH", "feature"),
            ("CI_REPO", "other/repo"),
            ("PR_AUTOMATION_TOKEN", ""),
        ]:
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                automation.validate_apply_environment({**valid, key: value})

    def test_apply_guard_runs_before_network(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sys.argv", [str(SCRIPT), "--apply"]),
            patch.object(automation, "urlopen") as urlopen,
        ):
            self.assertEqual(automation.main(), 1)
            urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
