import unittest

from tools.verify_reference_bundle import verify


class ReferenceBundleTests(unittest.TestCase):
    def test_preserved_archives_and_real_package_reports(self):
        result = verify()
        self.assertEqual(result["status"], "PASS", result["errors"])
        self.assertEqual(len(result["archive_checks"]), 4)
        self.assertEqual(len(result["analysis_report_checks"]), 3)


if __name__ == "__main__":
    unittest.main()
