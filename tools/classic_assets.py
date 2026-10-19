"""Classic PopCap PAK research and raw reanim export; separate from Godot PCK.

No source paths or character names are built in. Generated game assets stay local.
"""
import argparse
import hashlib
import json
import math
import re
import struct
import zlib
from pathlib import Path, PurePosixPath


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_path(name):
    name = name.replace("\\", "/")
    p = PurePosixPath(name)
    if not name or p.is_absolute() or any(x in ("..", ".") or ":" in x for x in name.split("/")):
        raise ValueError("Unsafe archive path: " + name)
    return str(p)


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError("Truncated binary at " + str(self.pos))
        result = self.data[self.pos:self.pos+n]
        self.pos += n
        return result

    def unpack(self, fmt):
        return struct.unpack("<"+fmt, self.take(struct.calcsize("<"+fmt)))

    def string(self):
        return self.take(self.unpack("I")[0]).decode("utf-8").rstrip("\0")


class Pak:
    """Version-0, uncompressed-entry PAK, with optional whole-file XOR F7."""
    def __init__(self, path):
        original = Path(path).read_bytes()
        self.sha256 = digest(original)
        self.data = original
        if original[:4] == bytes.fromhex("37bd374d"):
            self.data = original.translate(bytes(x ^ 247 for x in range(256)))
        r = Reader(self.data)
        if r.unpack("II") != (0xBAC04AC0, 0):
            raise ValueError("Unsupported PAK header/version (not a Godot PCK)")
        entries = []
        seen = set()
        while True:
            flag = r.unpack("B")[0]
            if flag == 0x80:
                break
            if flag != 0:
                raise ValueError("Unsupported PAK directory flag")
            name = safe_path(r.take(r.unpack("B")[0]).decode("gbk"))
            size = r.unpack("I")[0]
            r.take(8)  # source FILETIME
            if name.lower() in seen:
                raise ValueError("Duplicate case-insensitive PAK path: " + name)
            seen.add(name.lower())
            entries.append((name, size))
        self.entries = {}
        for name, size in entries:
            self.entries[name.lower()] = (name, r.pos, size)
            r.take(size)
        if r.pos != len(self.data):
            raise ValueError("PAK size mismatch; compressed-entry variants need another decoder")

    def read(self, name):
        name, pos, size = self.entries[safe_path(name).lower()]
        return self.data[pos:pos+size]

    def extract(self, names, directory):
        records = []
        for name in names:
            canonical = self.entries[safe_path(name).lower()][0]
            data = self.read(canonical)
            target = Path(directory) / canonical
            # Also reject an existing symlink/junction escaping the output root.
            if not target.resolve().is_relative_to(Path(directory).resolve()):
                raise ValueError("Extraction path escapes output")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            records.append({"path": canonical, "sha256": digest(data), "size": len(data)})
        return records


def strings(data, encoding="gbk"):
    text = data.decode(encoding)  # strict: never silently remove Chinese characters
    return [(m.group(1), m.group(2).strip()) for m in re.finditer(r"^\[([^\]\r\n]+)\]\s*([^\[]*)", text, re.M)]


def research(pak, properties, name, encoding="gbk"):
    sources, matches = [], []
    for path in sorted(Path(properties).glob("*.txt")):
        data = path.read_bytes()
        blocks = strings(data, encoding)
        exact = [key for key, value in blocks if value.strip() == name]
        if not exact:
            continue
        sources.append({"file": path.name, "sha256": digest(data), "encoding": encoding,
                        "inPak": "properties/"+path.name.lower() in pak.entries,
                        "sameAsPak": (pak.read("properties/"+path.name) == data)
                        if "properties/"+path.name.lower() in pak.entries else None})
        for key in exact:
            candidates = [v[0] for k, v in pak.entries.items()
                          if PurePosixPath(k).name == key.lower()+".reanim.compiled"]
            matches.append({"key": key, "source": path.name,
                            "blocks": dict((k,v) for k,v in blocks if k == key or k.startswith(key+"_")),
                            "animationCandidates": candidates,
                            "mappingEvidence": "exact localized value -> key -> exact filename stem; inspect tracks before accepting"})
    return {"schemaVersion": 1, "pakSha256": pak.sha256, "query": name,
            "sources": sources, "matches": matches}


def decode_reanim(data):
    r = Reader(data)
    magic, size = r.unpack("II")
    if magic != 0xDEADFED4:
        raise ValueError("Unsupported reanim compiled header")
    raw = zlib.decompress(r.take(len(data)-8))
    if len(raw) != size:
        raise ValueError("Reanim decompressed length mismatch")
    r = Reader(raw)
    r.take(8)
    count, fps = r.unpack("If")
    r.take(4)
    if r.unpack("I")[0] != 12 or not (0 < count < 65535 and math.isfinite(fps) and fps > 0):
        raise ValueError("Unsupported reanim track table")
    counts = []
    for _ in range(count):
        r.take(8)
        counts.append(r.unpack("I")[0])
    tracks = []
    for count in counts:
        name = r.string()
        if r.unpack("I")[0] != 44 or count > len(raw)//44:
            raise ValueError("Unsupported reanim transform records")
        frames = []
        for _ in range(count):
            values = r.unpack("8f")
            if not all(math.isfinite(v) for v in values):
                raise ValueError("Non-finite transform")
            frames.append({k:v for k,v in zip(("x","y","kx","ky","sx","sy","f","a"),values) if abs(v+10000) >= .001})
            r.take(12)
        for frame in frames:
            for key in ("image", "font", "text"):
                value = r.string()
                if value:
                    frame[key] = value
        tracks.append({"name": name, "transforms": frames})
    if r.pos != len(raw):
        raise ValueError("Unexpected reanim trailer")
    return {"fps": fps, "tracks": tracks}


def resolved(track):
    state = dict(x=0., y=0., kx=0., ky=0., sx=1., sy=1., f=0., a=1.)
    for frame in track["transforms"]:
        state.update(frame)
        yield dict(state)


def inspect_animation(doc):
    tracks = []
    images = set()
    for track in doc["tracks"]:
        frames = list(resolved(track))
        images.update(f["image"] for f in frames if "image" in f)
        visible = [i for i,f in enumerate(frames) if f["f"] >= 0]
        tracks.append({"name":track["name"], "frames":len(frames),
                       "activeBoundsInclusive": [min(visible),max(visible)] if visible else None,
                       "hasImage":any("image" in f for f in frames)})
    return {"fps":doc["fps"], "tracks":tracks, "images":sorted(images)}


def image_candidates(image):
    if not image.startswith("IMAGE_REANIM_"):
        return []
    stem = image[len("IMAGE_REANIM_"):].lower()
    return ["reanim/"+stem+ext for ext in (".png", ".jpg", ".gif", ".tga")]


def export_bundle(pak, animation, output):
    data = pak.read(animation)
    doc = decode_reanim(data)
    info = inspect_animation(doc)
    mapping, missing = {}, []
    names = [animation]
    for image in info["images"]:
        found = [p for p in image_candidates(image) if p in pak.entries]
        if len(found) != 1:
            missing.append({"image":image, "candidates":found})
        else:
            mapping[image] = pak.entries[found[0]][0]
            names.append(found[0])
    records = pak.extract(sorted(set(names)), Path(output)/"files")
    write_json(Path(output)/"raw-reanim.json", doc)
    manifest = {"schemaVersion":1,"pakSha256":pak.sha256,"animation":animation,
                "animationSha256":digest(data),"inspection":info,"imageMap":mapping,
                "unresolvedImages":missing,"files":records}
    write_json(Path(output)/"bundle.json",manifest)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pak", required=True)
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("index"); s.add_argument("--out", required=True)
    s = sub.add_parser("research"); s.add_argument("--properties", required=True); s.add_argument("--name", required=True); s.add_argument("--encoding", default="gbk"); s.add_argument("--out", required=True)
    s = sub.add_parser("extract"); s.add_argument("--path", nargs="+", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("bundle"); s.add_argument("--animation", required=True); s.add_argument("--out", required=True)
    a = p.parse_args(); pak = Pak(a.pak)
    if a.command == "index":
        result = {"pakSha256":pak.sha256,"files":[{"path":v[0],"size":v[2]} for v in pak.entries.values()]}
        write_json(Path(a.out),result)
    elif a.command == "research":
        result = research(pak,a.properties,a.name,a.encoding); write_json(Path(a.out),result)
    elif a.command == "extract":
        result = {"pakSha256":pak.sha256,"files":pak.extract(a.path,a.out)}; write_json(Path(a.out)/"extraction.json",result)
    else:
        result = export_bundle(pak,a.animation,a.out)
        if result["unresolvedImages"]:
            raise ValueError("Unresolved image IDs; inspect bundle.json before conversion")
    print(json.dumps({"command":a.command,"pakSha256":pak.sha256,"output":a.out},ensure_ascii=False))


if __name__ == "__main__":
    main()
