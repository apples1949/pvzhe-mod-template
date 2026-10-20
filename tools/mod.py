"""Player workflow. All paths are resolved independently of the current directory."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from pck import Pack, safe_path
from game_cache import GameCache
from manifest_policy import EXAMPLE_IDS, validate_metadata

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".work"
DIST = ROOT / "dist"
PACKAGE = DIST / "hello-world.pmod"
PROBE = ROOT / "tools/HostProbe/bin/Release/net9.0/HostProbe.dll"
EXAMPLE = "hello-world"
EXAMPLE_DIRS = {"feature-lab": "FeatureLab", "super-gatling": "SuperGatling"}


def select_example(name):
    global EXAMPLE, DIST, PACKAGE
    if name != "hello-world" and name not in EXAMPLE_DIRS:
        raise ValueError(f"Unknown example: {name}")
    EXAMPLE = name
    DIST = ROOT / "dist" if name == "hello-world" else ROOT / "dist" / name
    PACKAGE = DIST / (name + ".pmod")
    path = source_root() / "mod.json"
    if path.exists():
        metadata = json.loads(path.read_text(encoding="utf-8"))
        validate_metadata(metadata)
        if metadata["id"] not in EXAMPLE_IDS:
            PACKAGE = DIST / (metadata["id"] + ".pmod")


def source_root():
    return ROOT / "mod" if EXAMPLE == "hello-world" else ROOT / "examples" / EXAMPLE_DIRS[EXAMPLE] / "mod"


def build_target():
    """Optional player project selection; bundled examples remain independent."""
    if EXAMPLE in EXAMPLE_DIRS:
        folder = EXAMPLE_DIRS[EXAMPLE]
        return ROOT / "examples" / folder / (folder + ".csproj"), folder
    config_path = ROOT / "mod-project.json"
    if not config_path.exists():
        return ROOT / "src/HelloMod/HelloMod.csproj", "HelloMod"
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if (not isinstance(config, dict) or set(config) != {"schemaVersion", "project", "assemblyName"}
            or type(config["schemaVersion"]) is not int or config["schemaVersion"] != 1):
        raise ValueError("mod-project.json requires schemaVersion=1, project and assemblyName")
    project_value, assembly = config["project"], config["assemblyName"]
    if not isinstance(project_value, str):
        raise ValueError("Project must be a repository-relative .csproj path")
    project = (ROOT / safe_path(project_value)).resolve()
    if not project.is_relative_to(ROOT.resolve()) or project.suffix.lower() != ".csproj" or not project.is_file():
        raise ValueError("Project must be an existing repository-relative .csproj file")
    if (not isinstance(assembly, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", assembly)
            or assembly.casefold() in {"godotsharp", "plantsvszombies"}):
        raise ValueError("Invalid/reserved assemblyName; use the project's AssemblyName without .dll")
    if assembly.lower().endswith(".dll"):
        raise ValueError("assemblyName must not include .dll")
    return project, assembly


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(*args, capture=False):
    result = subprocess.run([str(a) for a in args], check=False, text=True,
                            encoding="utf-8", cwd=ROOT, capture_output=capture)
    if result.returncode:
        if capture:
            print(result.stderr, file=sys.stderr)
        result.check_returncode()
    return result.stdout if capture else None


def probe_build():
    run("dotnet", "build", ROOT / "tools/HostProbe", "-c", "Release", "--nologo")


def prepare(args):
    game = Path(args.game_dir).resolve()
    packs = list(game.glob("*.pck"))
    if args.pck:
        pck = Path(args.pck).resolve()
    elif len(packs) == 1:
        pck = packs[0]
    else:
        raise ValueError("Specify --pck when the game directory does not contain exactly one PCK")
    pack = Pack(pck)
    refs = WORK / "references"
    refs.mkdir(parents=True, exist_ok=True)
    identities = {}
    for name in ("PlantsVsZombies.dll", "GodotSharp.dll"):
        matches = list(game.glob(f"data_*/{name}"))
        if len(matches) == 1:
            source = matches[0]
            shutil.copyfile(source, refs / name)
            origin = str(source)
        elif not matches:
            candidates = [p for p in pack.entries if Path(p).name == name]
            if len(candidates) != 1:
                raise ValueError(f"Cannot uniquely locate {name} in release or PCK")
            (refs / name).write_bytes(pack.read(candidates[0]))
            origin = "res://" + candidates[0]
        else:
            raise ValueError(f"Multiple release assemblies: {name}")
        identities[name] = {"origin": origin, "sha256": sha(refs / name)}
    probe_build()
    api = json.loads(run("dotnet", PROBE, refs, capture=True))
    if api["schemaVersion"] < 3 or api["runtimeApiVersion"] < 1:
        raise ValueError("Released Mod API is incompatible with this template")
    write_json(WORK / "api.json", api)
    write_json(WORK / "pck-index.json", {"format": pack.version, "engine": pack.engine, "entries": pack.entries})
    # project.binary is sufficient for later inspection of user directory settings.
    if "project.binary" in pack.entries:
        (WORK / "release").mkdir(parents=True, exist_ok=True)
        (WORK / "release/project.binary").write_bytes(pack.read("project.binary"))
    write_json(WORK / "release.json", {"gameDir": str(game), "pck": str(pck),
               "pckSha256": sha(pck), "engine": pack.engine, "pckFormat": pack.version,
               "entryCount": len(pack.entries), "assemblies": identities})
    cache = GameCache(WORK, json.loads((WORK / "release.json").read_text(encoding="utf-8")), pack)
    print(f"Resource cache initialized: {cache.root}")
    print(f"Prepared released engine {pack.engine}, PCK v{pack.version}, {len(pack.entries)} entries")
    print("Local evidence: .work/release.json, .work/api.json, .work/pck-index.json")


def verify_references():
    evidence = json.loads((WORK / "release.json").read_text(encoding="utf-8"))
    for name, item in evidence["assemblies"].items():
        if sha(WORK / "references" / name) != item["sha256"]:
            raise ValueError(f"Changed reference: {name}; run prepare again")
    return evidence


def manifest(release=False):
    m = json.loads((source_root() / "mod.json").read_text(encoding="utf-8"))
    validate_metadata(m, release=release)
    if m["runtimeAssembly"] != "Runtime/ModAssembly.dll" or m["runtimeAssemblyPolicy"] != "required":
        raise ValueError("This builder requires Runtime/ModAssembly.dll and required policy")
    if not m["id"] or not m["runtimeEntryType"]:
        raise ValueError("Missing mod ID or entry type")
    api = json.loads((WORK / "api.json").read_text(encoding="utf-8"))
    if not 2 <= m["schemaVersion"] <= api["schemaVersion"] or not 1 <= m["runtimeApiVersion"] <= api["runtimeApiVersion"]:
        raise ValueError("Manifest API/schema exceeds prepared release")
    return m


def build(args):
    m = manifest(release=getattr(args, "release", False))
    check_id_conflicts(m, args)
    verify_references()
    project, assembly = build_target()
    run("dotnet", "build", project, "-c", "Release", "--nologo")
    dll = project.parent / f"bin/Release/net9.0/{assembly}.dll"
    probe_build()
    run("dotnet", PROBE, WORK / "references", dll, m["runtimeEntryType"])
    # Explicit allowlist: never archive project/references/bin wholesale.
    files = {"mod.json": (json.dumps(m, ensure_ascii=False, indent=2) + "\n").encode(),
             m["runtimeAssembly"]: dll.read_bytes()}
    for name in m.get("resources", []):
        relative = safe_path(name)
        source = (source_root() / relative).resolve()
        if not source.is_relative_to(source_root()) or source.suffix.lower() in (".dll", ".cs", ".gd", ".exe", ".ps1"):
            raise ValueError(f"Invalid content resource: {name}")
        if relative.casefold() in {p.casefold() for p in files}:
            raise ValueError(f"Reserved/duplicate archive path: {name}")
        files[relative] = source.read_bytes()
    DIST.mkdir(parents=True, exist_ok=True)
    temp = PACKAGE.with_suffix(".tmp")
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    temp.replace(PACKAGE)
    (DIST / "verification.json").unlink(missing_ok=True)
    for screenshot in DIST.glob("*.png"):
        screenshot.unlink()
    write_json(DIST / "build-info.json", {"packageSha256": sha(PACKAGE),
               "release": verify_references(), "entries": sorted(files),
               "project": project.relative_to(ROOT).as_posix(), "assemblyName": assembly})
    check_package(PACKAGE)
    print(f"Built: {PACKAGE}")


def check_package(path, release=False):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for name in names:
            safe_path(name)
        if len({n.casefold() for n in names}) != len(names) or z.testzip():
            raise ValueError("Invalid archive paths/checksums")
        m = json.loads(z.read("mod.json"))
        validate_metadata(m, release=release)
        allowed = {"mod.json", "Runtime/ModAssembly.dll", *m.get("resources", [])}
        if set(names) != allowed or not z.read(m["runtimeAssembly"]).startswith(b"MZ"):
            raise ValueError("Unexpected files or missing managed assembly")
        return m


def check_id_conflicts(metadata, args):
    directory = getattr(args, "mods_dir", None)
    if not directory:
        return
    target = Path(directory).resolve()
    if not target.is_dir():
        raise ValueError(f"Mods directory does not exist: {target}")
    for path in sorted(target.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".pmod" or path.resolve() == PACKAGE.resolve():
            continue
        try:
            with zipfile.ZipFile(path) as archive:
                other = json.loads(archive.read("mod.json"))
            other_id = other.get("id")
            if not isinstance(other_id, str) or not other_id.strip():
                raise ValueError("missing ID")
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, AttributeError) as error:
            raise ValueError(f"Cannot inspect installed Mod ID: {path.name}: {error}") from error
        if other_id.strip().casefold() == metadata["id"]:
            if getattr(args, "allow_update", False) and path.name.casefold() == PACKAGE.name.casefold():
                continue
            raise ValueError(f"Mod ID conflict: {metadata['id']} in {path.name}; "
                             "--allow-update only permits a confirmed update of the same package filename")


def check(args):
    metadata = check_package(PACKAGE, release=getattr(args, "release", False))
    if getattr(args, "release", False):
        if metadata != manifest(release=True):
            raise ValueError("Packaged manifest differs from current mod.json; rebuild before release")
    check_id_conflicts(metadata, args)
    print(f"PASS: package metadata and contents checked: {PACKAGE}")
    if getattr(args, "release", False) and not getattr(args, "mods_dir", None):
        print("Local Mod ID conflicts not checked; use --mods-dir. Global uniqueness is not verified.")


def install(args):
    check_package(PACKAGE)
    target = Path(args.mods_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    dest = target / PACKAGE.name
    if dest.exists() and sha(dest) != sha(PACKAGE):
        backup = dest.with_name(dest.name + "." + sha(dest)[:12] + ".bak")
        if not backup.exists():
            shutil.copyfile(dest, backup)
    shutil.copyfile(PACKAGE, dest)
    print(f"Installed: {dest}\nEnable in game Mod management, then restart.")


def verify(args):
    if EXAMPLE not in ("hello-world", "feature-lab"):
        raise ValueError("This example requires its documented functional verification; built-in log markers cover Hello World/FeatureLab only.")
    check_package(PACKAGE)
    log = Path(args.log).read_text(encoding="utf-8", errors="replace")
    m = manifest()
    start = log.rfind(f"[Mod:{m['id']}] HELLO_INIT:")
    if start < 0:
        raise ValueError("Missing runtime initialization")
    log = log[start:]
    with zipfile.ZipFile(PACKAGE) as archive:
        binary_sha = hashlib.sha256(archive.read(m["runtimeAssembly"])).hexdigest()
    if f"[Mod:{m['id']}] HELLO_BINARY: {binary_sha}" not in log:
        raise ValueError("Runtime DLL does not match the current package, or log predates binary evidence")
    markers = ("HELLO_INIT", "HELLO_READY", "HELLO_UI") if EXAMPLE == "hello-world" else (
        "HELLO_INIT", "HELLO_READY", "LAB_UI", "LAB_DIALOG", "LAB_SETTINGS", "LAB_LEVEL",
        "LAB_HUD", "LAB_BATTLE", "LAB_BONUS", "LAB_KILL", "LAB_RESULT", "LAB_TEST_PASS")
    for marker in markers:
        if f"[Mod:{m['id']}] {marker}:" not in log:
            raise ValueError(f"Missing runtime evidence: {marker}; use a fresh log from this build")
    if f"package applied: {m['id']}" not in log:
        raise ValueError("Missing host package applied evidence")
    phases = log.split(f"[Mod:{m['id']}] HELLO_SHUTDOWN:", 1)
    active = phases[0]
    if f"WARNING: [Mod:{m['id']}]" in active or "ERROR:" in active:
        raise ValueError("Runtime warnings/errors before shutdown; inspect the current log")
    write_json(DIST / "verification.json", {"packageSha256": sha(PACKAGE),
               "logSha256": sha(args.log), "log": str(Path(args.log).resolve()),
               "runtimeBinarySha256": binary_sha,
               "shutdownDiagnostics": [line for line in phases[-1].splitlines()
                   if len(phases) > 1 and line.startswith(("WARNING:", "ERROR:"))],
               "example": EXAMPLE, "markers": markers,
               "result": "runtime scenario observed"})
    print(f"PASS: {EXAMPLE}; package/binary identity and {len(markers)} runtime markers observed")


def extract(args):
    evidence_path = WORK / "release.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.exists() else None
    pck = args.pck or (evidence["pck"] if evidence else None)
    if not pck:
        raise ValueError("Run prepare or specify --pck")
    pack = Pack(pck)
    names = [n for n in pack.entries if n.startswith(args.prefix)] if args.prefix else args.path
    if not names:
        raise ValueError("No matching PCK resources")
    if args.output and not getattr(args, "dependencies", False):
        pack.extract(names, args.output)
        print(f"Extracted {len(names)} files with MD5 verification")
        return
    if not evidence:
        raise ValueError("Shared cache requires prepare first")
    cache = GameCache(WORK, evidence, pack)
    report = cache.fetch(names, dependencies=getattr(args, "dependencies", False))
    if args.output:
        pack.extract(report["paths"], args.output)
    print(f"Cache: {cache.files}; extracted={report['extracted']}; reused={report['reused']}")
    if report["unresolved"]:
        print("Unresolved dependencies (not source recovery): " + ", ".join(report["unresolved"]))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("prepare"); a.add_argument("--game-dir", required=True); a.add_argument("--pck"); a.set_defaults(func=prepare)
    a = sub.add_parser("build"); a.set_defaults(func=build)
    a = sub.add_parser("check"); a.set_defaults(func=check)
    a = sub.add_parser("install"); a.add_argument("--mods-dir", required=True); a.set_defaults(func=install)
    a = sub.add_parser("verify"); a.add_argument("--log", required=True); a.set_defaults(func=verify)
    a = sub.add_parser("extract"); a.add_argument("--pck"); a.add_argument("--output"); a.add_argument("--dependencies", action="store_true")
    group = a.add_mutually_exclusive_group(required=True); group.add_argument("--path", nargs="+"); group.add_argument("--prefix")
    a.set_defaults(func=extract)
    for command in ("build", "check", "install", "verify"):
        sub.choices[command].add_argument("--example", choices=("hello-world", *EXAMPLE_DIRS), default="hello-world")
    for command in ("build", "check"):
        parser = sub.choices[command]
        parser.add_argument("--release", action="store_true", help="Reject template/example metadata before distribution")
        parser.add_argument("--mods-dir", help="Read installed top-level pmod IDs for local conflicts")
        parser.add_argument("--allow-update", action="store_true", help="Permit a confirmed same-ID/same-filename update")
    args = p.parse_args()
    if getattr(args, "allow_update", False) and not getattr(args, "mods_dir", None):
        p.error("--allow-update requires --mods-dir")
    if hasattr(args, "example"):
        select_example(args.example)
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
