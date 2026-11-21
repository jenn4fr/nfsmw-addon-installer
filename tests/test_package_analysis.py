import json
import tempfile
import unittest
from pathlib import Path

from nfsmw_installer.package_analysis import analyze_package


class PackageAnalysisTests(unittest.TestCase):
    def build_package(self, root: Path):
        addon = root / "Addon"
        (addon / "CARS" / "TESTCAR").mkdir(parents=True)
        (addon / "CARS" / "TESTCAR" / "GEOMETRY.BIN").write_bytes(b"g")
        (addon / "CARS" / "TESTCAR" / "TEXTURES.BIN").write_bytes(b"t")
        (addon / "Setup").mkdir()
        (addon / "Install.nfsms").write_text(
            "game MW\n"
            "folder_create CARS\\TESTCAR\n"
            "file_copy CARS\\TESTCAR\\GEOMETRY.BIN CARS\\TESTCAR\\GEOMETRY.BIN\n"
            "script Setup\\car.nfsms\n", encoding="utf-8")
        (addon / "Setup" / "car.nfsms").write_text(
            "copy_node pvehicle punto racers testcar\n"
            "update_field pvehicle testcar MODEL Visual TESTCAR\n"
            "script Shared\\third.nfsms\n", encoding="utf-8")
        (addon / "Shared").mkdir()
        (addon / "Shared" / "third.nfsms").write_text(
            "update_field pvehicle testcar MANUFACTURER 1\n", encoding="utf-8")
        (root / "Binary Data Install.end").write_text(
            '[VERSN1]\n{\n'
            '"Usage": "User",\n'
            '"Game": "MostWanted",\n'
            '"Endscript": "Binary Files\\\\global_install.end",\n'
            '"Files": ["GLOBAL\\\\GLOBALB.LZC",],\n'
            '"Links": [{"LoadType":"Attributes","PathType":"Absolute","File":"GLOBAL\\\\attributes.bin"},],\n'
            '}\n', encoding="utf-8")
        binary = root / "Binary Files"
        binary.mkdir()
        (binary / "global_install.end").write_text(
            '[VERSN2]\nmove_file override relative absolute _Main\\CARS\\TESTCAR\\GEOMETRY.BIN CARS\\TESTCAR\\GEOMETRY.BIN\n'
            'import override GLOBAL\\GLOBALB.LZC DBModelParts _CarParts\\TESTCAR.bin\n'
            'append _Textures\\GlobalB.end\n', encoding="utf-8")
        (binary / "_Main" / "CARS" / "TESTCAR").mkdir(parents=True)
        (binary / "_Main" / "CARS" / "TESTCAR" / "GEOMETRY.BIN").write_bytes(b"geometry")
        (binary / "_CarParts").mkdir()
        (binary / "_CarParts" / "TESTCAR.bin").write_bytes(b"carparts")
        (binary / "_Textures" / "FrontB" / "FrontendTextures").mkdir(parents=True)
        (binary / "_Textures" / "FrontB" / "FrontendTextures" / "TEST.dds").write_bytes(b"dds")
        (binary / "_Textures" / "GlobalB.end").write_text(
            '[VERSN2]\nbind_textures override Frontend\\FrontB.lzc TPKBlocks DEFAULT _Textures\\FrontB\\FrontendTextures\n',
            encoding="utf-8")
        (binary / "global_uninstall.end").write_text(
            '[VERSN2]\nerase_folder absolute CARS\\TESTCAR\n', encoding="utf-8")
        (root / "REPLACE" / "ADDONS" / "CARS_REPLACE" / "PUNTO").mkdir(parents=True)
        (root / "REPLACE" / "ADDONS" / "CARS_REPLACE" / "PUNTO" / "ATTRIBUTES.MWPS").write_text(
            'vpak GLOBAL\\ATTRIBUTES.BIN db\npatch int32 bin:0x1 2\n', encoding="utf-8")
        (root / "Ed Files" / "Config" / "NFSMW").mkdir(parents=True)
        (root / "Ed Files" / "Config" / "NFSMW" / "TESTCAR.ini").write_text("[INFO]\n", encoding="utf-8")

    def test_detects_alternative_profiles_and_nested_nfsms(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build_package(root)
            report = analyze_package(root)
            profile_ids = {p["id"] for p in report["profiles"]}
            self.assertIn("unlimiter_addon", profile_ids)
            self.assertIn("classic_modloader_replacement", profile_ids)
            self.assertEqual(report["car_ids"], ["TESTCAR"])
            self.assertEqual(len(report["components"]["nfsms"]["scripts"]), 3)
            self.assertEqual(report["components"]["nfsms"]["entrypoints"], ["Addon/Install.nfsms"])
            self.assertEqual(report["components"]["nfsms"]["script_base"], "Addon")
            self.assertEqual(report["components"]["nfsms"]["missing_references"], [])
            self.assertTrue(report["components"]["binary_manifests"][0]["valid"])
            self.assertTrue(report["components"]["binary_manifests"][0]["endscript_exists"])
            self.assertEqual(report["components"]["binary_missing_references"], [])
            self.assertIn("Frontend/FrontB.lzc", report["components"]["binary_target_game_files"])
            self.assertNotIn("CARS/TESTCAR", report["components"]["binary_target_game_files"])
            self.assertIn("CARS/TESTCAR", report["components"]["binary_uninstall_target_game_files"])
            self.assertTrue(report["components"]["binary_uninstall_available"])
            self.assertTrue(report["components"]["mwps"])
            self.assertTrue(report["components"]["ed_payload"])
            self.assertFalse(report["safety"]["writes_performed"])

    def test_detects_missing_script_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Install.nfsms").write_text("script missing.nfsms\n", encoding="utf-8")
            report = analyze_package(root)
            self.assertEqual(len(report["components"]["nfsms"]["missing_references"]), 1)

    def test_rejects_unsafe_script_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Install.nfsms").write_text("script ..\\outside.nfsms\n", encoding="utf-8")
            report = analyze_package(root)
            self.assertEqual(len(report["components"]["nfsms"]["unsafe_references"]), 1)


    def test_amod_include_graph_and_car_registration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "CARS" / "TESTCAR").mkdir(parents=True)
            (root / "CARS" / "TESTCAR" / "GEOMETRY.BIN").write_bytes(b"g")
            (root / "CARS" / "TESTCAR" / "TEXTURES.BIN").write_bytes(b"t")
            (root / "parts").mkdir()
            (root / "install.amod").write_text(
                'attribulina 1\ngame mostwanted_pc\ninclude "parts/car.amod"\n', encoding="utf-8")
            (root / "parts" / "car.amod").write_text(
                'attribulina 1\ngame mostwanted_pc\ncollection pvehicle/testcar under pvehicle/racers {\n MODEL = TESTCAR\n}\n',
                encoding="utf-8")
            report = analyze_package(root)
            self.assertEqual(report["car_ids"], ["TESTCAR"])
            self.assertEqual(report["components"]["amod"]["entrypoints"], ["install.amod"])
            self.assertEqual(report["components"]["amod"]["include_graph"]["install.amod"], ["parts/car.amod"])
            self.assertEqual(report["components"]["direct_model_payload"], [
                {"source": "CARS/TESTCAR/GEOMETRY.BIN", "destination": "CARS/TESTCAR/GEOMETRY.BIN"},
                {"source": "CARS/TESTCAR/TEXTURES.BIN", "destination": "CARS/TESTCAR/TEXTURES.BIN"},
            ])

    def test_amod_missing_and_unsafe_includes_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "install.amod").write_text(
                'attribulina 1\ninclude "missing.amod"\ninclude "../outside.amod"\ninclude "loop.amod"\n', encoding="utf-8")
            (root / "loop.amod").write_text('include "install.amod"\n', encoding="utf-8")
            report = analyze_package(root)
            self.assertEqual(len(report["components"]["amod"]["missing_references"]), 1)
            self.assertEqual(len(report["components"]["amod"]["unsafe_references"]), 1)
            self.assertEqual(report["components"]["amod"]["cycles"], ["install.amod"])

    def test_binary_manifest_handles_windows_backslash_f_escape_and_trailing_comma(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Binary Data Install.end").write_text(
                '[VERSN1]\n{"Endscript":"Binary Files\\\\global_install.end",'
                '"Files":["GLOBAL\\\\GLOBALB.LZC",],'
                '"Links":[{"File":"GLOBAL\\\\FE_ATTRIB.BIN",}],}\n', encoding="utf-8")
            (root / "Binary Files").mkdir()
            (root / "Binary Files" / "global_install.end").write_text("[VERSN2]\n", encoding="utf-8")
            report = analyze_package(root)
            manifest = report["components"]["binary_manifests"][0]
            self.assertTrue(manifest["valid"])
            self.assertEqual(manifest["links"][0]["File"], "GLOBAL/FE_ATTRIB.BIN")


if __name__ == "__main__":
    unittest.main()
