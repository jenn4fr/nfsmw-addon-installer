import json, tempfile, unittest
from pathlib import Path
from nfsmw_installer.apply_plan import apply_file_plan, rollback_journal

class ApplyPlanTests(unittest.TestCase):
    def test_dry_run_does_not_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); pkg=root/'pkg'; game=root/'game'; pkg.mkdir(); game.mkdir()
            src=pkg/'a.bin'; src.write_bytes(b'new')
            plan={"package":str(pkg),"game_root":str(game),"operations":[{"operation":"file_copy","source":"a.bin","source_absolute":str(src),"source_exists":True,"destination":"CARS/A/a.bin"}]}
            pp=root/'plan.json'; pp.write_text(json.dumps(plan))
            result=apply_file_plan(pp)
            self.assertFalse(result['writes_performed'])
            self.assertFalse((game/'CARS/A/a.bin').exists())
    def test_execute_and_rollback_created_file(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); pkg=root/'pkg'; game=root/'game'; pkg.mkdir(); game.mkdir()
            src=pkg/'a.bin'; src.write_bytes(b'new')
            plan={"package":str(pkg),"game_root":str(game),"operations":[{"operation":"file_copy","source":"a.bin","source_absolute":str(src),"source_exists":True,"destination":"CARS/A/a.bin"}]}
            pp=root/'plan.json'; pp.write_text(json.dumps(plan))
            result=apply_file_plan(pp, execute=True)
            dest=game/'CARS/A/a.bin'; self.assertEqual(dest.read_bytes(), b'new')
            rollback=rollback_journal(result['journal'])
            self.assertEqual(rollback['removed_files'], 1)
            self.assertFalse(dest.exists())
    def test_existing_file_requires_overwrite_and_is_backed_up(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); pkg=root/'pkg'; game=root/'game'; pkg.mkdir(); game.mkdir()
            src=pkg/'a.bin'; src.write_bytes(b'new'); dest=game/'CARS/A/a.bin'; dest.parent.mkdir(parents=True); dest.write_bytes(b'old')
            plan={"package":str(pkg),"game_root":str(game),"operations":[{"operation":"file_copy","source":"a.bin","source_absolute":str(src),"source_exists":True,"destination":"CARS/A/a.bin"}]}
            pp=root/'plan.json'; pp.write_text(json.dumps(plan))
            with self.assertRaises(FileExistsError): apply_file_plan(pp, execute=True)
            result=apply_file_plan(pp, execute=True, overwrite=True)
            self.assertEqual(dest.read_bytes(), b'new')
            rollback_journal(result['journal'])
            self.assertEqual(dest.read_bytes(), b'old')

    def test_rollback_rejects_destination_outside_game_root(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); game=root/'game'; backup=root/'backup'; game.mkdir(); backup.mkdir()
            journal={"game_root":str(game),"backup_root":str(backup),"operations":[
                {"operation":"file_copy","status":"copied","destination":str(root/'victim.bin'),"created":True,"backup":None}
            ]}
            with self.assertRaises(ValueError): rollback_journal(journal)
