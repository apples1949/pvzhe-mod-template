"""Prepare local release-bound assets, reusing the PCK/DLL hash cache."""
import argparse
import os
import re
import json
from pathlib import Path
import shutil
import subprocess
import uuid
from xml.sax.saxutils import escape
import zipfile
from attack_model import file_sha, save, grid_row_y
from attack_plan import default_plan
from game_cache import GameCache
from runtime_test import test

ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = "Asset/Texture/TowerDefense/Background/TowerDefenseMap/Frontlawn/Frontlawn.jpg"
DRIVER = '''extends Node
var started = false
func _process(_delta):
    if started: return
    var button = get_tree().root.find_child("StartButton",true,false)
    if button is BaseButton and button.is_visible_in_tree() and not button.disabled:
        started = true
        button.emit_signal("pressed")
'''


def _prepare(output, plant="PlantPeaShooterSingle", target="ZombieNormal"):
    work = ROOT / ".work"
    release = json.loads((work / "release.json").read_text(encoding="utf-8"))
    cache = GameCache(work, release)
    # Verify that this version still has the map input before starting the host.
    cache.fetch([BACKGROUND], dependencies=True)
    settings = dict(background="res://"+BACKGROUND, plant=plant, target=target)
    source = ROOT / "tools/AttackPreviewCapture/Entry.cs"
    import hashlib
    source_files = sorted(source.parent.glob("*.cs"))+[source.parent/"level.json"]
    source_identity = {p.name: file_sha(p) for p in source_files}
    key = hashlib.sha256((json.dumps(settings, sort_keys=True)+json.dumps(source_identity, sort_keys=True)).encode()).hexdigest()
    assets = cache.root / "attack-preview" / key
    manifest_path = assets / "assets.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, item in manifest["assets"].items():
            if file_sha(assets / item["path"]) != item["sha256"]:
                raise ValueError("Cached preview image changed: "+name)
    else:
        run = work / "attack-preview" / ("capture-"+uuid.uuid4().hex[:8])
        run.mkdir(parents=True)
        for p in source_files: shutil.copyfile(p, run/p.name)
        refs = work / "references"
        project = run / "Capture.csproj"
        project.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net9.0</TargetFramework><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings></PropertyGroup><ItemGroup>'+''.join(
            f'<Reference Include="{name}"><HintPath>{escape(str(refs/(name+".dll")))}</HintPath><Private>false</Private></Reference>' for name in ("PlantsVsZombies", "GodotSharp"))+'</ItemGroup></Project>', encoding="utf-8")
        subprocess.run(["dotnet", "build", str(project), "-c", "Release", "--nologo"], check=True)
        package = run / "attack-preview-capture.pmod"
        manifest = dict(schemaVersion=3, id="attack-preview-capture", name="Attack asset capture", author="Template", version="0.1.0",
                        runtimeAssembly="Runtime/ModAssembly.dll", runtimeEntryType="AttackPreviewCapture.Entry", runtimeApiVersion=3,
                        runtimeAssemblyPolicy="required", resources=["capture.json", "level.json"], scripts=[], dependencies=[], contentEntries=[dict(category="Level", key="calibration")], overrides={})
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("mod.json", json.dumps(manifest))
            archive.writestr("capture.json", json.dumps(settings))
            archive.write(source.parent/"level.json", "level.json")
            archive.write(run / "bin/Release/net9.0/Capture.dll", "Runtime/ModAssembly.dll")
        runtime = test(driver_code=DRIVER, package_path=package, runtime_dir=run / "runtime", required_markers=["ATTACK_ASSETS_DONE:"])
        assets.mkdir(parents=True, exist_ok=True)
        records = {}
        from PIL import Image
        for name in ("background", "plant", "target"):
            path = assets / (name+".png")
            shutil.copyfile(runtime / path.name, path)
            with Image.open(path) as image:
                if name != "background":
                    if image.mode != "RGBA" or image.getextrema()[3][0] != 0 or image.getbbox() is None:
                        raise ValueError("Invalid transparent reference pose: "+name)
                    x0, y0, x1, y1 = image.getbbox()
                    if x0 < 2 or y0 < 2 or x1 > image.width-2 or y1 > image.height-2:
                        raise ValueError("Reference pose may be clipped; enlarge capture viewport and update imageOrigin: "+name)
            records[name] = dict(path=path.name, sha256=file_sha(path))
        log = (runtime / "game.log").read_text(encoding="utf-8")
        def metadata(marker):
            match = re.search(re.escape(marker)+r": (\{[^\r\n]+\})", log)
            if not match: raise ValueError("Missing capture geometry: "+marker)
            return json.loads(match.group(1))
        manifest = dict(assets=records, settings=settings, runtime=str(runtime), captureSourceSha256=file_sha(source),
                        grid=metadata("ATTACK_GRID"), plantGeometry=metadata("ATTACK_GEOMETRY_plant"), targetGeometry=metadata("ATTACK_GEOMETRY_target"),
                        baseline=metadata("ATTACK_BASELINE"), nativeHitBox=metadata("ATTACK_NATIVE_HITBOX"), sourceFiles=source_identity)
        save(manifest_path, manifest)
    output = Path(output).resolve()
    if output.exists(): raise ValueError("Use a new session path")
    records = {name: dict(item, path=str(assets/item["path"])) for name, item in manifest["assets"].items()}
    grid = manifest["grid"]
    row = 3
    plant_y = grid_row_y(grid, row, plant=True)
    target_y = grid_row_y(grid, row)
    baseline = dict(manifest["baseline"], measuredAttackInterval=manifest["baseline"]["attackInterval"],
                    attackInterval=manifest["baseline"]["configuredInterval"], intervalPolicy="nominal-config",
                    runtime=manifest["runtime"], captureSourceFiles=manifest["sourceFiles"])
    plan=default_plan(plant,baseline["attackInterval"])
    plan["groups"][0]["items"][0]["trajectory"]["speed"]=baseline["bulletSpeed"]
    plan["reference"]={"releaseCacheKey":cache.key}
    config = dict(schemaVersion=3, sessionId=uuid.uuid4().hex, canvas=[1080, 600], assets=records,
                  backgroundCrop=[0, 0, 1080, 600],
                  grid=grid,
                  baseline=baseline,
                  provenance=dict(releaseCacheKey=cache.key, release=cache.identity, capture=manifest),
                  plant=dict(key=plant, position=[grid["begin"][0]+grid["size"][0]*.5, plant_y], imageOrigin=[128, 190]),
                  target=dict(key=target, position=[830, target_y], imageOrigin=[128, 190], aimOffset=[0, 0], speed=0, hitBoxRect=manifest["targetGeometry"]["hitBoxRect"]),
                  binding=dict(space="plant-reference-pose", nodePath=None, requiresRuntimeBinding=True), plan=plan)
    save(output, config)
    print("Prepared session:", output)
    return config


def prepare(output, plant="PlantPeaShooterSingle", target="ZombieNormal"):
    lock = ROOT / ".work/attack-preview/capture.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("Asset preparation already running; do not overlap shared host capture")
    try:
        return _prepare(output, plant, target)
    finally:
        os.close(handle)
        lock.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--plant-key", default="PlantPeaShooterSingle")
    parser.add_argument("--target-key", default="ZombieNormal")
    args = parser.parse_args()
    prepare(args.output, args.plant_key, args.target_key)
