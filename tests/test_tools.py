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
from runtime_test import config_entries, variant_string


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
    def test_runtime_log_must_match_current_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); work = root / ".work"; work.mkdir(); (root / "mod").mkdir()
            package = root / "dist/test.pmod"; package.parent.mkdir()
            m = {"id": "test.hello", "schemaVersion": 3, "runtimeApiVersion": 1,
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
            manifest = {"runtimeAssembly": "Runtime/ModAssembly.dll", "resources": []}
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


if __name__ == "__main__":
    unittest.main()
