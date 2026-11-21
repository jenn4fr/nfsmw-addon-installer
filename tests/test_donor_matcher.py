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
