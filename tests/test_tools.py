import hashlib
import json
import struct
import sys
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pck import Pack, safe_path
from mod import check_package
import mod
from manifest_policy import validate_metadata
from runtime_test import config_entries, variant_string


def metadata(**values):
    return {"id": "test.mod", "name": "测试 Mod", "author": "测试作者", "version": "0.1.0", **values}


def make_pack(path, version=4, names=("res://a.txt",), flags=0):
    payload = b"hello"
    header = b"GDPC" + struct.pack("<IIIIIQ", version, 4, 7, 0, flags, 112)
    rows = b""
    for name in names:
        n = name.encode(); n += b"\0" * (-len(n) % 4)
        rows += struct.pack("<I", len(n)) + n + struct.pack("<QQ", 0, len(payload)) + hashlib.md5(payload).digest() + struct.pack("<I", 0)
    directory = struct.pack("<I", len(names)) + rows
    if version == 2:
        header += b"\0" * 64
        # v2 directory precedes payload; adjust base accordingly.
        base = len(header) + len(directory)
        header = header[:24] + struct.pack("<Q", base) + header[32:]
        path.write_bytes(header + directory + payload)
    else:
        header += struct.pack("<Q", 112 + len(payload))
        header += b"\0" * (112 - len(header))
        path.write_bytes(header + payload + directory)


class PckTests(unittest.TestCase):
    def test_supported_formats_checksum_and_repeatable_extract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for version in (2, 3, 4):
                path = root / f"v{version}.pck"; make_pack(path, version)
                pack = Pack(path)
                self.assertEqual(pack.read("a.txt"), b"hello")
                out = root / f"out{version}"
                pack.extract(["a.txt"], out); pack.extract(["a.txt"], out)
                (out / "a.txt").write_bytes(b"user data")
                with self.assertRaises(FileExistsError):
                    pack.extract(["a.txt"], out)

    def test_reject_corruption_encryption_and_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.pck"
            make_pack(path)
            data = bytearray(path.read_bytes()); data[112] ^= 1; path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "checksum"):
                Pack(path).read("a.txt")
            make_pack(path, flags=1)
            with self.assertRaisesRegex(ValueError, "Encrypted"):
                Pack(path)
            make_pack(path, names=("res://a.txt", "res://A.txt"))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                Pack(path)
            make_pack(path); path.write_bytes(path.read_bytes()[:-8])
            with self.assertRaises(ValueError):
                Pack(path)

    def test_unsafe_paths(self):
        for name in ("../outside", "/absolute", "C:/file", "dir\\file", "NUL.txt", "dir/../file", "a//b", "a./file"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_path(name)

    def test_extract_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); path = root / "test.pck"; make_pack(path, names=("res://link/a.txt",))
            out = root / "out"; out.mkdir(); elsewhere = root / "elsewhere"; elsewhere.mkdir()
            try:
                (out / "link").symlink_to(elsewhere, target_is_directory=True)
            except OSError:
                self.skipTest("Windows symlink privilege not available")
            with self.assertRaisesRegex(ValueError, "escaped"):
                Pack(path).extract(["link/a.txt"], out)


class PackageTests(unittest.TestCase):
    def test_profiles_keep_sources_and_outputs_separate(self):
        with patch.multiple(mod, EXAMPLE=mod.EXAMPLE, DIST=mod.DIST, PACKAGE=mod.PACKAGE):
            mod.select_example("feature-lab")
            self.assertEqual(mod.source_root(), mod.ROOT / "examples/FeatureLab/mod")
            self.assertEqual(mod.PACKAGE, mod.ROOT / "dist/feature-lab/feature-lab.pmod")
            mod.select_example("hello-world")
            self.assertEqual(mod.source_root(), mod.ROOT / "mod")
            self.assertEqual(mod.PACKAGE, mod.ROOT / "dist/hello-world.pmod")
            with self.assertRaisesRegex(ValueError, "Unknown"):
                mod.select_example("typo")

    def test_declared_level_data_allowed_but_unlisted_data_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.pmod"
            manifest = metadata(runtimeAssembly="Runtime/ModAssembly.dll", resources=["Assets/level.json"])
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("mod.json", json.dumps(manifest))
                z.writestr("Runtime/ModAssembly.dll", b"MZtest")
                z.writestr("Assets/level.json", '{"Name":"own.level"}')
            self.assertEqual(check_package(path), manifest)
            with zipfile.ZipFile(path, "a") as z:
                z.writestr("Assets/undeclared.json", "{}")
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                check_package(path)

    def test_feature_verification_requires_scenario_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); work = root / ".work"; work.mkdir()
            source = root / "examples/FeatureLab/mod"; source.mkdir(parents=True)
            package = root / "dist/feature-lab/feature-lab.pmod"; package.parent.mkdir(parents=True)
            m = {**metadata(), "id": "test.features", "schemaVersion": 3, "runtimeApiVersion": 3,
                 "runtimeAssembly": "Runtime/ModAssembly.dll", "runtimeAssemblyPolicy": "required",
                 "runtimeEntryType": "FeatureLab.Entry", "resources": []}
            (source / "mod.json").write_text(json.dumps(m))
            (work / "api.json").write_text(json.dumps({"schemaVersion": 3, "runtimeApiVersion": 3}))
            with zipfile.ZipFile(package, "w") as z:
                z.writestr("mod.json", json.dumps(m)); z.writestr("Runtime/ModAssembly.dll", b"MZfeatures")
            log = root / "game.log"
            identity = hashlib.sha256(b"MZfeatures").hexdigest()
            base = f"[Mod:test.features] HELLO_INIT: test\n[Mod:test.features] HELLO_BINARY: {identity}\npackage applied: test.features\n"
            markers = ("HELLO_READY", "LAB_UI", "LAB_DIALOG", "LAB_SETTINGS", "LAB_LEVEL", "LAB_HUD",
                       "LAB_BATTLE", "LAB_BONUS", "LAB_KILL", "LAB_RESULT", "LAB_TEST_PASS")
            with patch.multiple(mod, ROOT=root, WORK=work, DIST=package.parent, PACKAGE=package, EXAMPLE="feature-lab"):
                log.write_text(base + "".join(f"[Mod:test.features] {x}: yes\n" for x in markers[:-1]))
                with self.assertRaisesRegex(ValueError, "LAB_TEST_PASS"):
                    mod.verify(SimpleNamespace(log=log))
                with log.open("a") as f:
                    f.write("[Mod:test.features] LAB_TEST_PASS: yes\n")
                mod.verify(SimpleNamespace(log=log))
                report = json.loads((package.parent / "verification.json").read_text())
                self.assertEqual(report["example"], "feature-lab")
                self.assertEqual(report["runtimeBinarySha256"], identity)

    def test_runtime_log_must_match_current_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); work = root / ".work"; work.mkdir(); (root / "mod").mkdir()
            package = root / "dist/test.pmod"; package.parent.mkdir()
            m = {**metadata(), "id": "test.hello", "schemaVersion": 3, "runtimeApiVersion": 1,
                 "runtimeAssembly": "Runtime/ModAssembly.dll", "runtimeAssemblyPolicy": "required",
                 "runtimeEntryType": "HelloMod.Entry", "resources": []}
            (root / "mod/mod.json").write_text(json.dumps(m))
            (work / "api.json").write_text(json.dumps({"schemaVersion": 3, "runtimeApiVersion": 3}))
            with zipfile.ZipFile(package, "w") as z:
                z.writestr("mod.json", json.dumps(m)); z.writestr("Runtime/ModAssembly.dll", b"MZbinary")
            log = root / "game.log"
            lines = "[Mod:test.hello] HELLO_INIT: hello\n[Mod:test.hello] HELLO_BINARY: {}\n[ModLoader] package applied: test.hello\n[Mod:test.hello] HELLO_READY: ready\n[Mod:test.hello] HELLO_UI: mounted\n"
            with patch.multiple(mod, ROOT=root, WORK=work, DIST=package.parent, PACKAGE=package):
                log.write_text(lines.format("wrong"))
                with self.assertRaisesRegex(ValueError, "does not match"):
                    mod.verify(SimpleNamespace(log=log))
                good = lines.format(hashlib.sha256(b"MZbinary").hexdigest())
                log.write_text(good)
                mod.verify(SimpleNamespace(log=log))
                log.write_text(good + "ERROR: callback failed\n")
                with self.assertRaisesRegex(ValueError, "warnings/errors"):
                    mod.verify(SimpleNamespace(log=log))

    def test_reject_accidentally_distributed_host_dll(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.pmod"
            manifest = metadata(runtimeAssembly="Runtime/ModAssembly.dll", resources=[])
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("mod.json", json.dumps(manifest)); z.writestr("Runtime/ModAssembly.dll", b"MZtest")
            self.assertEqual(check_package(path), manifest)
            with zipfile.ZipFile(path, "a") as z:
                z.writestr("PlantsVsZombies.dll", b"MZhost")
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                check_package(path)

    def test_binary_project_roundtrip(self):
        value = variant_string("独立测试")
        key = b"application/config/name"
        data = b"ECFG" + struct.pack("<II", 1, len(key)) + key + struct.pack("<I", len(value)) + value
        self.assertEqual(config_entries(data)[key.decode()], value)
        with self.assertRaises(ValueError):
            config_entries(data + b"unexpected")


class MetadataTests(unittest.TestCase):
    def test_limits_and_character_sets(self):
        validate_metadata(metadata(id="a" * 32, author="作" * 32, version="1.2.3-alpha.1+build.001"))
        for key, value in (("id", "a" * 33), ("id", "Uppercase"), ("id", "dir/mod"),
                           ("id", "dir\\mod"), ("id", "中文"), ("id", ".."),
                           ("author", "作" * 33), ("author", "😀" * 17),
                           ("name", ""), ("author", " "), ("id", 123), ("name", "Name\n")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_metadata(metadata(**{key: value}))

    def test_semver_including_numeric_prerelease(self):
        for version in ("0.1.0", "1.0.0-beta.1", "1.0.0-0", "1.0.0-01x", "1.0.0+001", "1.2.3+" + "x" * 26):
            validate_metadata(metadata(version=version))
        for version in ("1.0", "v1.0.0", "01.0.0", "1.0.0-01", "1.0.0-beta.01",
                        "1.0.0-", "1.0.0+a..b", "1.0.0_foo", "1.2.3+" + "x" * 27):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "version"):
                validate_metadata(metadata(version=version))

    def test_release_rejects_examples_but_local_build_allows_them(self):
        for changes in ({"id": "local.hello-world"}, {"id": "local.feature-lab"},
                        {"author": "Mod 开发者"}, {"name": "Hello World 模板"}):
            sample = metadata(**changes)
            validate_metadata(sample)
            with self.assertRaisesRegex(ValueError, "release"):
                validate_metadata(sample, release=True)
        validate_metadata(metadata(id="local.my-custom-mod"), release=True)

    def test_custom_identity_changes_package_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "mod").mkdir()
            (root / "mod/mod.json").write_text(json.dumps(metadata(id="my.kill-counter")))
            with patch.multiple(mod, ROOT=root, EXAMPLE=mod.EXAMPLE, DIST=mod.DIST, PACKAGE=mod.PACKAGE):
                mod.select_example("hello-world")
                self.assertEqual(mod.PACKAGE.name, "my.kill-counter.pmod")

    def test_conflicts_and_confirmed_updates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); installed = root / "test.mod.pmod"
            with zipfile.ZipFile(installed, "w") as archive:
                archive.writestr("mod.json", json.dumps(metadata(id="TEST.MOD")))
            args = SimpleNamespace(mods_dir=root, allow_update=False)
            with patch.object(mod, "PACKAGE", root / "dist/test.mod.pmod"):
                with self.assertRaisesRegex(ValueError, "conflict"):
                    mod.check_id_conflicts(metadata(), args)
                args.allow_update = True
                mod.check_id_conflicts(metadata(), args)
                installed.rename(root / "another-file.pmod")
                with self.assertRaisesRegex(ValueError, "conflict"):
                    mod.check_id_conflicts(metadata(), args)

    def test_release_check_rejects_stale_packaged_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "mod").mkdir(); work = root / ".work"; work.mkdir()
            packaged = metadata(runtimeAssembly="Runtime/ModAssembly.dll", runtimeAssemblyPolicy="required",
                                runtimeEntryType="HelloMod.Entry", schemaVersion=3, runtimeApiVersion=1, resources=[])
            (root / "mod/mod.json").write_text(json.dumps({**packaged, "author": "Changed"}))
            (work / "api.json").write_text(json.dumps({"schemaVersion": 3, "runtimeApiVersion": 3}))
            package = root / "test.mod.pmod"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("mod.json", json.dumps(packaged)); archive.writestr("Runtime/ModAssembly.dll", b"MZtest")
            with patch.multiple(mod, ROOT=root, WORK=work, PACKAGE=package, EXAMPLE="hello-world"):
                with self.assertRaisesRegex(ValueError, "differs"):
                    mod.check(SimpleNamespace(release=True, mods_dir=None))


if __name__ == "__main__":
    unittest.main()
