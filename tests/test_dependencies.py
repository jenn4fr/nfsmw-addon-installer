import unittest

from nfsmw_installer.core import _analyze_scripts


class DependencyAnalysisTests(unittest.TestCase):

    def analyze(self, script, inventory):
        return _analyze_scripts(
            {"Addon/SetupFiles/test.nfsms": script.encode("utf-8")},
            inventory,
        )

    def collection_dependencies(self, graph):
        return [
            dep for dep in graph["dependencies"]
            if dep["kind"] == "collection_reference"
        ]

    def test_collection_created_earlier(self):
        script = (
            "copy_node transmission punto default rebel\n"
            "update_field pvehicle rebel transmission[0] Collection rebel\n"
        )
        inventory = {
            "nodes": ["transmission/punto", "pvehicle/rebel"],
            "collections": [],
        }

        _, findings, graph = self.analyze(script, inventory)
        deps = self.collection_dependencies(graph)

        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0]["reference"], "transmission/rebel")
        self.assertEqual(deps[0]["status"], "created_earlier")
        self.assertEqual(deps[0]["created_at_line"], 1)
        self.assertFalse(findings)

    def test_collection_created_later_warns(self):
        script = (
            "update_field pvehicle rebel transmission[0] Collection rebel\n"
            "copy_node transmission punto default rebel\n"
        )
        inventory = {
            "nodes": ["transmission/punto", "pvehicle/rebel"],
            "collections": [],
        }

        _, findings, graph = self.analyze(script, inventory)
        deps = self.collection_dependencies(graph)

        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0]["status"], "created_later")
        self.assertEqual(deps[0]["created_at_line"], 2)
        self.assertIn(
            "COLLECTION_USED_BEFORE_CREATION",
            [finding.code for finding in findings],
        )

    def test_collection_found_in_inventory(self):
        script = (
            "update_field pvehicle rebel transmission[0] Collection rebel\n"
        )
        inventory = {
            "nodes": ["pvehicle/rebel"],
            "collections": ["transmission/rebel"],
        }

        _, findings, graph = self.analyze(script, inventory)
        deps = self.collection_dependencies(graph)

        self.assertEqual(deps[0]["status"], "inventory")
        self.assertFalse(findings)

    def test_unknown_collection_warns_with_inventory(self):
        script = (
            "update_field pvehicle rebel transmission[0] Collection missing\n"
        )
        inventory = {
            "nodes": ["pvehicle/rebel"],
            "collections": [],
        }

        _, findings, graph = self.analyze(script, inventory)
        deps = self.collection_dependencies(graph)

        self.assertEqual(deps[0]["status"], "unverified")
        self.assertIn(
            "COLLECTION_NOT_IN_INVENTORY",
            [finding.code for finding in findings],
        )


if __name__ == "__main__":
    unittest.main()
