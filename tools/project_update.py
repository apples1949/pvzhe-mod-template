"""Fetch and stage template changes without overwriting a player's Mod or origin."""
import argparse
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import uuid
from game_environment import compatible, inside, save, verify

UPSTREAM = 'https://github.com/axh-xecoy/pvzhe-mod-template.git'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def files(raw):
    return {name.decode('utf-8') for name in raw.split(b'\0') if name}


def plan(root, ref='main', upstream=UPSTREAM, base=None):
    root = Path(root).resolve()
    if not ref or ref.startswith('-') or any(c in ref for c in '\r\n\0:'): raise ValueError('Invalid upstream ref')
    if not upstream or upstream.startswith('-'): raise ValueError('Invalid upstream source')
    git(root, 'rev-parse', '--show-toplevel')
    git(root, 'fetch', '--no-tags', '--no-recurse-submodules', upstream, ref)
    target = git(root, 'rev-parse', '--verify', 'FETCH_HEAD^{commit}').decode().strip()
    lock = root / 'template.lock.json'
    state = json.loads(lock.read_text(encoding='utf-8')) if lock.exists() else {}
    if state and (state.get('schemaVersion') != 1 or state.get('revision') is not None and not isinstance(state['revision'],str)):
        raise ValueError('Unknown or invalid template provenance lock')
    if state.get('upstream') and state['upstream'] != upstream:
        raise ValueError('Upstream differs from project lock; explicitly reconcile the source before updating')
    base = base or state.get('revision')
    if base:
        base = git(root, 'rev-parse', '--verify', base + '^{commit}').decode().strip()
    else:
        try: base = git(root, 'merge-base', 'HEAD', target).decode().strip()
        except subprocess.CalledProcessError:
            raise ValueError('No shared template history; identify the original template commit before merging')
    git(root, 'merge-base', '--is-ancestor', base, target)
    changed = files(git(root, 'diff', '--no-renames', '--name-only', '-z', base, target, '--'))
    local = files(git(root, 'diff', '--name-only', '-z', base, '--'))
    untracked = files(git(root, 'ls-files', '--others', '--exclude-standard', '-z'))
    folder = root / '.work/template-updates' / uuid.uuid4().hex
    inside(folder, root / '.work')
    incoming = folder / 'incoming'; incoming.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(git(root, 'archive', '--format=tar', target))) as archive:
        for member in archive:
            if member.isdir(): continue
            if not member.isfile(): raise ValueError('Upstream archive contains unsupported links/special files')
            dest = inside(incoming / member.name, incoming)
            if Path(member.name).parts[0] in ('.game', '.work', '.git'): raise ValueError('Upstream contains local game/work data')
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, dest.open('wb') as output: shutil.copyfileobj(source, output)
    (folder / 'upstream.patch').write_bytes(git(root, 'diff', '--binary', base, target, '--'))
    (folder / 'local.patch').write_bytes(git(root, 'diff', '--binary', base, '--'))
    backup = folder / 'untracked'
    for name in untracked:
        if Path(name).parts[0] in ('.game', '.work', '.git', 'dist'): continue
        source = inside(root / name, root)
        if not source.is_file(): continue
        dest = inside(backup / name, backup); dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    environment = 'unprepared'
    manifest = root / '.game/current/release-manifest.json'
    if manifest.exists():
        current = verify(manifest.parent)
        try: compatible(incoming, current); environment = 'match'
        except ValueError: environment = 'requires-game-or-compatible-template'
    result = dict(schemaVersion=1, upstream=upstream, base=base, target=target,
        changed=sorted(changed), overlaps=sorted(changed & (local | untracked)),
        incoming=str(incoming), environment=environment,
        action='Review and merge staged template changes; player source and origin have not been modified')
    save(folder / 'plan.json', result)
    return folder / 'plan.json', result


def record(root, plan_path):
    root = Path(root).resolve(); plan_path = inside(Path(plan_path), root / '.work/template-updates')
    result = json.loads(plan_path.read_text(encoding='utf-8'))
    incoming = inside(Path(result['incoming']), root / '.work/template-updates')
    if json.loads((root / 'game-compatibility.json').read_text(encoding='utf-8')) != json.loads((incoming / 'game-compatibility.json').read_text(encoding='utf-8')):
        raise ValueError('Target compatibility policy has not been merged; cannot record the update')
    from game_environment import active
    active(root) # A bookkeeping record cannot bless a game-version mismatch.
    target = git(root, 'rev-parse', '--verify', result['target'] + '^{commit}').decode().strip()
    save(root / 'template.lock.json', dict(schemaVersion=1, upstream=result['upstream'], revision=target))
    return dict(recorded=target, note='Provenance only; this command does not build or verify Mod behavior')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'record'])
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--ref', default='main'); parser.add_argument('--base'); parser.add_argument('--upstream', default=UPSTREAM)
    parser.add_argument('--plan')
    args = parser.parse_args()
    if args.command == 'plan':
        path, result = plan(args.root, args.ref, args.upstream, args.base); result['planPath'] = str(path)
    else:
        if not args.plan: parser.error('--plan is required')
        result = record(args.root, args.plan)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
