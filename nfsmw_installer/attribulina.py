"""Safe subprocess adapter for Attribulina CLI.

This module supports conversion, validation and dry-run only.
It does not provide an actual database installation operation.
"""

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass
class AttribulinaResult:
    operation: str
    command: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class AttribulinaAdapter:
    def __init__(
        self,
        executable: str | Path,
        database: str | Path,
        timeout: int = 180,
    ):
        self.executable = Path(executable)
        self.database = Path(database)
        self.timeout = timeout

    def _validate_environment(self) -> None:
        if not self.executable.is_file():
            raise FileNotFoundError(
                f"Attribulina executable not found: {self.executable}"
            )

        if not self.database.is_file():
            raise FileNotFoundError(
                f"Database file not found: {self.database}"
            )

        if self.timeout <= 0:
            raise ValueError("Timeout must be greater than zero")

    @staticmethod
    def _text(value) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _run(self, operation: str, arguments: list[str]) -> AttribulinaResult:
        self._validate_environment()

        command = (str(self.executable), *arguments)

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                check=False,
            )

            return AttribulinaResult(
                operation=operation,
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
            )

        except subprocess.TimeoutExpired as exc:
            return AttribulinaResult(
                operation=operation,
                command=command,
                returncode=None,
                stdout=self._text(exc.stdout),
                stderr=self._text(exc.stderr),
                timed_out=True,
            )

    def convert(
        self,
        script: str | Path,
        output: str | Path,
        overwrite: bool = False,
    ) -> AttribulinaResult:
        script = Path(script)
        output = Path(output)

        if not script.is_file():
            raise FileNotFoundError(f"NFSMS script not found: {script}")

        if output.exists() and not overwrite:
            raise FileExistsError(f"Output already exists: {output}")

        output.parent.mkdir(parents=True, exist_ok=True)

        result = self._run(
            "convert",
            [
                "convert",
                str(self.database),
                str(script),
                "-o",
                str(output),
                "--vlted",
            ],
        )

        if result.ok and not output.is_file():
            return AttribulinaResult(
                operation="convert",
                command=result.command,
                returncode=1,
                stdout=result.stdout,
                stderr=(
                    result.stderr
                    + "\nAttribulina returned success but did not create "
                    "the requested output file."
                ),
            )

        return result

    def check(self, script: str | Path) -> AttribulinaResult:
        script = Path(script)

        if not script.is_file():
            raise FileNotFoundError(f"AMOD script not found: {script}")

        return self._run(
            "check",
            ["check", str(script), str(self.database)],
        )

    def dry_run(self, script: str | Path) -> AttribulinaResult:
        script = Path(script)

        if not script.is_file():
            raise FileNotFoundError(f"AMOD script not found: {script}")

        return self._run(
            "dry_run",
            [
                "apply",
                str(self.database),
                str(script),
                "--dry-run",
                "--strict",
                "--no-backup",
                "--no-mod-list",
            ],
        )
