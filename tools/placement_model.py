"""Validated placement sessions, independent of Tk and game APIs."""
import copy
import hashlib
import json
import math
from pathlib import Path
import time
import uuid


def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Invalid {name}: {value!r}")
    return value


def rectangle(item, width, height):
    w = number(item.get("width"), "width", 20, width)
    h = number(item.get("height"), "height", 20, height)
    number(item.get("x"), "x", 0, width-w)
    number(item.get("y"), "y", 0, height-h)


class Session:
    def __init__(self, config, base=None, resume=None):
        if not isinstance(config, dict):
            raise ValueError("Configuration must be an object")
        provenance = config.get("context", {}).get("previewProvenance")
        if provenance:
            from game_cache import GameCache, sha
            work = Path(provenance["workDir"])
            release = json.loads((work / "release.json").read_text(encoding="utf-8"))
            cache = GameCache(work, release)
            if cache.key != provenance["releaseCacheKey"] or sha(provenance["modAssembly"]) != provenance["modAssemblySha256"]:
                raise ValueError("Preview belongs to an old release/component build; recapture before use")
        self.config = copy.deepcopy(config)
        self.base = Path(base or ".").resolve()
        if config.get("schemaVersion") != 1 or not isinstance(config.get("layouts"), list) or not config["layouts"]:
            raise ValueError("Expected schemaVersion=1 and non-empty layouts")
        self.asset_hashes = {}
        for layout in config["layouts"]:
            if not isinstance(layout, dict) or not isinstance(layout.get("objects"), list) or not all(isinstance(item, dict) for item in layout["objects"]):
                raise ValueError("Each layout must contain an objects array")
            paths = [layout.get("background"), *(item.get("image") for item in layout.get("objects", []))]
            for image in paths:
                if image and image not in self.asset_hashes:
                    digest = hashlib.sha256()
                    with self.asset(image).open("rb") as stream:
                        for chunk in iter(lambda: stream.read(65536), b""):
                            digest.update(chunk)
                    self.asset_hashes[image] = digest.hexdigest()
        identity = dict(config=config, assets=self.asset_hashes)
        self.fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        self.layouts = copy.deepcopy(config["layouts"])
        keys = set()
        for layout in self.layouts:
            key = layout.get("id")
            if not isinstance(key, str) or not key or key in keys:
                raise ValueError("Layout ids must be unique non-empty strings")
            keys.add(key)
            canvas = layout.get("canvas", {})
            width = number(canvas.get("width"), "canvas width", 100, 4096)
            height = number(canvas.get("height"), "canvas height", 100, 4096)
            if not isinstance(width, int) or not isinstance(height, int):
                raise ValueError("Canvas dimensions must be integers")
            if not isinstance(layout.get("objects"), list) or not layout["objects"]:
                raise ValueError("Each layout needs objects")
            ids = set()
            for item in layout["objects"]:
                ident = item.get("id")
                if not isinstance(ident, str) or not ident or ident in ids:
                    raise ValueError("Object ids must be unique within a layout")
                ids.add(ident)
                rectangle(item, width, height)
                number(item.get("imagePadding", 0), "imagePadding", 0, 128)
                item.setdefault("text", ident)
            for region in layout.get("regions", []):
                rectangle(region, width, height)
        self.original = copy.deepcopy(self.layouts)
        self.active = self.layouts[0]["id"]
        self.changed = False
        self.visited = set()
        self.id = uuid.uuid4().hex
        if resume is not None:
            self.restore(resume)

    @classmethod
    def load(cls, path, resume=None):
        path = Path(path).resolve()
        config = json.loads(path.read_text(encoding="utf-8-sig"))
        previous = json.loads(Path(resume).read_text(encoding="utf-8")) if resume else None
        return cls(config, path.parent, previous)

    @property
    def layout(self):
        return next(layout for layout in self.layouts if layout["id"] == self.active)

    def asset(self, path):
        if not isinstance(path, str) or not path:
            raise ValueError("Image path must be a non-empty string")
        result = (self.base / path).resolve()
        if not result.is_file():
            raise ValueError(f"Missing local image: {result}")
        return result

    def select(self, key):
        if key not in {layout["id"] for layout in self.layouts}:
            raise ValueError("Unknown layout")
        self.active = key
        self.visited.add(key)

    def update(self, ident, **values):
        item = next(item for item in self.layout["objects"] if item["id"] == ident)
        candidate = dict(item, **values)
        rectangle(candidate, self.layout["canvas"]["width"], self.layout["canvas"]["height"])
        item.update(values)
        self.changed = True

    def reset(self):
        original = next(layout for layout in self.original if layout["id"] == self.active)
        self.layout["objects"] = copy.deepcopy(original["objects"])
        self.changed = True

    def restore(self, result):
        if result.get("configSha256") != self.fingerprint:
            raise ValueError("Resume belongs to a different configuration; prepare a new session")
        previous = result.get("layouts", [])
        if [l.get("id") for l in previous] != [l["id"] for l in self.layouts]:
            raise ValueError("Resume layout mismatch")
        for layout, draft in zip(self.layouts, previous):
            if [o.get("id") for o in draft.get("objects", [])] != [o["id"] for o in layout["objects"]]:
                raise ValueError("Resume object mismatch")
            self.active = layout["id"]
            for item in draft["objects"]:
                self.update(item["id"], **{k: item[k] for k in ("x", "y", "width", "height")})
        self.active = result.get("activeLayout", self.layouts[0]["id"])
        self.select(self.active)
        self.visited = set()
        self.changed = bool(result.get("changed"))

    def result(self, status):
        if status not in ("confirmed", "cancelled", "timeout"):
            raise ValueError("Unknown feedback status")
        result = dict(schemaVersion=1, sessionId=self.id, configSha256=self.fingerprint,
            status=status, confirmed=status == "confirmed", changed=self.changed,
            placementPolicy="absolute", coordinateSpace="canvas-logical-pixels",
            context=copy.deepcopy(self.config.get("context", {})), assetSha256=dict(self.asset_hashes), activeLayout=self.active,
            visitedLayouts=sorted(self.visited), layouts=[])
        for layout in self.layouts:
            result["layouts"].append(dict(id=layout["id"], canvas=copy.deepcopy(layout["canvas"]),
                objects=[{k: item[k] for k in ("id", "text", "x", "y", "width", "height")} for item in layout["objects"]]))
        if status == "timeout":
            result["message"] = "用户还未输入（未确认）" if self.changed else "用户还未输入"
        return result


class FeedbackClock:
    def __init__(self, seconds=60, now=time.monotonic):
        number(seconds, "seconds", 1, 86400)
        self.seconds, self.now, self.deadline = seconds, now, None

    def start(self):
        if self.deadline is None:
            self.deadline = self.now() + self.seconds

    def extend(self):
        if self.deadline is not None:
            self.deadline += 60

    @property
    def remaining(self):
        return self.seconds if self.deadline is None else max(0, math.ceil(self.deadline-self.now()))


def write_result(path, result):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(path)
