"""Read standalone, unencrypted Godot PCK v2/v3/v4 without third-party packages.

Format reference: Godot core/io/file_access_pack.cpp (see docs/compatibility.md).
Does not decompile scripts, decode imported assets, or read embedded/encrypted packs.
"""
import hashlib
import struct
from pathlib import Path, PurePosixPath


def safe_path(name):
    name = name.removeprefix("res://")
    parts = name.split("/")
    if (not name or "\\" in name or ":" in name or
            any(p in ("", ".", "..") or p.endswith((".", " ")) for p in parts)):
        raise ValueError(f"Unsafe resource path: {name}")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    if any(p.split('.')[0].upper() in reserved for p in parts):
        raise ValueError(f"Reserved resource path: {name}")
    return str(PurePosixPath(name))


class Pack:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.entries = {}
        length = self.path.stat().st_size
        with self.path.open("rb") as f:
            def read(n):
                b = f.read(n)
                if len(b) != n:
                    raise ValueError("Truncated PCK")
                return b

            def u32():
                return struct.unpack("<I", read(4))[0]

            def u64():
                return struct.unpack("<Q", read(8))[0]

            if read(4) != b"GDPC":
                raise ValueError("Only standalone GDPC PCK files are supported")
            self.version = u32()
            self.engine = [u32(), u32(), u32()]
            if self.version not in (2, 3, 4):
                raise ValueError(f"Unsupported PCK version {self.version}")
            flags = u32()
            if flags & ~2:
                raise ValueError("Encrypted, sparse or unknown PCK flags are unsupported")
            base = u64()
            if self.version in (3, 4):
                directory = u64()
                if directory >= length:
                    raise ValueError("PCK directory outside file")
                f.seek(directory)
            else:
                read(64)
            count = u32()
            if count > 1000000:
                raise ValueError("Invalid PCK entry count")
            seen = set()
            for _ in range(count):
                n = u32()
                if n > 65536:
                    raise ValueError("PCK path exceeds limit")
                name = safe_path(read(n).rstrip(b"\0").decode("utf-8"))
                offset, size = u64() + base, u64()
                md5, entry_flags = read(16).hex(), u32()
                if entry_flags:
                    raise ValueError(f"Encrypted/removal/delta entry unsupported: {name}")
                if offset + size > length or name.casefold() in seen:
                    raise ValueError(f"Invalid range or duplicate PCK entry: {name}")
                seen.add(name.casefold())
                self.entries[name] = {"offset": offset, "size": size, "md5": md5}

    def read(self, name):
        name = safe_path(name)
        info = self.entries[name]
        with self.path.open("rb") as f:
            f.seek(info["offset"])
            data = f.read(info["size"])
        if len(data) != info["size"] or hashlib.md5(data).hexdigest() != info["md5"]:
            raise ValueError(f"PCK checksum mismatch: {name}")
        return data

    def extract(self, names, output):
        root = Path(output).resolve()
        for name in names:
            destination = (root / safe_path(name)).resolve()
            if not destination.is_relative_to(root):
                raise ValueError("Extraction escaped destination")
            data = self.read(name)
            if destination.exists():
                if destination.read_bytes() == data:
                    continue
                raise FileExistsError(f"Refusing to overwrite: {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
