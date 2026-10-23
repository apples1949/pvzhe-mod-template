import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import project_update
import game_environment as env
from test_game_environment import release, policy


@unittest.skipUnless(shutil.which('git'), 'Git is required')
class ProjectUpdateTests(unittest.TestCase):
    def test_fetch_stages_conflicts_and_preserves_player_identity_and_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); upstream = root / 'upstream'; upstream.mkdir()
            def git(folder, *args): return subprocess.check_output(['git','-C',str(folder),*args],stderr=subprocess.DEVNULL).decode().strip()
            def commit(folder): git(folder,'add','.');git(folder,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','test')
            git(upstream,'init','-b','main'); (upstream/'README.md').write_text('original')
            (upstream/'template.lock.json').write_text(json.dumps(dict(schemaVersion=1,upstream=str(upstream),revision=None)))
            (upstream/'game-compatibility.json').write_text(json.dumps(dict(schemaVersion=1,supportedReleases=[])))
            commit(upstream)
            player=root/'player'; subprocess.run(['git','clone',str(upstream),str(player)],check=True,capture_output=True)
            (player/'README.md').write_text('player changes'); (player/'mod.json').write_text('{"id":"my.mod"}')
            (upstream/'README.md').write_text('upstream changes'); (upstream/'new-tool.txt').write_text('new');commit(upstream)
            origin=git(player,'remote','get-url','origin')
            path,result=project_update.plan(player,upstream=str(upstream))
            self.assertIn('README.md',result['overlaps']);self.assertEqual(result['environment'],'unprepared')
            self.assertEqual((player/'README.md').read_text(),'player changes')
            self.assertEqual((player/'mod.json').read_text(),'{"id":"my.mod"}')
            self.assertEqual(git(player,'remote','get-url','origin'),origin)
            self.assertEqual((Path(result['incoming'])/'README.md').read_text(),'upstream changes')
            self.assertTrue((path.parent/'untracked/mod.json').is_file())
            self.assertIsNone(json.loads((player/'template.lock.json').read_text())['revision'])

    def test_refspec_cannot_write_an_unrelated_local_branch(self):
        with self.assertRaises(ValueError): project_update.plan('.', ref='main:refs/heads/other')

    def test_game_mismatch_blocks_record_and_matching_game_is_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); upstream = root / 'upstream'; upstream.mkdir()
            def git(folder, *args): return project_update.git(folder, *args).decode().strip()
            def commit():
                git(upstream, 'add', '.')
                git(upstream, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'test')
            a = release(root / 'a', 'a'); b = release(root / 'b', 'b')
            git(upstream, 'init', '-b', 'main'); policy(upstream, [a]); commit()
            player = root / 'player'; git(root, 'clone', str(upstream), str(player))
            slot, current, _ = env.install(player, root / 'a')
            stamp = (slot / 'game.pck').stat().st_mtime_ns
            path, result = project_update.plan(player, upstream=str(upstream))
            self.assertEqual(result['environment'], 'match')
            project_update.record(player, path)
            self.assertEqual((slot / 'game.pck').stat().st_mtime_ns, stamp)
            policy(upstream, [b]); commit()
            path, result = project_update.plan(player, upstream=str(upstream))
            self.assertEqual(result['environment'], 'requires-game-or-compatible-template')
            with self.assertRaisesRegex(ValueError, 'not been merged'): project_update.record(player, path)
            policy(player, [b])
            with self.assertRaises(ValueError): project_update.record(player, path)
            self.assertEqual(env.verify(slot)['fingerprint'], current['fingerprint'])
