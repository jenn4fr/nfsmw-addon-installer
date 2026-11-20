import unittest

from nfsmw_installer.inventory import (
    parse_class_list,
    parse_collection_tree,
)


class InventoryParserTests(unittest.TestCase):

    def test_class_list_parser(self):
        text = """\
brakes (92)
ecar (97)
frontend (461)
gameplay (0)
"""
        self.assertEqual(
            parse_class_list(text),
            [
                ("brakes", 92),
                ("ecar", 97),
                ("frontend", 461),
                ("gameplay", 0),
            ],
        )

    def test_nested_paths_are_preserved(self):
        text = """\
default
  racers
    punto
    viper
  traffic
    street
      traf4dseda
"""
        records = parse_collection_tree(text, "ecar")

        paths = [r["path"] for r in records]

        self.assertEqual(
            paths,
            [
                "default",
                "default/racers",
                "default/racers/punto",
                "default/racers/viper",
                "default/traffic",
                "default/traffic/street",
                "default/traffic/street/traf4dseda",
            ],
        )

    def test_parent_and_depth_are_correct(self):
        records = parse_collection_tree(
            "default\n  racers\n    punto\n",
            "ecar",
        )

        punto = records[-1]

        self.assertEqual(punto["name"], "punto")
        self.assertEqual(punto["parent"], "default/racers")
        self.assertEqual(punto["depth"], 2)
        self.assertEqual(punto["class"], "ecar")


if __name__ == "__main__":
    unittest.main()
