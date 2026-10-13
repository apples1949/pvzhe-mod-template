"""Run the released executable with an isolated user directory via a local PCK copy.

Only project settings and a test-only GDScript driver are added to the local copy.
The driver presses the loading screen's existing StartButton and captures the UI.
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import uuid
from pathlib import Path
from pck import Pack
from mod import check_package, sha

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".work"


def config_entries(data):
    if data[:4] != b"ECFG":
        raise ValueError("Unsupported project.binary")
    count = struct.unpack_from("<I", data, 4)[0]
    position, entries = 8, {}
    for _ in range(count):
        length = struct.unpack_from("<I", data, position)[0]; position += 4
        key = data[position:position + length].decode(); position += length
        length = struct.unpack_from("<I", data, position)[0]; position += 4
        entries[key] = data[position:position + length]; position += length
    if position != len(data):
        raise ValueError("Unexpected project.binary trailing data")
    return entries


def variant_string(text):
    data = text.encode()
    return struct.pack("<II", 4, len(data)) + data + b"\0" * (-len(data) % 4)


def test():
    if os.name != "nt":
        raise ValueError("Runtime test currently supports Windows release only")
    evidence = json.loads((WORK / "release.json").read_text(encoding="utf-8"))
    if sha(evidence["pck"]) != evidence["pckSha256"]:
        raise ValueError("Released PCK changed; prepare and build again")
    pack = Pack(evidence["pck"])
    if pack.version != 4:
        raise ValueError("Runtime test PCK patch supports v4 only")
    entries = config_entries(pack.read("project.binary"))
    name = "PVZHE Mod Template Test " + uuid.uuid4().hex[:12]
    entries["application/config/name"] = variant_string(name)
    entries["application/config/use_custom_user_dir"] = struct.pack("<II", 1, 0)
    driver_name = "ModTemplateTestDriver.gd"
    entries["autoload/ModTemplateTestDriver"] = variant_string("*res://" + driver_name)
    driver = b'''extends Node
var elapsed := 0.0
var started := false
var captured := false
func _process(delta):
    elapsed += delta
    if elapsed < 12.0:
        return
    if not started:
        var button = get_tree().root.find_child("StartButton", true, false)
        if button is Button and button.is_visible_in_tree() and not button.disabled:
            started = true
            print("[TemplateTest] pressing existing loading StartButton")
            button.emit_signal("pressed")
    var banner = get_tree().root.find_child("HelloModBanner", true, false)
    if banner is Label and banner.is_visible_in_tree() and not captured:
        captured = true
        capture.call_deferred()
func capture():
    await get_tree().create_timer(4.0).timeout
    await RenderingServer.frame_post_draw
    var result = get_viewport().get_texture().get_image().save_png("user://hello-world.png")
    print("[TemplateTest] visible banner screenshot result=", result)
    await get_tree().create_timer(2.0).timeout
    get_tree().quit()
'''
    data = b"ECFG" + struct.pack("<I", len(entries))
    for key, value in entries.items():
        k = key.encode()
        data += struct.pack("<I", len(k)) + k + struct.pack("<I", len(value)) + value
    target = WORK / "runtime" / pack.path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(pack.path, target)
    with target.open("r+b") as f:
        f.seek(24); base = struct.unpack("<Q", f.read(8))[0]
        f.seek(0, 2); new_offset = f.tell(); f.write(data)
        driver_offset = f.tell(); f.write(driver)
        directory = f.tell()
        f.write(struct.pack("<I", len(pack.entries) + 1))
        for key, info in pack.entries.items():
            k = ("res://" + key).encode(); k += b"\0" * (-len(k) % 4)
            offset, size, md5 = info["offset"], info["size"], bytes.fromhex(info["md5"])
            if key == "project.binary":
                offset, size, md5 = new_offset, len(data), hashlib.md5(data).digest()
            f.write(struct.pack("<I", len(k)) + k + struct.pack("<QQ", offset - base, size) + md5 + struct.pack("<I", 0))
        k = ("res://" + driver_name).encode(); k += b"\0" * (-len(k) % 4)
        f.write(struct.pack("<I", len(k)) + k + struct.pack("<QQ", driver_offset - base, len(driver))
                + hashlib.md5(driver).digest() + struct.pack("<I", 0))
        f.seek(32); f.write(struct.pack("<Q", directory))
    # Reparse/check the patched entry before starting the host.
    if Pack(target).read("project.binary") != data:
        raise ValueError("Test pack verification failed")
    userdata = Path(os.environ["APPDATA"]) / "Godot/app_userdata" / name
    (WORK / "runtime/userdata-path.txt").write_text(str(userdata), encoding="utf-8")
    mods = userdata / "Mods"
    mods.mkdir(parents=True, exist_ok=True)
    package = ROOT / "dist/hello-world.pmod"
    check_package(package)
    shutil.copyfile(package, mods / package.name)
    manifest = json.loads((ROOT / "mod/mod.json").read_text(encoding="utf-8"))
    state = mods / "enabled_mods.json"
    previous = state.read_bytes() if state.exists() else None
    log = WORK / "runtime/game.log"
    original_exe = Path(evidence["pck"]).with_suffix(".exe")
    if not original_exe.exists():
        raise FileNotFoundError("Expected game executable beside PCK with same basename")
    exe = target.with_suffix(".exe")
    shutil.copyfile(original_exe, exe)
    for folder in original_exe.parent.glob("data_*"):
        if folder.is_dir():
            for dll, identity in evidence["assemblies"].items():
                source = folder / dll
                if source.exists() and sha(source) != identity["sha256"]:
                    raise ValueError(f"Released assembly changed: {dll}; prepare and build again")
            shutil.copytree(folder, target.parent / folder.name, dirs_exist_ok=True)
    try:
        state.write_text(json.dumps({"schemaVersion": 2, "enabledIds": [manifest["id"]], "preferredOrder": [manifest["id"]]}), encoding="utf-8")
        if log.exists():
            log.unlink()
        command = [str(exe), "--rendering-driver", "opengl3", "--windowed", "--resolution", "800x450",
                   "--quit-after", "2700", "--log-file", str(log)]
        print("Test driver presses the existing loading StartButton, captures the banner, then exits.", flush=True)
        print("Starting released game with isolated data:", userdata, flush=True)
        with (WORK / "runtime/stdout.log").open("w", encoding="utf-8") as output:
            subprocess.run(command, cwd=exe.parent, stdout=output, stderr=subprocess.STDOUT, timeout=120, check=True)
        subprocess.run([sys.executable, str(ROOT / "tools/mod.py"), "verify", "--log", str(log)], cwd=ROOT, check=True)
        screenshot = userdata / "hello-world.png"
        if screenshot.exists():
            shutil.copyfile(screenshot, ROOT / "dist/hello-world.png")
    finally:
        if previous is None:
            state.unlink(missing_ok=True)
        else:
            state.write_bytes(previous)


if __name__ == "__main__":
    lock = WORK / "runtime/test.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit("Another runtime test is active. If interrupted, confirm the test process exited before removing .work/runtime/test.lock.")
    try:
        test()
    finally:
        os.close(handle)
        lock.unlink(missing_ok=True)
