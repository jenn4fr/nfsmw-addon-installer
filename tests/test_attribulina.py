import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nfsmw_installer.attribulina import AttribulinaAdapter


class AttribulinaAdapterTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.exe = self.root / "attribcli.exe"
        self.db = self.root / "FE_ATTRIB.BIN"
        self.script = self.root / "install.nfsms"
        self.amod = self.root / "install.amod"

        for path in (self.exe, self.db, self.script):
            path.write_text("test", encoding="utf-8")

        self.adapter = AttribulinaAdapter(self.exe, self.db)

    def tearDown(self):
        self.temp.cleanup()

    @patch("nfsmw_installer.attribulina.subprocess.run")
    def test_convert_uses_vlted_and_output(self, mock_run):
        def fake_run(command, **kwargs):
            output = Path(command[command.index("-o") + 1])
            output.write_text("AMOD test", encoding="utf-8")
            return SimpleNamespace(
                returncode=0, stdout="converted", stderr=""
            )

        mock_run.side_effect = fake_run
        result = self.adapter.convert(self.script, self.amod)

        self.assertTrue(result.ok)
        self.assertIn("--vlted", result.command)
        self.assertTrue(self.amod.is_file())

    @patch("nfsmw_installer.attribulina.subprocess.run")
    def test_check_uses_script_and_database(self, mock_run):
        self.amod.write_text("AMOD test", encoding="utf-8")
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout="reads fine", stderr=""
        )

        result = self.adapter.check(self.amod)

        self.assertTrue(result.ok)
        self.assertEqual(result.command[1], "check")
        self.assertEqual(result.command[2], str(self.amod))
        self.assertEqual(result.command[3], str(self.db))

    @patch("nfsmw_installer.attribulina.subprocess.run")
    def test_dry_run_has_safety_flags(self, mock_run):
        self.amod.write_text("AMOD test", encoding="utf-8")
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout="would write", stderr=""
        )

        result = self.adapter.dry_run(self.amod)

        self.assertTrue(result.ok)
        self.assertIn("--dry-run", result.command)
        self.assertIn("--strict", result.command)
        self.assertIn("--no-backup", result.command)
        self.assertIn("--no-mod-list", result.command)

    @patch("nfsmw_installer.attribulina.subprocess.run")
    def test_nonzero_exit_is_failure(self, mock_run):
        self.amod.write_text("AMOD test", encoding="utf-8")
        mock_run.return_value = SimpleNamespace(
            returncode=1, stdout="", stderr="validation failed"
        )

        result = self.adapter.check(self.amod)

        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, 1)
        self.assertIn("validation failed", result.stderr)

    def test_convert_refuses_to_overwrite_by_default(self):
        self.amod.write_text("existing", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            self.adapter.convert(self.script, self.amod)

    def test_missing_database_is_rejected(self):
        adapter = AttribulinaAdapter(self.exe, self.root / "missing.bin")
        self.amod.write_text("AMOD test", encoding="utf-8")

        with self.assertRaises(FileNotFoundError):
            adapter.check(self.amod)


if __name__ == "__main__":
    unittest.main()
