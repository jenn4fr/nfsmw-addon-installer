from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.audit_game_installation import audit_game_installation, sha256_file


class GameInstallationAuditTests(unittest.TestCase):
    def make_game(self, root: Path) -> None:
        for rel in ("CARS", "GLOBAL", "FRONTEND", "scripts", "modloader",
                    "scripts/UnlimiterData"):
            (root / rel).mkdir(parents=True, exist_ok=True)
        for rel in ("speed.exe", "GLOBAL/ATTRIBUTES.BIN", "GLOBAL/FE_ATTRIB.BIN"):
            (root / rel).write_bytes((rel + "-fixture").encode("ascii"))
        (root / "modloader/NFSMW-ML.log").write_text(
            "NFSMW-ML started\n2 mod folder(s)\n", encoding="utf-8"
        )

    def test_complete_fixture_is_audited_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_game(root)
            before = {p.relative_to(root).as_posix(): sha256_file(p)
                      for p in root.rglob("*") if p.is_file()}
            report = audit_game_installation(root)
            after = {p.relative_to(root).as_posix(): sha256_file(p)
                     for p in root.rglob("*") if p.is_file()}
            self.assertEqual(report["status"], "audited")
            self.assertTrue(report["read_only"])
            self.assertFalse(report["writes_performed"])
            self.assertEqual(before, after)
            self.assertTrue(report["modloader_log"]["exists"])

    def test_missing_required_database_marks_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_game(root)
            (root / "GLOBAL/FE_ATTRIB.BIN").unlink()
            report = audit_game_installation(root)
            self.assertEqual(report["status"], "incomplete")
            self.assertIn("GLOBAL/FE_ATTRIB.BIN",
                          [x["path"] for x in report["required_files"] if not x["exists"]])

    def test_missing_game_root_raises(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "not-a-game"
            with self.assertRaises(FileNotFoundError):
                audit_game_installation(missing)

    def test_bad_timeout_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_game(root)
            with self.assertRaises(ValueError):
                audit_game_installation(root, timeout=0)

    def test_attribulina_is_not_invoked_if_executable_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_game(root)
            report = audit_game_installation(
                root, attribulina=root / "missing-attribcli.exe"
            )
            self.assertEqual(report["attribulina_info"]["ATTRIBUTES.BIN"]["status"], "not-run")
            self.assertFalse(report["writes_performed"])


if __name__ == "__main__":
    unittest.main()
