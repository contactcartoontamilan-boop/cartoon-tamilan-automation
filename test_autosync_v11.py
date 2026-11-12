"""V11 deployment contract: no blind deletion or unreviewed social posting."""
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parent


class OracleSyncContractTests(unittest.TestCase):
    def test_old_duplicate_daily_jobs_removed(self):
        self.assertFalse((BASE / ".github/workflows/daily.yml").exists())
        self.assertFalse((BASE / "run_campaign_daily_v9.sh").exists())

    def test_updater_is_fast_forward_and_validation_gated(self):
        body = (BASE / "oracle_autosync_v11.sh").read_text(encoding="utf-8")
        self.assertIn("git worktree add", body)
        self.assertIn("unittest discover", body)
        self.assertIn("git merge --ff-only", body)
        self.assertIn("git status --porcelain", body)
        self.assertNotIn("git clean -fd", body)
        self.assertNotIn("git reset --hard", body)
        self.assertNotIn("git push", body)

    def test_scheduler_does_not_publish_social_posts(self):
        installer = (BASE / "setup_oracle_autosync_v11.sh").read_text(encoding="utf-8")
        self.assertIn("OnUnitActiveSec=5min", installer)
        self.assertIn("flock --shared", installer)
        self.assertIn(" --art-mode cover", installer)
        self.assertNotIn("--publish\n", installer)


if __name__ == "__main__":
    unittest.main()
