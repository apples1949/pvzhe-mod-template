"""Hash-bound, incremental local PCK cache. Never part of the mod package."""
import hashlib
import json
from pathlib import Path
import re
from pck import Pack, safe_path

SCHEMA = 1
EXTRACTOR = "pck-cache-v1"
TEXT_TYPES = {".tscn", ".tres", ".import", ".remap", ".cfg", ".json"}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


class GameCache:
    def __init__(self, work, release, pack=None):
        self.work = Path(work).resolve()
        self.release = release
        if release.get('environmentRoot'):
            from game_environment import active
            slot, environment = active(self.work.parent)
            if Path(release['environmentRoot']).resolve() != slot or release.get('environmentFingerprint') != environment['fingerprint']:
                raise ValueError('Resource cache does not match active game environment; run prepare')
        self.pack = pack or Pack(release["pck"])
        if sha(self.pack.path) != release["pckSha256"]:
            raise ValueError("Released PCK changed; run prepare before using cached resources")
        for name, identity in release.get("assemblies", {}).items():
            if sha(self.work / "references" / name) != identity["sha256"]:
                raise ValueError(f"Changed reference: {name}; run prepare")
            origin = identity.get("origin", "")
            if origin and not origin.startswith("res://"):
                if not Path(origin).is_file() or sha(origin) != identity["sha256"]:
                    raise ValueError(f"Released assembly moved/changed: {name}; run prepare")
        self.identity = dict(pckSha256=release["pckSha256"], engine=self.pack.engine,
            pckFormat=self.pack.version, assemblies={name:item["sha256"] for name,item in release.get("assemblies", {}).items()}, extractor=EXTRACTOR)
        self.key = hashlib.sha256(json.dumps(self.identity,sort_keys=True).encode()).hexdigest()
        cache_root = Path(release['environmentRoot']) / 'resources' if release.get('environmentRoot') else self.work / 'game-cache'
        self.root = cache_root / self.key
        if not self.root.resolve().is_relative_to(cache_root.resolve()):
            raise ValueError("Cache directory escaped game-cache")
        self.files = self.root / "files"
        self.root.mkdir(parents=True,exist_ok=True)
        path = self.root / "manifest.json"
        if path.exists():
            self.manifest = json.loads(path.read_text(encoding="utf-8"))
            if self.manifest.get("schemaVersion") != SCHEMA or self.manifest.get("identity") != self.identity:
                raise ValueError("Invalid cache manifest; preserve evidence and prepare a new cache")
        else:
            self.manifest = dict(schemaVersion=SCHEMA, identity=self.identity, source=str(self.pack.path), files={}, requests={})
            save(path,self.manifest)
        index = self.root / "index.json"
        if not index.exists():
            save(index,dict(format=self.pack.version,engine=self.pack.engine,entries=self.pack.entries))
        save(self.work / "game-cache/current.json",dict(schemaVersion=SCHEMA,key=self.key,manifest=str(path)))

    def resolve(self, name):
        name = safe_path(name)
        if name in self.pack.entries:
            return [name]
        return [name+suffix for suffix in (".import", ".remap") if name+suffix in self.pack.entries]

    def destination(self, name):
        target = (self.files / safe_path(name)).resolve()
        if not target.is_relative_to(self.files):
            raise ValueError("Cache path escaped files directory")
        return target

    def fetch(self, names, dependencies=False):
        pending = [(safe_path(name), True) for name in names]
        found, missing, reused, extracted = set(), set(), 0, 0
        while pending:
            requested, required = pending.pop()
            candidates = self.resolve(requested)
            if not candidates:
                if required:
                    raise ValueError(f"Resource not indexed: {requested}")
                missing.add(requested); continue
            for name in candidates:
                if name in found: continue
                found.add(name)
                target = self.destination(name)
                expected = self.pack.entries[name]["md5"]
                if target.exists():
                    with target.open("rb") as stream:
                        actual = hashlib.file_digest(stream,"md5").hexdigest()
                    if actual != expected:
                        raise ValueError(f"Cached file changed: {name}; preserve/remove this local file before retry")
                    reused += 1
                else:
                    data = self.pack.read(name)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(data); extracted += 1
                self.manifest["files"][name] = dict(md5=expected,sha256=sha(target),size=target.stat().st_size)
                if dependencies and Path(name).suffix in TEXT_TYPES:
                    text = target.read_text(encoding="utf-8",errors="replace")
                    pending.extend((safe_path(dep),False) for dep in re.findall(r'res://([^"\s<>]+)',text))
        request_key = hashlib.sha256(json.dumps(dict(names=sorted(names),dependencies=dependencies),sort_keys=True).encode()).hexdigest()
        report = dict(paths=sorted(found),unresolved=sorted(missing),extracted=extracted,reused=reused)
        self.manifest["requests"][request_key] = report
        save(self.root / "manifest.json",self.manifest)
        return report
