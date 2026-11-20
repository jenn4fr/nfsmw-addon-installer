import unittest
from nfsmw_installer.core import parse_nfsms, classify_file

class ParserTests(unittest.TestCase):
    def test_comments_and_lines(self):
        cmds=parse_nfsms('# comment\ncopy_node brakes punto default rebel # trailing\nupdate_field pvehicle rebel MASS 1656')
        self.assertEqual(len(cmds),2)
        self.assertEqual(cmds[0].line,2)
        self.assertEqual(cmds[0].args,['brakes','punto','default','rebel'])
    def test_file_classification(self):
        self.assertEqual(classify_file('ADDONS/CARS_REPLACE/PUNTO/ATTRIBUTES.MWPS'),'binary_patch_script')
        self.assertEqual(classify_file('Ed Files/Config/NFSMW/REBEL.ini'),'unlimiter_or_mod_config')

if __name__=='__main__': unittest.main()
