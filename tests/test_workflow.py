import tempfile
import unittest
from pathlib import Path

from nfsmw_installer.package_analysis import analyze_package
from nfsmw_installer.workflow import build_workflow_plan, execute_guided_install, rollback_guided_install


class WorkflowTests(unittest.TestCase):
    def build_package(self, root: Path):
        addon = root / "Addon"
        (addon / "Model").mkdir(parents=True)
        (addon / "Model" / "GEOMETRY.BIN").write_bytes(b"geometry")
        (addon / "Model" / "TEXTURES.BIN").write_bytes(b"textures")
        (addon / "Setup").mkdir()
        (addon / "Install.nfsms").write_text(
            "game MW\n"
            "file_copy Model\\GEOMETRY.BIN CARS\\TESTCAR\\GEOMETRY.BIN\n"
            "file_copy Model\\TEXTURES.BIN CARS\\TESTCAR\\TEXTURES.BIN\n"
            "script Setup\\car.nfsms\n", encoding="utf-8")
        (addon / "Setup" / "car.nfsms").write_text(
            "copy_node pvehicle punto racers testcar\n"
            "update_field pvehicle testcar MODEL Visual TESTCAR\n", encoding="utf-8")
        (root / "Binary Data Install.end").write_text(
            '[VERSN1]\n{"Usage":"User","Game":"MostWanted",'
            '"Endscript":"Binary Files\\\\global_install.end",'
            '"Files":["GLOBAL\\\\GLOBALB.LZC",],'
            '"Links":[{"LoadType":"Attributes","PathType":"Absolute","File":"GLOBAL\\\\ATTRIBUTES.BIN"},],}\n',
            encoding="utf-8")
        (root / "Binary Files").mkdir()
        (root / "Binary Files" / "_Main" / "CARS" / "TESTCAR").mkdir(parents=True)
        (root / "Binary Files" / "_Main" / "CARS" / "TESTCAR" / "GEOMETRY.BIN").write_bytes(b"geometry")
        (root / "Binary Files" / "global_install.end").write_text(
            "[VERSN2]\nadd_string LANGUAGES\\ENGLISH.BIN STRBlocks GLOBAL AUTO CAR_TESTCAR_NAME TestCar\n",
            encoding="utf-8")
        (root / "Ed Files" / "Config" / "NFSMW").mkdir(parents=True)
        (root / "Ed Files" / "Config" / "NFSMW" / "TESTCAR.ini").write_text("[INFO]\n", encoding="utf-8")
        (root / "Ed Files" / "Resources" / "NFSMW" / "FrontEnd" / "FrontEndTextures" / "12345678").mkdir(parents=True)
        (root / "Ed Files" / "Resources" / "NFSMW" / "FrontEnd" / "FrontEndTextures" / "12345678" / "CARSELECT_MANUFACTURER_TEST.dds").write_bytes(b"dds")

    def make_game(self, root: Path):
        (root / "scripts").mkdir(parents=True)
        (root / "scripts" / "NFSMWUnlimiter.asi").write_bytes(b"unlimiter")
        (root / "dinput8.dll").write_bytes(b"loader")
        (root / "speed.exe").write_bytes(b"speed")
        (root / "GLOBAL").mkdir()
        (root / "GLOBAL" / "GLOBALB.LZC").write_bytes(b"globalb-original")
        (root / "GLOBAL" / "ATTRIBUTES.BIN").write_bytes(b"attributes-original")
        (root / "GLOBAL" / "FE_ATTRIB.BIN").write_bytes(b"fe-attributes-original")
        (root / "FRONTEND").mkdir()
        (root / "FRONTEND" / "FRONTA.BUN").write_bytes(b"fronta-original")
        (root / "FRONTEND" / "FRONTB.LZC").write_bytes(b"frontb-original")
        (root / "LANGUAGES").mkdir()
        (root / "LANGUAGES" / "ENGLISH.BIN").write_bytes(b"english-original")

    def test_unlimiter_preflight_blocks_missing_unlimiter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            game = root / "game"
            package.mkdir(); game.mkdir()
            self.build_package(package)
            self.make_game(game)
            (game / "scripts" / "NFSMWUnlimiter.asi").unlink()
            plan = build_workflow_plan(package, game, profile="unlimiter_addon", ed_root=root / "ed")
            self.assertFalse(plan["ready"])
            self.assertFalse(next(x for x in plan["compatibility_checks"] if x["check"] == "Unlimiter")["passed"])

    def test_multiple_profiles_require_explicit_choice(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            game = root / "game"
            package.mkdir(); game.mkdir()
            self.build_package(package)
            (package / "REPLACE" / "ADDONS" / "CARS_REPLACE" / "PUNTO").mkdir(parents=True)
            (package / "REPLACE" / "ADDONS" / "CARS_REPLACE" / "PUNTO" / "ATTRIBUTES.MWPS").write_text("vpak GLOBAL\\ATTRIBUTES.BIN db\n")
            self.make_game(game)
            auto_plan = build_workflow_plan(package, game, ed_root=root / "ed")
            self.assertEqual(auto_plan["profile"]["id"], "unlimiter_addon")
            self.assertEqual(auto_plan["profile_selection"], "target_compatible_auto")
            classic_plan = build_workflow_plan(package, game, profile="classic_modloader_replacement", ed_root=root / "ed")
            self.assertFalse(classic_plan["ready"])


    def test_nfsmw_ml_per_mod_package_installs_into_modloader_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "TestMod"
            game = root / "game"
            package.mkdir(); game.mkdir()
            payload = package / "modloader" / "TestMod" / "CARS" / "TESTCAR"
            payload.mkdir(parents=True)
            (payload / "GEOMETRY.BIN").write_bytes(b"geometry")
            (payload / "TEXTURES.BIN").write_bytes(b"textures")
            (game / "scripts").mkdir()
            (game / "scripts" / "NFSMW-ML.asi").write_bytes(b"ml")
            (game / "dinput8.dll").write_bytes(b"asi")
            (game / "speed.exe").write_bytes(b"speed")
            plan = build_workflow_plan(package, game)
            self.assertEqual(plan["profile"]["id"], "nfsmw_modular_loader")
            self.assertTrue(plan["ready"])
            self.assertEqual({x["destination"] for x in plan["modloader_payload"]}, {
                "modloader/TestMod/CARS/TESTCAR/GEOMETRY.BIN",
                "modloader/TestMod/CARS/TESTCAR/TEXTURES.BIN",
            })
            answers = iter(["y"])
            result = execute_guided_install(package, game, backup_root=root / "backup",
                                            input_fn=lambda _prompt: next(answers),
                                            confirm_game_test=True)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue((game / "modloader" / "TestMod" / "CARS" / "TESTCAR" / "GEOMETRY.BIN").is_file())

    def test_legacy_modloader_addons_can_map_to_nfsmw_ml_when_no_mwps(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "LegacyPackage"
            game = root / "game"
            package.mkdir(); game.mkdir()
            payload = package / "Modloader" / "ADDONS" / "CARS_REPLACE" / "PUNTO"
            payload.mkdir(parents=True)
            (payload / "GEOMETRY.BIN").write_bytes(b"geometry")
            (payload / "TEXTURES.BIN").write_bytes(b"textures")
            global_payload = package / "Modloader" / "ADDONS" / "GLOBAL"
            global_payload.mkdir(parents=True)
            (global_payload / "GLOBALB.LZC").write_bytes(b"global")
            (game / "scripts").mkdir()
            (game / "scripts" / "NFSMW-ML.asi").write_bytes(b"ml")
            (game / "dinput8.dll").write_bytes(b"asi")
            (game / "speed.exe").write_bytes(b"speed")
            plan = build_workflow_plan(package, game)
            self.assertEqual(plan["profile"]["id"], "nfsmw_modular_loader")
            destinations = {x["destination"] for x in plan["modloader_payload"]}
            self.assertIn("modloader/LegacyPackage/CARS/PUNTO/GEOMETRY.BIN", destinations)
            self.assertIn("modloader/LegacyPackage/GLOBAL/GLOBALB.LZC", destinations)

    def test_unknown_legacy_modloader_group_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "LegacyPackage"
            game = root / "game"
            package.mkdir(); game.mkdir()
            payload = package / "Modloader" / "ADDONS" / "UNKNOWN" / "something.bin"
            payload.parent.mkdir(parents=True)
            payload.write_bytes(b"unknown")
            (game / "speed.exe").write_bytes(b"speed")
            (game / "scripts").mkdir(); (game / "scripts" / "NFSMW-ML.asi").write_bytes(b"ml")
            (game / "dinput8.dll").write_bytes(b"asi")
            plan = build_workflow_plan(package, game)
            self.assertFalse(plan["ready"])
            self.assertEqual(plan["unmapped_legacy_modloader_payload"], ["Modloader/ADDONS/UNKNOWN/something.bin"])


    def test_explicit_car_id_adds_readback_target_when_parser_cannot_detect_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "OpaqueAMOD"
            game = root / "game"
            package.mkdir(); game.mkdir()
            model = package / "Models" / "TESTCAR"
            model.mkdir(parents=True)
            (model / "GEOMETRY.BIN").write_bytes(b"g")
            (model / "TEXTURES.BIN").write_bytes(b"t")
            (package / "install.amod").write_text("attribulina 1\ngame mostwanted_pc\n", encoding="utf-8")
            (game / "speed.exe").write_bytes(b"speed")
            (game / "scripts").mkdir(); (game / "scripts" / "NFSMWUnlimiter.asi").write_bytes(b"asi")
            (game / "dinput8.dll").write_bytes(b"asi")
            (game / "GLOBAL").mkdir(); (game / "GLOBAL" / "ATTRIBUTES.BIN").write_bytes(b"a"); (game / "GLOBAL" / "FE_ATTRIB.BIN").write_bytes(b"f")
            without_id = build_workflow_plan(package, game, profile="unlimiter_addon")
            self.assertFalse(without_id["ready"])
            with_id = build_workflow_plan(package, game, profile="unlimiter_addon", car_ids_extra=["testcar"])
            self.assertTrue(with_id["ready"])
            self.assertEqual(with_id["car_ids"], ["TESTCAR"])

    def test_uninstall_only_nfsms_is_not_treated_as_install_entrypoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "UninstallOnly"
            game = root / "game"
            package.mkdir(); game.mkdir()
            model = package / "CARS" / "TESTCAR"
            model.mkdir(parents=True)
            (model / "GEOMETRY.BIN").write_bytes(b"g")
            (model / "TEXTURES.BIN").write_bytes(b"t")
            (package / "Uninstall.nfsms").write_text("delete_node pvehicle testcar\n", encoding="utf-8")
            (game / "speed.exe").write_bytes(b"speed")
            (game / "scripts").mkdir(); (game / "scripts" / "NFSMWUnlimiter.asi").write_bytes(b"asi")
            (game / "dinput8.dll").write_bytes(b"asi")
            (game / "GLOBAL").mkdir(); (game / "GLOBAL" / "ATTRIBUTES.BIN").write_bytes(b"a"); (game / "GLOBAL" / "FE_ATTRIB.BIN").write_bytes(b"f")
            plan = build_workflow_plan(package, game, profile="unlimiter_addon")
            self.assertFalse(plan["ready"])
            self.assertIsNone(plan["nfsms_entrypoint"])
            report = analyze_package(package)
            self.assertEqual(report["components"]["nfsms"]["uninstall_entrypoints"], ["Uninstall.nfsms"])

    def test_package_with_both_nfsms_and_amod_entrypoints_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Ambiguous"
            game = root / "game"
            package.mkdir(); game.mkdir()
            model = package / "CARS" / "TESTCAR"
            model.mkdir(parents=True)
            (model / "GEOMETRY.BIN").write_bytes(b"g")
            (model / "TEXTURES.BIN").write_bytes(b"t")
            (package / "install.nfsms").write_text("create_node pvehicle testcar\n", encoding="utf-8")
            (package / "install.amod").write_text("attribulina 1\ncollection pvehicle/testcar {\n}\n", encoding="utf-8")
            (game / "speed.exe").write_bytes(b"speed")
            (game / "scripts").mkdir(); (game / "scripts" / "NFSMWUnlimiter.asi").write_bytes(b"asi")
            (game / "dinput8.dll").write_bytes(b"asi")
            (game / "GLOBAL").mkdir(); (game / "GLOBAL" / "ATTRIBUTES.BIN").write_bytes(b"a"); (game / "GLOBAL" / "FE_ATTRIB.BIN").write_bytes(b"f")
            with self.assertRaisesRegex(ValueError, "both NFSMS and AMOD"):
                build_workflow_plan(package, game, profile="unlimiter_addon")




    def test_backup_root_inside_global_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "pkg"
            game = root / "game"
            self.build_package(package)
            self.make_game(game)
            binary = root / "Binary.exe"; binary.write_bytes(b"fake")
            installer = root / "AttribulinaModInstaller.exe"; installer.write_bytes(b"fake")
            cli = root / "attribcli.exe"; cli.write_bytes(b"fake")
            ed = root / "Ed"; ed.mkdir(); (ed / "Ed.exe").write_bytes(b"fake")
            backup = game / "GLOBAL" / "installer-backup"
            with self.assertRaisesRegex(ValueError, "cannot be inside a game directory"):
                execute_guided_install(
                    package, game, binary_exe=binary, attribulina_installer=installer,
                    attribcli=cli, ed_root=ed, ed_exe=ed / "Ed.exe", backup_root=backup,
                    input_fn=lambda _prompt: "y", launcher=lambda _command: None,
                )
            self.assertFalse(backup.exists())

    def test_vlted_requirement_requires_explicit_attribulina_substitution_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "VltEdPackage"
            game = root / "game"
            self.build_package(package)
            self.make_game(game)
            (package / "readme.txt").write_text("Requires Vlt-Ed 4.6 for database installation.", encoding="utf-8")
            binary = root / "Binary.exe"; binary.write_bytes(b"fake")
            installer = root / "AttribulinaModInstaller.exe"; installer.write_bytes(b"fake")
            cli = root / "attribcli.exe"; cli.write_bytes(b"fake")
            ed = root / "Ed"; ed.mkdir(); (ed / "Ed.exe").write_bytes(b"fake")
            backup = root / "backup"
            with self.assertRaisesRegex(RuntimeError, "substitution was not accepted"):
                execute_guided_install(
                    package, game, binary_exe=binary, attribulina_installer=installer,
                    attribcli=cli, ed_root=ed, ed_exe=ed / "Ed.exe", backup_root=backup,
                    input_fn=lambda _prompt: "n", launcher=lambda _command: None,
                )
            self.assertFalse(backup.exists())

    def test_binary_only_addon_still_runs_database_readback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "BinaryOnly"
            game = root / "game"
            package.mkdir(); game.mkdir()
            model = package / "Binary Files" / "_Main" / "CARS" / "TESTCAR"
            model.mkdir(parents=True)
            (model / "GEOMETRY.BIN").write_bytes(b"geometry")
            (model / "TEXTURES.BIN").write_bytes(b"textures")
            (package / "Binary Files" / "global_install.end").write_text(
                '[VERSN2]\nmove_file override relative absolute _Main\\CARS\\TESTCAR\\GEOMETRY.BIN CARS\\TESTCAR\\GEOMETRY.BIN\n'
                'move_file override relative absolute _Main\\CARS\\TESTCAR\\TEXTURES.BIN CARS\\TESTCAR\\TEXTURES.BIN\n',
                encoding="utf-8")
            (package / "Binary Data Install.end").write_text(
                '[VERSN1]\n{"Usage":"User","Game":"MostWanted","Endscript":"Binary Files\\global_install.end","Files":["GLOBAL\\GLOBALB.LZC"]}\n',
                encoding="utf-8")
            (package / "UnlimiterData").mkdir()
            (package / "UnlimiterData" / "TESTCAR.ini").write_text("[Car]\nName=TestCar\n", encoding="utf-8")
            (game / "speed.exe").write_bytes(b"speed")
            (game / "dinput8.dll").write_bytes(b"asi")
            (game / "scripts").mkdir(); (game / "scripts" / "NFSMWUnlimiter.asi").write_bytes(b"unlimiter")
            (game / "scripts" / "UnlimiterData").mkdir()
            (game / "GLOBAL").mkdir(); (game / "GLOBAL" / "GLOBALB.LZC").write_bytes(b"global-before")
            (game / "GLOBAL" / "ATTRIBUTES.BIN").write_bytes(b"attributes"); (game / "GLOBAL" / "FE_ATTRIB.BIN").write_bytes(b"fe")
            binary = root / "Binary.exe"; binary.write_bytes(b"fake")
            attribcli = root / "attribcli.exe"
            attribcli.write_text(
                "#!/usr/bin/env python3\nimport pathlib,sys\nout=pathlib.Path(sys.argv[sys.argv.index('-o')+1])\nout.parent.mkdir(parents=True,exist_ok=True)\nout.write_text('create pvehicle/testcar')\n",
                encoding="utf-8")
            attribcli.chmod(0o755)
            def launcher(command):
                if Path(command[0]).name.casefold() == "binary.exe":
                    (game / "GLOBAL" / "GLOBALB.LZC").write_bytes(b"global-after")
                    for name in ("GEOMETRY.BIN", "TEXTURES.BIN"):
                        dest = game / "CARS" / "TESTCAR" / name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes((model / name).read_bytes())
            answers = iter(["", "y", "y"])
            result = execute_guided_install(
                package, game, profile="unlimiter_addon", binary_exe=binary, attribcli=attribcli,
                backup_root=root / "backup", input_fn=lambda _prompt: next(answers),
                launcher=launcher, confirm_game_test=True,
            )
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["database_verification"]["status"], "read_back_passed")
            self.assertTrue((game / "scripts" / "UnlimiterData" / "TESTCAR.ini").is_file())

    def test_amod_addon_guided_install_with_direct_model_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "AMODCar"
            game = root / "game"
            package.mkdir(); game.mkdir()
            model = package / "CARS" / "TESTCAR"
            model.mkdir(parents=True)
            (model / "GEOMETRY.BIN").write_bytes(b"geometry")
            (model / "TEXTURES.BIN").write_bytes(b"textures")
            (package / "UnlimiterData").mkdir()
            (package / "UnlimiterData" / "TESTCAR.ini").write_text("[Car]\nName=TestCar\n", encoding="utf-8")
            (package / "install.amod").write_text(
                'attribulina 1\ngame mostwanted_pc\ncollection pvehicle/testcar under pvehicle/racers {\n MODEL = TESTCAR\n}\n',
                encoding="utf-8")
            (game / "speed.exe").write_bytes(b"speed")
            (game / "scripts").mkdir()
            (game / "scripts" / "UnlimiterData").mkdir()
            (game / "scripts" / "NFSMWUnlimiter.asi").write_bytes(b"unlimiter")
            (game / "dinput8.dll").write_bytes(b"asi")
            (game / "GLOBAL").mkdir()
            (game / "GLOBAL" / "ATTRIBUTES.BIN").write_bytes(b"attributes-before")
            (game / "GLOBAL" / "FE_ATTRIB.BIN").write_bytes(b"fe-before")
            (root / "AttribulinaModInstaller.exe").write_bytes(b"fake")
            attribcli = root / "attribcli.exe"
            attribcli.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib,sys\n"
                "out=pathlib.Path(sys.argv[sys.argv.index('-o')+1])\n"
                "out.parent.mkdir(parents=True,exist_ok=True)\n"
                "out.write_text('create pvehicle/testcar')\n",
                encoding="utf-8")
            attribcli.chmod(0o755)
            plan = build_workflow_plan(package, game, profile="unlimiter_addon")
            self.assertTrue(plan["ready"])
            self.assertEqual(plan["nfsms_entrypoint_relative"], "install.amod")
            def launcher(command):
                if Path(command[0]).name.casefold() == "attribulinamodinstaller.exe":
                    (game / "GLOBAL" / "ATTRIBUTES.BIN").write_bytes(b"attributes-after")
            answers = iter(["", "y", "y"])
            result = execute_guided_install(
                package, game, profile="unlimiter_addon",
                attribulina_installer=root / "AttribulinaModInstaller.exe", attribcli=attribcli,
                backup_root=root / "backup", input_fn=lambda _prompt: next(answers),
                launcher=launcher, confirm_game_test=True,
            )
            self.assertEqual(result["status"], "PASS")
            self.assertTrue((game / "CARS" / "TESTCAR" / "GEOMETRY.BIN").is_file())
            self.assertTrue((game / "scripts" / "UnlimiterData" / "TESTCAR.ini").is_file())

    def test_guided_install_and_rollback_with_mocked_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            game = root / "game"
            ed = root / "ed"
            package.mkdir(); game.mkdir(); ed.mkdir()
            self.build_package(package)
            self.make_game(game)
            for tool in (root / "Binary.exe", root / "AttribulinaModInstaller.exe", ed / "Ed.exe"):
                tool.write_bytes(b"fake exe")

            attribcli = root / "attribcli.exe"
            attribcli.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib,sys\n"
                "out=pathlib.Path(sys.argv[sys.argv.index('-o')+1])\n"
                "out.parent.mkdir(parents=True,exist_ok=True)\n"
                "out.write_text('create pvehicle/testcar from pvehicle/punto\\n')\n",
                encoding="utf-8")
            attribcli.chmod(0o755)

            def launcher(command):
                name = Path(command[0]).name.casefold()
                if name == "binary.exe":
                    (game / "GLOBAL" / "GLOBALB.LZC").write_bytes(b"globalb-binary-installed")
                    source_model = package / "Binary Files" / "_Main" / "CARS" / "TESTCAR" / "GEOMETRY.BIN"
                    dest_model = game / "CARS" / "TESTCAR" / "GEOMETRY.BIN"
                    dest_model.parent.mkdir(parents=True, exist_ok=True)
                    dest_model.write_bytes(source_model.read_bytes())
                elif name == "ed.exe":
                    (game / "FRONTEND" / "FRONTA.BUN").write_bytes(b"fronta-ed-installed")
                elif name == "attribulinamodinstaller.exe":
                    (game / "GLOBAL" / "ATTRIBUTES.BIN").write_bytes(b"attributes-installed")
                    model = game / "CARS" / "TESTCAR"
                    model.mkdir(parents=True, exist_ok=True)
                    (model / "GEOMETRY.BIN").write_bytes(b"geometry")
                    (model / "TEXTURES.BIN").write_bytes(b"textures")

            answers = iter(["", "y", "", "y", "", "y", "y"])
            result = execute_guided_install(
                package, game, profile="unlimiter_addon",
                binary_exe=root / "Binary.exe",
                attribulina_installer=root / "AttribulinaModInstaller.exe",
                attribcli=attribcli, ed_root=ed, ed_exe=ed / "Ed.exe",
                backup_root=root / "backup", input_fn=lambda _prompt: next(answers),
                launcher=launcher, confirm_game_test=True,
            )
            self.assertEqual(result["status"], "PASS")
            self.assertTrue((game / "CARS" / "TESTCAR" / "GEOMETRY.BIN").is_file())
            self.assertTrue((ed / "Config" / "NFSMW" / "TESTCAR.ini").is_file())
            # The rollback guard must refuse if another mod changed GLOBAL after this run,
            # and it must refuse before restoring any part of the transaction.
            (game / "GLOBAL" / "other-mod.bin").write_bytes(b"external change")
            with self.assertRaises(RuntimeError):
                rollback_guided_install(result["journal"])
            self.assertTrue((game / "CARS" / "TESTCAR" / "GEOMETRY.BIN").is_file())
            (game / "GLOBAL" / "other-mod.bin").unlink()
            rollback = rollback_guided_install(result["journal"])
            self.assertGreaterEqual(rollback["restored_files"], 1)
            self.assertFalse((game / "CARS" / "TESTCAR" / "GEOMETRY.BIN").exists())
            self.assertFalse((ed / "Config" / "NFSMW" / "TESTCAR.ini").exists())


if __name__ == "__main__":
    unittest.main()
