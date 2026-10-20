"""Build an isolated audit assembly; never put verification code in the example DLL."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import mod
from runtime_test import test

START_DRIVER = '''extends Node
var started = false
func _ready():
    process_mode = Node.PROCESS_MODE_ALWAYS
func _process(_delta):
    if started: return
    var button = get_tree().root.find_child("StartButton",true,false)
    if button is BaseButton and button.is_visible_in_tree() and not button.disabled:
        started = true
        button.emit_signal("pressed")
'''

NORMAL_DRIVER = START_DRIVER + '''
var accepted = false
var launched = false
var capturing = false
var handled_pauses = []
func _physics_process(_delta):
    var root = get_tree().root
    var pause = root.find_child("DialogBoxGamePause",true,false)
    if pause != null and not handled_pauses.has(pause.get_instance_id()):
        handled_pauses.append(pause.get_instance_id())
        if handled_pauses.size() > 4:
            print("AUDIT_TEST_ERROR: repeated environment pause")
            get_tree().quit(2)
            return
        get_window().grab_focus()
        pause.call("CloseDialog")
        print("SUPER_ENV_PAUSE: known normal-start pause closed")
    var profile = root.find_child("DialogBoxNewUser",true,false)
    if not accepted and profile != null and profile.get("nameLineEdit") != null:
        profile.get("nameLineEdit").text = "SuperNormalAudit"
        profile.get("readyButtonNewUser").emit_signal("pressed")
        accepted = true
    var button = root.find_child("SuperGatlingLaunch",true,false)
    if accepted and profile == null and not launched and button is BaseButton and button.is_visible_in_tree():
        launched = true
        launch.call_deferred(button)
    if launched and not capturing and root.find_child("TowerDefenseInGameSeedBank",true,false) != null:
        capturing = true
        capture.call_deferred()
func launch(button):
    await get_tree().create_timer(0.5,true,false,true).timeout
    button.emit_signal("pressed")
func capture():
    await get_tree().create_timer(3.0,true,false,true).timeout
    await RenderingServer.frame_post_draw
    get_viewport().get_texture().get_image().save_png("user://super-normal.png")
    print("SUPER_NORMAL_PACKAGE_PASS: no Mod test flags; normal experience entry reached")
    get_tree().quit()
'''


def run(case):
    base = ROOT / ".work" / "super-gatling-verification"
    base.mkdir(parents=True, exist_ok=True)
    lock = base / "test.lock"
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit("Verification already active; do not rebuild/replace its inputs.")
    try:
        run_dir = base / (case + "-" + uuid.uuid4().hex[:8])
        build_dir = run_dir / "build"
        build_dir.mkdir(parents=True)
        mod.select_example("super-gatling")
        if case == "normal":
            subprocess.run([sys.executable, str(ROOT / "tools/mod.py"), "build", "--example", "super-gatling"], check=True)
            package = mod.PACKAGE
            markers = ["SUPER_NORMAL_PACKAGE_PASS:"]
            driver, arguments = NORMAL_DRIVER, ()
        else:
            refs = ROOT / ".work" / "references"
            files = list(EXAMPLE.glob("*.cs")) + [EXAMPLE / "Verification" / (("Picker" if case == "native" else "Core" if case in ("death", "cadence") else case.title()) + ".cs")]
            # Immutable source snapshot: the running package never depends on live edits.
            for source in files:
                shutil.copyfile(source, build_dir / source.name)
            project = build_dir / "Audit.csproj"
            project.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net9.0</TargetFramework><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings><AssemblyName>SuperGatlingAudit</AssemblyName></PropertyGroup><ItemGroup>' + ''.join(
                f'<Reference Include="{name}"><HintPath>{escape(str(refs / (name + ".dll")))}</HintPath><Private>false</Private></Reference>' for name in ("PlantsVsZombies", "GodotSharp")) + '</ItemGroup></Project>', encoding="utf-8")
            subprocess.run(["dotnet", "build", str(project), "-c", "Release", "--nologo"], check=True)
            manifest = json.loads((EXAMPLE / "mod/mod.json").read_text(encoding="utf-8"))
            level = json.loads((EXAMPLE / "mod/Assets/level.json").read_text(encoding="utf-8"))
            for feature in level["Feature"]:
                if feature["Name"] == "Wave":
                    for wave in feature["Data"]["Wave"]:
                        for spawn in wave["Spawn"]: spawn["Line"] = 5
                if case in ("picker", "native") and feature["Name"] == "SeedBank":
                    feature["Data"].update(Method="CHOOSE", Packet=[])
            package = build_dir / "super-gatling-pea.pmod"
            with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("mod.json", json.dumps(manifest, ensure_ascii=False))
                archive.write(build_dir / "bin/Release/net9.0/SuperGatlingAudit.dll", "Runtime/ModAssembly.dll")
                for resource in manifest["resources"]:
                    if resource == "Assets/level.json": archive.writestr(resource, json.dumps(level, ensure_ascii=False))
                    else: archive.write(EXAMPLE / "mod" / resource, resource)
            mod.check_package(package)
            markers = {
                "core": ["SUPER_CARD_PASS:", "SUPER_NORMAL:", "SUPER_MUZZLE_PASS:", "SUPER_TRAJECTORY_PASS:", "SUPER_POWER_PASS:", "AUDIT_DISCOVERY_DONE:"],
                "picker": ["SUPER_AUTO_POOL_PASS:", "SUPER_DAMAGE_PASS:", "SUPER_DEATH_PASS:", "SUPER_PICKER_PASS:", "SUPER_NATIVE_LEVEL_PASS:", "AUDIT_DISCOVERY_DONE:"],
                "native": ["SUPER_NATIVE_LEVEL_PASS:", "AUDIT_DISCOVERY_DONE:"],
                "death": ["SUPER_POWER_DEATH_PASS:", "AUDIT_DISCOVERY_DONE:"],
                "guidance": ["SUPER_GUIDANCE_PASS:", "AUDIT_DISCOVERY_DONE:"],
                "cadence": ["SUPER_POWER_PASS:", "SUPER_TRAJECTORY_PASS:", "AUDIT_DISCOVERY_DONE:"],
                "animation": ["SUPER_ANIMATION_IDLE_PASS:", "SUPER_ANIMATION_NEGATIVE_PASS:", "SUPER_ANIMATION_FIRE_PASS:", "SUPER_ANIMATION_POWER_PASS:", "AUDIT_DISCOVERY_DONE:"]
            }[case]
            driver, arguments = START_DRIVER, (("--skill-audit", "--native-only") if case == "native" else ("--skill-audit", "--power-death-only") if case == "death" else ("--skill-audit", "--power-cadence-only") if case == "cadence" else ("--skill-audit",))
        result = test("super-gatling", driver_code=driver, package_path=package, runtime_dir=run_dir / "runtime",
                      user_args=arguments, required_markers=markers)
        if case == "animation":
            images = subprocess.run([sys.executable, str(EXAMPLE / "verify_animation_frames.py"),
                                     "--runtime", str(result)])
            mod.write_json(result / "verification-summary.json", {
                "passed": images.returncode == 0,
                "runtimeAssessment": "assessment.json", "imageAssessment": "image-assessment.json"})
            images.check_returncode()
        print("Verification evidence:", result)
    finally:
        os.close(handle)
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("core", "cadence", "guidance", "death", "picker", "native", "animation", "normal"))
    run(parser.parse_args().case)
