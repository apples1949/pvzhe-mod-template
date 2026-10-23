import copy
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_environment as env
import runtime_storage as storage
from test_tools import make_pack


def release(path, label):
    path.mkdir(); make_pack(path / 'game.pck')
    with (path / 'game.pck').open('ab') as f: f.write(label.encode())
    (path / 'game.exe').write_bytes(b'MZ' + label.encode())
    data = path / 'data_game'; data.mkdir()
    for name in ('PlantsVsZombies.dll', 'GodotSharp.dll'):
        (data / name).write_bytes((name + label).encode())
    result = env.inspect(path); result['version'] = label
    return result


def policy(root, releases):
    env.save(root / 'game-compatibility.json', dict(schemaVersion=1, supportedReleases=[
        {key: r[key] for key in ('version','engine','pckSha256','assemblies')} for r in releases]))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.project = self.root / 'project'; self.project.mkdir()
        self.releases = [release(self.root / name, name) for name in ('a','b','c')]
        policy(self.project, self.releases)


class EnvironmentTests(Fixture):
    def test_same_release_reuses_and_rotation_keeps_only_two(self):
        slot, _, reused = env.install(self.project, self.root / 'a'); self.assertFalse(reused)
        stamp = (slot / 'game.pck').stat().st_mtime_ns
        self.assertTrue(env.install(self.project, self.root / 'a')[2])
        self.assertEqual(stamp, (slot / 'game.pck').stat().st_mtime_ns)
        env.install(self.project, self.root / 'b'); env.install(self.project, self.root / 'c')
        self.assertEqual(env.verify(slot)['version'], 'c')
        self.assertEqual(env.verify(slot.parent / 'old')['version'], 'b')
        self.assertEqual({p.name for p in slot.parent.iterdir()}, {'current','old'})

    def test_rollback_to_old_swaps_and_runtime_is_reused(self):
        slot, data, _ = env.install(self.project, self.root / 'a')
        runtime = env.ensure_runtime(slot, data); stamp = (runtime / 'game.exe').stat().st_mtime_ns
        env.ensure_runtime(slot, data); self.assertEqual(stamp, (runtime / 'game.exe').stat().st_mtime_ns)
        env.install(self.project, self.root / 'b')
        env.install(self.project, slot.parent / 'old')
        self.assertEqual(env.verify(slot)['version'], 'a')
        self.assertEqual(env.verify(slot.parent / 'old')['version'], 'b')

    def test_mismatch_and_tampering_fail_before_replacement(self):
        slot, _, _ = env.install(self.project, self.root / 'a'); policy(self.project, [self.releases[0]])
        with self.assertRaises(ValueError): env.install(self.project, self.root / 'b')
        self.assertEqual(env.active(self.project)[1]['version'], 'a')
        (slot / 'game.exe').write_bytes(b'changed')
        with self.assertRaises(ValueError): env.active(self.project)

    def test_copy_failure_preserves_both_existing_versions(self):
        slot, _, _ = env.install(self.project, self.root / 'a'); env.install(self.project, self.root / 'b')
        with patch.object(env.shutil, 'copyfile', side_effect=OSError('copy interrupted')):
            with self.assertRaises(OSError): env.install(self.project, self.root / 'c')
        self.assertEqual(env.verify(slot)['version'], 'b'); self.assertEqual(env.verify(slot.parent / 'old')['version'], 'a')
        self.assertEqual({p.name for p in slot.parent.iterdir()}, {'current','old'})

    def test_promotion_failure_rolls_back(self):
        slot, _, _ = env.install(self.project, self.root / 'a'); env.install(self.project, self.root / 'b')
        rename = Path.rename
        def fail_stage(path, target):
            if path.name.startswith('.incoming-') and Path(target) == slot: raise OSError('promotion interrupted')
            return rename(path, target)
        with patch.object(Path, 'rename', fail_stage):
            with self.assertRaises(OSError): env.install(self.project, self.root / 'c')
        self.assertEqual(env.verify(slot)['version'], 'b'); self.assertEqual(env.verify(slot.parent / 'old')['version'], 'a')

    def test_lease_and_manifest_traversal_are_rejected(self):
        slot, data, _ = env.install(self.project, self.root / 'a')
        with env.lease(self.project), self.assertRaises(ValueError): env.install(self.project, self.root / 'b')
        data = copy.deepcopy(data); data['files']['../escape'] = data['files']['game.exe']
        with self.assertRaises(ValueError): env.verify(slot, data)

    def test_partial_oldest_cleanup_never_rolls_back_into_damaged_release(self):
        slot, _, _ = env.install(self.project, self.root / 'a'); env.install(self.project, self.root / 'b')
        remove = env.shutil.rmtree
        def interrupted(path, *args, **kwargs):
            if Path(path).name.startswith('.retired-'):
                (Path(path) / 'game.exe').unlink()
                raise OSError('oldest cleanup interrupted')
            return remove(path, *args, **kwargs)
        with patch.object(env.shutil, 'rmtree', interrupted):
            with self.assertRaises(OSError): env.install(self.project, self.root / 'c')
        self.assertEqual(env.verify(slot)['version'], 'c')
        self.assertEqual(env.verify(slot.parent / 'old')['version'], 'b')
        with self.assertRaisesRegex(ValueError, 'Interrupted'): env.install(self.project, self.root / 'c')


class StorageTests(Fixture):
    def make_runtime(self):
        slot, manifest, _ = env.install(self.project, self.root / 'a')
        runtime = self.project / '.work/run'; runtime.mkdir(parents=True)
        for name in manifest['files']:
            dest = runtime / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(slot / name, dest)
        pack = runtime / 'game.pck'
        with pack.open('r+b') as f:
            f.seek(32); f.write(struct.pack('<Q', 999)); f.seek(0,2); f.write(b'test patch')
        (runtime / 'game.log').write_text('evidence'); (runtime / 'mod.pmod').write_bytes(b'mod')
        return slot, runtime, pack.read_bytes()

    def test_preview_then_cleanup_and_exact_restore(self):
        slot, runtime, original = self.make_runtime()
        with patch.object(storage, 'running_workspace_executables', return_value=[]):
            report = storage.cleanup(self.project)
            self.assertEqual(report['archivedPacks'], 1); self.assertTrue((runtime / 'game.pck').exists())
            self.assertFalse((runtime / 'pack-replay.json').exists())
            report = storage.cleanup(self.project, True)
        self.assertEqual(report['archivedPacks'], 1); self.assertFalse((runtime / 'game.pck').exists())
        self.assertEqual((runtime / 'game.log').read_text(), 'evidence'); self.assertEqual((runtime / 'mod.pmod').read_bytes(), b'mod')
        storage.restore(self.project, runtime)
        self.assertEqual((runtime / 'game.pck').read_bytes(), original)
        self.assertEqual((runtime / 'data_game/GodotSharp.dll').read_bytes(), (slot / 'data_game/GodotSharp.dll').read_bytes())
        with patch.object(storage, 'running_workspace_executables', return_value=[]):
            self.assertEqual(storage.cleanup(self.project, True)['archivedPacks'], 1)
        storage.restore(self.project, runtime)
        self.assertEqual((runtime / 'game.pck').read_bytes(), original)

    def test_corrupt_source_and_patch_never_pass(self):
        slot, runtime, original = self.make_runtime(); pack = runtime / 'game.pck'
        changed = bytearray(original); changed[100] ^= 1; pack.write_bytes(changed)
        self.assertIsNone(storage.archive_pack(pack, slot / 'game.pck', runtime, True)); self.assertTrue(pack.exists())
        pack.write_bytes(original); storage.archive_pack(pack, slot / 'game.pck', runtime, True)
        (runtime / 'test-pack.tail.bin').write_bytes(b'corrupt')
        with self.assertRaises(ValueError): storage.restore(self.project, runtime)
        self.assertFalse(pack.exists())

    def test_active_process_and_expired_base_are_not_ignored(self):
        slot, runtime, _ = self.make_runtime()
        with patch.object(storage, 'running_workspace_executables', return_value=[123]), self.assertRaises(ValueError): storage.cleanup(self.project, True)
        storage.archive_pack(runtime / 'game.pck', slot / 'game.pck', runtime, True)
        env.install(self.project, self.root / 'b'); env.install(self.project, self.root / 'c')
        with self.assertRaisesRegex(ValueError, 'no longer'): storage.restore(self.project, runtime)
