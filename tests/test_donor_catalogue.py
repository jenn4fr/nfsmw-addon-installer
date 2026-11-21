import tempfile
import unittest
from pathlib import Path

from nfsmw_installer.donor_catalogue import build_donor_catalogue, parse_amod_export


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
                "collection pvehicle/m3 under root in vault db {\n    MASS = 1500\n}\n",
                encoding="utf-8",
            )
            catalogue = build_donor_catalogue(Path(tmp))
            self.assertEqual(catalogue["collection_count"], 1)
            self.assertIn("attributes.bin:m3", catalogue["vehicle_profiles"])
            self.assertEqual(catalogue["vehicle_profiles"]["attributes.bin:m3"]["configurations"]["pvehicle"][0]["fields"]["MASS"], 1500)

    def test_parent_path_is_preserved(self):
        records = parse_amod_export(
            "collection pvehicle/rx7 under pvehicle/racers in vault db {\n"
            "    MASS = 1280\n}\n"
        )
        self.assertEqual(records[0]["parent"], "pvehicle/racers")

    def test_catalogue_anchors_playable_cars_and_joins_exact_leaf(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports = {
                "pvehicle": (
                    "collection pvehicle/racers under pvehicle/default in vault db {\n}\n"
                    "collection pvehicle/testcar under pvehicle/racers in vault db {\n    MASS = 1280\n    MODEL = \"TESTCAR\"\n    engine = [engine/v8_engine, engine/v8_engine_top]\n    brakes = [brakes/not_exported]\n}\n"
                    "collection pvehicle/copsuv under pvehicle/cops in vault db {\n    MASS = 2000\n}\n"
                ),
                "engine": "collection engine/v8_engine under engine/default in vault db {\n    Power = 300\n}\ncollection engine/v8_engine_top under engine/v8_engine in vault db {\n    Power = 450\n}\n",
                "ecar": "collection ecar/testcar under ecar/racers in vault db {\n    RideHeight = 2\n    CamberFront = 0.2\n}\n",
            }
            for cls, body in exports.items():
                path = Path(tmp) / "ATTRIBUTES.BIN" / "classes" / cls
                path.mkdir(parents=True)
                (path / "complete-export.amod").write_text(body, encoding="utf-8")
            catalogue = build_donor_catalogue(Path(tmp))
            self.assertIn("attributes.bin:testcar", catalogue["vehicle_profiles"])
            self.assertNotIn("attributes.bin:copsuv", catalogue["vehicle_profiles"])
            profile = catalogue["vehicle_profiles"]["attributes.bin:testcar"]
            self.assertEqual([x["collection"] for x in profile["configurations"]["engine"]],
                             ["v8_engine", "v8_engine_top"])
            self.assertEqual(profile["features"]["pvehicle.MASS"], 1280)
            self.assertEqual(profile["features"]["ecar.RideHeight"], 2)
            engine_refs = [x for x in profile["collection_references"] if x["class"] == "engine"]
            self.assertTrue(all(x["resolved"] for x in engine_refs))
            brake_ref = next(x for x in profile["collection_references"] if x["class"] == "brakes")
            self.assertFalse(brake_ref["resolved"])


if __name__ == "__main__":
    unittest.main()
