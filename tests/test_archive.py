import tempfile
import unittest
import zipfile
import subprocess
from pathlib import Path
from unittest.mock import patch

from nfsmw_installer.archive import extract_archive, inspect_archive


class ArchiveTests(unittest.TestCase):
    def test_zip_inspection_and_safe_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "car.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("Addon/CARS/TEST/GEOMETRY.BIN", b"geometry")
                zf.writestr("Addon/readme.txt", "test")
            info = inspect_archive(archive)
            self.assertEqual(info["format"], "zip")
            self.assertEqual(info["file_count"], 2)
            out = root / "out"
            result = extract_archive(archive, out)
            self.assertTrue(result["extraction_verified"])
            self.assertEqual((out / "Addon/CARS/TEST/GEOMETRY.BIN").read_bytes(), b"geometry")


    def test_zip_case_colliding_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "collision.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("CARS/TESTCAR/GEOMETRY.BIN", b"a")
                zf.writestr("cars/testcar/geometry.bin", b"b")
            with self.assertRaisesRegex(ValueError, "duplicate/case-colliding"):
                inspect_archive(archive)

    def test_zip_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../outside.txt", b"bad")
            with self.assertRaises(ValueError):
                inspect_archive(archive)

    def test_extraction_refuses_nonempty_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "car.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("file.txt", b"ok")
            out = root / "out"
            out.mkdir()
            (out / "keep.txt").write_text("keep")
            with self.assertRaises(FileExistsError):
                extract_archive(archive, out)

    def test_7z_listing_is_parsed_and_unpacked_size_limit_is_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "car.rar"
            archive.write_bytes(b"not-a-real-rar")
            seven = root / "7z.exe"
            seven.write_bytes(b"fake executable")
            listing = (
                f"Path = {archive}\nType = Rar5\n\n"
                "Path = Addon\\CARS\\TEST\\GEOMETRY.BIN\n"
                "Size = 128\nPacked Size = 64\nAttributes = ....A\n\n"
            )
            completed = subprocess.CompletedProcess([str(seven), "l"], 0, listing, "")
            with patch("nfsmw_installer.archive.subprocess.run", return_value=completed):
                info = inspect_archive(archive, seven_zip=seven)
                self.assertEqual(info["format"], "7zip")
                self.assertEqual(info["file_count"], 1)
                self.assertEqual(info["total_unpacked_bytes"], 128)
                with self.assertRaisesRegex(ValueError, "over the configured limit"):
                    inspect_archive(archive, seven_zip=seven, max_unpacked_bytes=64)

    def test_7z_listing_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "bad.7z"
            archive.write_bytes(b"not-a-real-7z")
            seven = root / "7z.exe"
            seven.write_bytes(b"fake executable")
            listing = (
                f"Path = {archive}\nType = 7z\n\n"
                "Path = ..\\outside.txt\nSize = 4\nAttributes = ....A\n\n"
            )
            completed = subprocess.CompletedProcess([str(seven), "l"], 0, listing, "")
            with patch("nfsmw_installer.archive.subprocess.run", return_value=completed):
                with self.assertRaisesRegex(ValueError, "path traversal"):
                    inspect_archive(archive, seven_zip=seven)


if __name__ == "__main__":
    unittest.main()
