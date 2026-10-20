"""Prepare this example from the player's own SuperGatling PAK (requires Pillow)."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from classic_assets import Pak, export_bundle, research, resolved
from reanim_dat import convert

EXPECTED_CLIPS = {"anim_idle": [0, 25], "anim_head_idle": [25, 50], "anim_shooting": [50, 75], "anim_power": [75, 87]}


def prepare(pak_path):
    pak = Pak(pak_path)
    cache = ROOT / ".work" / "super-gatling-assets" / pak.sha256
    properties = cache / "properties"
    pak.extract(["properties/NewPlantStrings.txt"], properties)
    info = research(pak, properties / "properties", "超级机枪射手", "gbk")
    matches = [entry for entry in info["matches"] if entry["key"] == "SUPERGATLING"]
    if len(matches) != 1 or "compiled/new/SuperGatling.reanim.compiled" not in matches[0]["animationCandidates"]:
        raise ValueError("This PAK does not match the example's localized SuperGatling identity.")
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "research.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    bundle = cache / "bundle"
    export_bundle(pak, "compiled/new/SuperGatling.reanim.compiled", bundle)
    raw = json.loads((bundle / "raw-reanim.json").read_text(encoding="utf-8"))
    stem = next(t for t in raw["tracks"] if t["name"] == "anim_idle")
    reference = next(resolved(stem))
    if any(abs(reference[key] - expected) > .0001 for key, expected in
           {"x": 37.6, "y": 48.7, "kx": 0, "ky": 0, "sx": 1, "sy": 1}.items()):
        raise ValueError("Stem reference changed; adapt the example's attachment transform before using this PAK.")
    converted = cache / "generated"
    result = convert(bundle, converted)
    if any(result["clipsHalfOpen"].get(name) != bounds for name, bounds in EXPECTED_CLIPS.items()):
        raise ValueError("Source animation segments differ. Adapt AnimationData.cs before using this PAK; no asset installed.")
    target = Path(__file__).resolve().parent / "mod" / "Assets" / "animation.dat"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(converted / "animation.dat", target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == result["datSha256"]
    print(json.dumps({"asset": str(target), "datSha256": result["datSha256"], "pakSha256": pak.sha256,
                      "evidence": str(cache)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pak", required=True, help="User-owned classic/hybrid PAK, not the target PCK")
    args = parser.parse_args()
    prepare(args.pak)
