import tempfile
import unittest
from pathlib import Path

from nfsmw_installer.donor_catalogue import (
    build_donor_catalogue,
    parse_amod_export,
)


class DonorCatalogueTests(unittest.TestCase):
    def test_parse_export_extracts_collection_and_scalar_fields(self):
        text = '''attribulina 1
game mw_pc
collection pvehicle/carrera under root in vault db {
    MASS = 1450
    PlayerUsable = true
    MODEL = "CARRERA"
    nested = {
        value = 2
    }
}
'''
        records = parse_amod_export(text)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["class"], "pvehicle")
        self.assertEqual(records[0]["leaf"], "carrera")
        self.assertEqual(records[0]["fields"]["MASS"], 1450)
        self.assertIs(records[0]["fields"]["PlayerUsable"], True)
        self.assertEqual(records[0]["fields"]["MODEL"], "CARRERA")

    def test_build_catalogue_from_scan_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ATTRIBUTES.BIN" / "classes" / "pvehicle"
            path.mkdir(parents=True)
            (path / "complete-export.amod").write_text(
                "collection pvehicle/m3 under root in vault db {\n"
                "    MASS = 1500\n"
                "}\n",
                encoding="utf-8",
            )
            catalogue = build_donor_catalogue(Path(tmp))
            self.assertEqual(catalogue["collection_count"], 1)
            self.assertIn("attributes.bin:m3", catalogue["vehicle_profiles"])
            self.assertEqual(
                catalogue["vehicle_profiles"]["attributes.bin:m3"]["configurations"]["pvehicle"][0]["fields"]["MASS"],
                1500,
            )


if __name__ == "__main__":
    unittest.main()
