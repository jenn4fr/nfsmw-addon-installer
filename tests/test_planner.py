import tempfile
import unittest
from pathlib import Path

from nfsmw_installer.planner import build_install_plan


class PlannerTests(unittest.TestCase):
    def make_package(self, root: Path):
        addon = root / "Addon"
        (addon / "REBEL").mkdir(parents=True)
        (addon / "SetupFiles").mkdir()
        (addon / "REBEL" / "GEOMETRY.BIN").write_bytes(b"geometry")
        (addon / "REBEL" / "TEXTURES.BIN").write_bytes(b"textures")
        (addon / "SetupFiles" / "rebel_install.nfsms").write_text("# test\n", encoding="utf-8")
        (addon / "Install.nfsms").write_text(
            "folder_create CARS\\REBEL\n"
            "file_copy REBEL\\GEOMETRY.BIN CARS\\REBEL\\GEOMETRY.BIN\n"
            "file_copy REBEL\\TEXTURES.BIN CARS\\REBEL\\TEXTURES.BIN\n"
            "script SetupFiles\\rebel_install.nfsms\n", encoding="utf-8")

    def test_plan_extracts_copy_and_script_operations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_package(root)
            plan = build_install_plan(root)
            copies = [op for op in plan["operations"] if op["operation"] == "file_copy"]
            scripts = [op for op in plan["operations"] if op["operation"] == "script"]
            self.assertEqual(len(copies), 2)
            self.assertTrue(all(op["source_exists"] for op in copies))
            self.assertEqual(len(scripts), 1)
            self.assertFalse(plan["writes_performed"])

    def test_detects_existing_destination_as_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "package"
            game = Path(temp) / "game"
            root.mkdir()
            game.mkdir()
            self.make_package(root)
            destination = game / "CARS" / "REBEL" / "GEOMETRY.BIN"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"existing")
            plan = build_install_plan(root, game)
            self.assertEqual(plan["summary"]["conflict_count"], 1)
            self.assertEqual(plan["operations"][1]["status"], "conflict")

    def test_maps_modloader_payload_into_per_mod_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "1970 AMC Rebel The Machine"
            game = Path(temp) / "game"
            root.mkdir()
            game.mkdir()
            self.make_package(root)

            payload = root / "Modloader" / "ADDONS"
            (payload / "CARS_REPLACE" / "PUNTO").mkdir(parents=True)
            (payload / "CARS_REPLACE" / "PUNTO" / "GEOMETRY.BIN").write_bytes(b"geometry")
            (payload / "FRONTEND" / "MANUFACTURERS").mkdir(parents=True)
            (payload / "FRONTEND" / "MANUFACTURERS" / "75-REBEL.BIN").write_bytes(b"logo")

            plan = build_install_plan(root, game)
            mapped = [op for op in plan["operations"] if op.get("mechanism") == "modloader"]

            self.assertEqual(len(mapped), 2)
            destinations = {op["destination"].replace("\\\\", "/") for op in mapped}
            self.assertIn(
                "modloader/1970_AMC_Rebel_The_Machine/CARS/PUNTO/GEOMETRY.BIN",
                destinations,
            )
            self.assertIn(
                "modloader/1970_AMC_Rebel_The_Machine/FRONTEND/MANUFACTURERS/75-REBEL.BIN",
                destinations,
            )
            self.assertTrue(all(op["status"] == "ready" for op in mapped))
            self.assertFalse(plan["writes_performed"])

    def test_rejects_package_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_package(root)
            script = root / "Addon" / "Install.nfsms"
            script.write_text("file_copy ..\\outside.bin CARS\\OUTSIDE.BIN\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_install_plan(root)


if __name__ == "__main__":
    unittest.main()
