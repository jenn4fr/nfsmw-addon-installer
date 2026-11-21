import unittest
from nfsmw_installer.donor_matcher import rank_donors, build_configuration_proposal

class DonorMatcherTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = {"vehicle_profiles": {
            "attributes.bin:donor_a": {"name":"donor_a", "database":"attributes.bin", "configurations": {
                "pvehicle":[{"collection":"cars/racers/donor_a", "fields":{"MASS":1200,"MODEL":"DONOR"}}],
                "engine":[{"collection":"donor_a", "fields":{"Power":300,"Torque":400}}],
                "transmission":[{"collection":"donor_a", "fields":{"Gears":6}}],
                "brakes":[{"collection":"donor_a", "fields":{"Brake":1}}],
                "chassis":[{"collection":"donor_a", "fields":{"Spring":1}}],
                "tires":[{"collection":"donor_a", "fields":{"Grip":1}}],
                "induction":[{"collection":"donor_a", "fields":{"Boost":1}}],
            }},
            "attributes.bin:donor_b": {"name":"donor_b", "database":"attributes.bin", "configurations": {
                "pvehicle":[{"collection":"cars/racers/donor_b", "fields":{"MASS":800}}]}}
        }}
    def test_ranks_more_complete_donor_first(self):
        result=rank_donors(self.catalogue, target_name="newcar")
        self.assertEqual(result["recommendations"][0]["name"], "donor_a")
        self.assertFalse(result["physical_compatibility_verified"])
    def test_excludes_target_identity(self):
        result=rank_donors(self.catalogue, target_name="donor_a")
        self.assertNotIn("donor_a", [x["name"] for x in result["recommendations"]])
    def test_proposal_preserves_identity_fields(self):
        p=build_configuration_proposal(self.catalogue, "attributes.bin:donor_a", "newcar")
        pv=[x for x in p["proposals"] if x["class"]=="pvehicle"][0]
        self.assertEqual(pv["fields"], {"MASS":1200})
        self.assertFalse(p["executable"])
        self.assertIn("vehicle identity", p["preserved_identity_domains"])

    def test_target_profile_adds_numeric_similarity_explanation(self):
        self.catalogue["vehicle_profiles"]["attributes.bin:donor_a"]["features"] = {"pvehicle.MASS": 1200}
        self.catalogue["vehicle_profiles"]["attributes.bin:donor_b"]["features"] = {"pvehicle.MASS": 1800}
        self.catalogue["vehicle_profiles"]["attributes.bin:target"] = {
            "name": "target", "database": "attributes.bin", "features": {"pvehicle.MASS": 1250},
            "configurations": {"pvehicle": [{"collection": "pvehicle/target", "fields": {"MASS": 1250}}]},
        }
        result = rank_donors(self.catalogue, target_name="new-addon", target_profile="target")
        by_name = {item["name"]: item for item in result["recommendations"]}
        self.assertGreater(by_name["donor_a"]["feature_similarity"]["score"],
                           by_name["donor_b"]["feature_similarity"]["score"])
        self.assertIn("numeric feature similarity", result["ranking_basis"])
        self.assertNotIn("target", [item["name"] for item in result["recommendations"]])

    def test_unknown_target_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            rank_donors(self.catalogue, target_profile="missing")

class TargetCollectionMappingTests(unittest.TestCase):
    def test_parses_explicit_create_directives_only(self):
        from nfsmw_installer.donor_matcher import parse_target_collections
        text = '''create engine/rebel from engine/punto under engine/default in vault db
create engine/rebel_top from engine/punto_top under engine/rebel in vault db
create frontend/rebel from frontend/audi under frontend/default in vault db
'''
        self.assertEqual(parse_target_collections(text), {"engine": "engine/rebel"})

    def test_proposal_maps_base_and_top_targets_from_amod_mapping(self):
        from nfsmw_installer.donor_matcher import build_configuration_proposal
        catalogue = {"vehicle_profiles": {"attributes.bin:donor": {
            "name": "donor", "database": "attributes.bin", "configurations": {
                "engine": [
                    {"collection": "engine/donor", "fields": {"Power": 300}},
                    {"collection": "engine/donor_top", "fields": {"Power": 400}},
                ]
            }
        }}}
        proposal = build_configuration_proposal(
            catalogue, "attributes.bin:donor", "Rebel",
            target_collections={"engine": "engine/rebel"})
        mapped = [x["target_collection"] for x in proposal["proposals"]]
        self.assertEqual(mapped, ["engine/rebel", "engine/rebel_top"])
        self.assertFalse(proposal["executable"])

    def test_target_aware_proposal_excludes_global_defaults_and_unmapped_classes(self):
        from nfsmw_installer.donor_matcher import build_configuration_proposal
        catalogue = {"vehicle_profiles": {"attributes.bin:donor": {
            "name": "donor", "database": "attributes.bin", "configurations": {
                "engine": [
                    {"collection": "engine/default", "fields": {"Power": 1}},
                    {"collection": "engine/donor", "fields": {"Power": 300}},
                ],
                "rigidbodyspecs": [
                    {"collection": "rigidbodyspecs/racers", "fields": {"GRAVITY": 1}}
                ],
            }
        }}}
        proposal = build_configuration_proposal(
            catalogue, "attributes.bin:donor", "Target",
            target_collections={"engine": "engine/target"})
        self.assertEqual(len(proposal["proposals"]), 1)
        self.assertEqual(proposal["proposals"][0]["donor_collection"], "engine/donor")
        self.assertEqual(proposal["proposals"][0]["target_collection"], "engine/target")
