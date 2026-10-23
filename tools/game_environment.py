"""Two-slot, hash-verified local releases. No game content belongs in Git."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def inside(path, root):
    path, root = Path(path), Path(root).resolve()
    if path.is_symlink() or getattr(os.path, 'isjunction', lambda p: False)(path):
        raise ValueError('Managed paths cannot be links: ' + str(path))
    resolved = path.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError('Path escaped managed directory: ' + str(path))
    for parent in path.absolute().parents:
        if parent == root: break
        if parent.is_symlink() or getattr(os.path, 'isjunction', lambda p: False)(parent):
            raise ValueError('Managed parent cannot be a link')
    return resolved


@contextmanager
def lease(root):
    game = Path(root).resolve() / '.game'
    if game.is_symlink() or getattr(os.path, 'isjunction', lambda p: False)(game):
        raise ValueError('.game cannot be a link')
    game.mkdir(parents=True, exist_ok=True)
    lock = game / 'environment.lock'
    try: handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError: raise ValueError('Game environment is busy; inspect .game/environment.lock before retrying')
    try:
        os.write(handle, json.dumps(dict(pid=os.getpid())).encode()); yield game
    finally:
        os.close(handle); lock.unlink()


def compatible(root, manifest):
    policy_path = Path(root) / 'game-compatibility.json'
    if not policy_path.is_file(): raise ValueError('Template has no declared compatibility policy; verify its baseline before using this game')
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    if policy.get('schemaVersion') != 1: raise ValueError('Unsupported compatibility policy')
    for release in policy['supportedReleases']:
        if (release['pckSha256'] == manifest['pckSha256']
            and release['assemblies'] == manifest['assemblies']
            and release['engine'] == manifest['engine']):
            return release['version']
    raise ValueError('Game does not match this template compatibility policy; obtain a supported release or use maintainer analysis-only preparation')


def inspect(game_dir, pck=None):
    from pck import Pack
    game_dir = Path(game_dir).resolve()
    packs = [Path(pck).resolve()] if pck else list(game_dir.glob('*.pck'))
    if len(packs) != 1: raise ValueError('Specify exactly one release PCK')
    pack = Pack(packs[0]); exe = pack.path.with_suffix('.exe')
    if pack.path.parent != game_dir or not exe.is_file():
        raise ValueError('Release EXE and PCK must be in the supplied directory with matching basenames')
    files = {pack.path.name: pack.path, exe.name: exe}
    for folder in game_dir.glob('data_*'):
        if not folder.is_dir(): continue
        for path in folder.rglob('*'):
            inside(path, game_dir)
            if path.is_file(): files[path.relative_to(game_dir).as_posix()] = path
    records = {name: dict(sha256=sha(path), size=path.stat().st_size) for name, path in files.items()}
    assemblies = {}
    for name in ('PlantsVsZombies.dll', 'GodotSharp.dll'):
        matches = [record['sha256'] for key, record in records.items() if key.startswith('data_') and key.endswith('/' + name)]
        if len(matches) != 1: raise ValueError('Cannot locate unique release runtime assembly: ' + name)
        assemblies[name] = matches[0]
    identity = dict(pckSha256=records[pack.path.name]['sha256'], engine=pack.engine,
                    assemblies=assemblies, files=records)
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return dict(schemaVersion=1, fingerprint=fingerprint, source=str(game_dir),
                pck=pack.path.name, exe=exe.name, **identity)


def verify(slot, manifest=None):
    slot = Path(slot).absolute()
    for directory in (slot, *slot.parents):
        if directory.is_symlink() or getattr(os.path, 'isjunction', lambda p: False)(directory):
            raise ValueError('Release environment cannot be a link')
    slot = slot.resolve()
    manifest = manifest or json.loads((slot / 'release-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schemaVersion') != 1: raise ValueError('Unsupported local release manifest')
    for name, item in manifest['files'].items():
        path = inside(slot / name, slot)
        if not path.is_file() or path.stat().st_size != item['size'] or sha(path) != item['sha256']:
            raise ValueError('Local release changed: ' + name)
    return manifest


def install(root, game_dir, pck=None):
    root = Path(root).resolve()
    candidate = inspect(game_dir, pck); candidate['version'] = compatible(root, candidate)
    with lease(root) as game:
        current, old = game / 'current', game / 'old'
        for debris in ('.incoming-*', '.retired-*'):
            if list(game.glob(debris)): raise ValueError('Interrupted release transaction exists; inspect it before another switch')
        if current.exists():
            existing = verify(current)
            if existing['fingerprint'] == candidate['fingerprint']:
                return current, existing, True
        if Path(game_dir).resolve() == old.resolve() and old.exists() and current.exists():
            verify(old)
            swap = game / ('.incoming-' + uuid.uuid4().hex)
            current.rename(swap)
            try: old.rename(current); swap.rename(old)
            except Exception:
                if current.exists() and not old.exists(): current.rename(old)
                swap.rename(current); raise
            return current, verify(current), True
        stage = game / ('.incoming-' + uuid.uuid4().hex)
        retired = game / ('.retired-' + uuid.uuid4().hex)
        stage.mkdir(); moved_current = moved_old = promoted = False
        try:
            for name in candidate['files']:
                source = inside(Path(game_dir).resolve() / name, Path(game_dir).resolve())
                target = inside(stage / name, stage); target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            save(stage / 'release-manifest.json', candidate); verify(stage, candidate)
            if old.exists(): inside(old, game).rename(retired); moved_old = True
            if current.exists(): inside(current, game).rename(old); moved_current = True
            stage.rename(current); promoted = True
        except Exception:
            if promoted: current.rename(stage)
            if moved_current: old.rename(current)
            if moved_old and retired.exists(): retired.rename(old)
            raise
        finally:
            if stage.exists(): shutil.rmtree(inside(stage, game))
        # Promotion has committed. A partial oldest-version cleanup must never
        # roll back into a partly deleted release; leave debris for inspection.
        if retired.exists(): shutil.rmtree(inside(retired, game))
        return current, candidate, False


def active(root):
    slot = Path(root).resolve() / '.game/current'
    manifest = verify(slot); compatible(root, manifest)
    return slot, manifest


def ensure_runtime(slot, manifest):
    """One writable test PCK, with stable release EXE/runtime files copied only once."""
    runtime = slot / 'runtime'; runtime.mkdir(exist_ok=True)
    for name, record in manifest['files'].items():
        if name == manifest['pck']: continue
        source, target = inside(slot / name, slot), inside(runtime / name, runtime)
        if target.exists():
            if sha(target) != record['sha256']: raise ValueError('Shared runtime modified: ' + name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
    return runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'status', 'install'])
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--game-dir'); parser.add_argument('--pck')
    args = parser.parse_args()
    if args.command == 'status':
        result = {}
        for name in ('current', 'old'):
            path = Path(args.root) / '.game' / name / 'release-manifest.json'
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                result[name] = dict(version=data['version'], fingerprint=data['fingerprint'])
    else:
        if not args.game_dir: parser.error('--game-dir is required')
        result = inspect(args.game_dir, args.pck) if args.command == 'inspect' else dict(zip(('slot', 'manifest', 'reused'), install(args.root, args.game_dir, args.pck)))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__': main()
