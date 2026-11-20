import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from nfsmw_installer import cli


def result(ok=True, returncode=0):
    return SimpleNamespace(
        ok=ok,
        returncode=returncode,
        stdout="test output",
        stderr="",
        timed_out=False,
    )


class CliPathTests(unittest.TestCase):

    def test_git_bash_drive_path_is_normalized_on_windows(self):
        with (
            patch("nfsmw_installer.cli.os.name", "nt"),
            patch("nfsmw_installer.cli.Path") as mock_path,
        ):
            cli.resolve_path("/d/softwares/NFS-hack/test.nfsms")

        mock_path.assert_called_once_with(
            "D:/softwares/NFS-hack/test.nfsms"
        )

    def test_native_windows_path_is_not_rewritten(self):
        native = r"D:\softwares\NFS-hack\test.nfsms"

        with patch("nfsmw_installer.cli.os.name", "nt"):
            with patch("nfsmw_installer.cli.Path") as mock_path:
                cli.resolve_path(native)

        mock_path.assert_called_once_with(native)


class ValidateDbCliTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.script = self.root / "install.nfsms"
        self.database = self.root / "FE_ATTRIB.BIN"
        self.executable = self.root / "attribcli.exe"
        self.output = self.root / "install.amod"

        args = [
            "validate-db",
            str(self.script),
            "--database", str(self.database),
            "--attribulina", str(self.executable),
            "--output", str(self.output),
        ]
        self.argv = args

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, mock_adapter):
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.main(self.argv)
        return code, output.getvalue()

    @patch("nfsmw_installer.cli.AttribulinaAdapter")
    def test_success_runs_all_stages_in_order(self, mock_adapter_class):
        adapter = mock_adapter_class.return_value
        adapter.convert.return_value = result()
        adapter.check.return_value = result()
        adapter.dry_run.return_value = result()

        code, output = self.run_cli(mock_adapter_class)

        self.assertEqual(code, 0)
        self.assertEqual(
            adapter.method_calls,
            [
                call.convert(self.script.resolve(), self.output),
                call.check(self.output),
                call.dry_run(self.output),
            ],
        )
        self.assertIn("VALIDATION COMPLETE", output)
        self.assertIn("Actual database installation: NOT PERFORMED", output)

    @patch("nfsmw_installer.cli.AttribulinaAdapter")
    def test_conversion_failure_stops_workflow(self, mock_adapter_class):
        adapter = mock_adapter_class.return_value
        adapter.convert.return_value = result(False, 1)

        code, output = self.run_cli(mock_adapter_class)

        self.assertEqual(code, 2)
        adapter.check.assert_not_called()
        adapter.dry_run.assert_not_called()
        self.assertIn("conversion failed", output)

    @patch("nfsmw_installer.cli.AttribulinaAdapter")
    def test_database_check_failure_stops_before_dry_run(
        self, mock_adapter_class
    ):
        adapter = mock_adapter_class.return_value
        adapter.convert.return_value = result()
        adapter.check.return_value = result(False, 1)

        code, output = self.run_cli(mock_adapter_class)

        self.assertEqual(code, 2)
        adapter.convert.assert_called_once()
        adapter.check.assert_called_once_with(self.output)
        adapter.dry_run.assert_not_called()
        self.assertIn("database validation failed", output)

    @patch("nfsmw_installer.cli.AttribulinaAdapter")
    def test_dry_run_failure_returns_error(self, mock_adapter_class):
        adapter = mock_adapter_class.return_value
        adapter.convert.return_value = result()
        adapter.check.return_value = result()
        adapter.dry_run.return_value = result(False, 1)

        code, output = self.run_cli(mock_adapter_class)

        self.assertEqual(code, 2)
        adapter.dry_run.assert_called_once_with(self.output)
        self.assertNotIn("VALIDATION COMPLETE", output)
        self.assertIn("strict dry-run failed", output)

    @patch("nfsmw_installer.cli.AttribulinaAdapter")
    def test_timeout_argument_is_passed_to_adapter(
        self, mock_adapter_class
    ):
        self.argv.extend(["--timeout", "45"])
        adapter = mock_adapter_class.return_value
        adapter.convert.return_value = result()
        adapter.check.return_value = result()
        adapter.dry_run.return_value = result()

        self.run_cli(mock_adapter_class)

        self.assertEqual(
            mock_adapter_class.call_args.kwargs["timeout"], 45
        )


if __name__ == "__main__":
    unittest.main()
