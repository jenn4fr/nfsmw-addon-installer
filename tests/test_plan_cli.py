from __future__ import annotations



import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch



from nfsmw_installer.cli import main



class PlanInstallCliTests(unittest.TestCase):
    def test_plan_install_writes_json_and_returns_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "pkg"
            addon = package / "Addon"
            (addon / "REBEL").mkdir(parents=True)
            (addon / "Install.nfsms").write_text(
                "folder_create CARS\\REBEL\n"
                "file_copy REBEL\\GEOMETRY.BIN CARS\\REBEL\\GEOMETRY.BIN\n"
                "script SetupFiles\\install.nfsms\n",
                encoding="utf-8",
            )
            (addon / "REBEL" / "GEOMETRY.BIN").write_bytes(b"geometry")
            output = root / "plan.json"
            code = main(["plan-install", str(package), "-o", str(output)])
            self.assertEqual(code, 0)
            plan = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(plan["mode"], "read-only-plan")
            self.assertFalse(plan["writes_performed"])
            self.assertEqual(len(plan["operations"]), 3)



    def test_plan_install_game_root_detects_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "pkg"
            addon = package / "Addon"
            (addon / "REBEL").mkdir(parents=True)
            (addon / "Install.nfsms").write_text(
                "file_copy REBEL\\GEOMETRY.BIN CARS\\REBEL\\GEOMETRY.BIN\n",
                encoding="utf-8",
            )
            (addon / "REBEL" / "GEOMETRY.BIN").write_bytes(b"geometry")
            game = root / "game"
            (game / "CARS" / "REBEL").mkdir(parents=True)
            (game / "CARS" / "REBEL" / "GEOMETRY.BIN").write_bytes(b"old")
            output = root / "plan.json"
            code = main([
                "plan-install", str(package), "--game-root", str(game),
                "-o", str(output),
            ])
            self.assertEqual(code, 0)
            plan = json.loads(output.read_text(encoding="utf-8"))
            copies = [op for op in plan["operations"] if op["operation"] == "file_copy"]
            self.assertEqual(copies[0]["status"], "conflict")
            self.assertEqual(len(plan["conflicts"]), 1)
            self.assertTrue(plan["backup_rollback_plan"])



if __name__ == "__main__":
    unittest.main()
