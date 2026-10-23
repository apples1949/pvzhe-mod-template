"""Archive only reconstructible game copies; retain Mod packages, logs and screenshots."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from game_environment import active, inside, lease, save, sha, verify

CHUNK = 1024 * 1024


def running_workspace_executables(root):
    if os.name != 'nt': return []
    command = 'Get-CimInstance Win32_Process | Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress'
    data = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True, encoding='utf-8', errors='replace'))
    result = []
    if isinstance(data, dict): data = [data]
    for proc in data or []:
        path = proc.get('ExecutablePath')
        if path and any(Path(path).resolve().is_relative_to(Path(root).resolve() / folder) for folder in ('.work', '.game')):
            result.append(proc['ProcessId'])
    return result


def archive_pack(pack, base, evidence, delete=False, base_sha=None, retain=False):
    """The test tool changes the v4 header and appends a directory/driver only."""
    pack, base, evidence = Path(pack), Path(base), Path(evidence)
    if pack.stat().st_size < base.stat().st_size: return None
    base_size = base.stat().st_size; original = hashlib.sha256(); normalized = hashlib.sha256()
    tail = evidence / 'test-pack.tail.bin'; temp = evidence / ('test-pack.' + uuid.uuid4().hex + '.tmp')
    with base.open('rb') as source: base_header = source.read(112)
    if base_header[:4] != b'GDPC': raise ValueError('Invalid base PCK')
    try:
        with pack.open('rb') as stream:
            header = stream.read(112); original.update(header)
            if len(header) != 112: return None
            changed = bytearray(header); changed[32:40] = base_header[32:40]
            normalized.update(changed); remaining = base_size - 112
            while remaining:
                block = stream.read(min(CHUNK, remaining))
                if not block: return None
                normalized.update(block); original.update(block); remaining -= len(block)
            if normalized.hexdigest() != (base_sha or sha(base)): return None
            tail_hash = hashlib.sha256()
            with temp.open('wb') as output:
                while block := stream.read(CHUNK):
                    output.write(block); original.update(block); tail_hash.update(block)
        result = dict(format='pvzhe.test-pack-replay', schemaVersion=1, pckName=pack.name,
            basePckSha256=normalized.hexdigest(), baseSize=base_size, header=header.hex(),
            tailFile=tail.name, tailSha256=tail_hash.hexdigest(), patchedSha256=original.hexdigest(),
            patchedSize=pack.stat().st_size, removedFiles={})
        if delete or retain:
            temp.replace(tail); save(evidence / 'pack-replay.json', result)
        if delete:
            # Compare-and-delete: never discard a changed file after archiving.
            if sha(pack) != result['patchedSha256']: raise ValueError('Test pack changed during archival')
            pack.unlink()
        return result
    finally:
        temp.unlink(missing_ok=True)


def restore(root, evidence, base=None):
    evidence = inside(Path(evidence), Path(root) / '.work')
    data = json.loads((evidence / 'pack-replay.json').read_text(encoding='utf-8'))
    if data.get('format') != 'pvzhe.test-pack-replay' or data.get('schemaVersion') != 1:
        raise ValueError('Unknown replay record')
    sources = []
    for name in ('current', 'old'):
        slot = Path(root) / '.game' / name
        if (slot / 'release-manifest.json').exists():
            manifest = verify(slot)
            if manifest['pckSha256'] == data['basePckSha256']: sources.append(slot / manifest['pck'])
    if base is not None: sources.insert(0, Path(base).resolve())
    base = next((p for p in sources if p.is_file() and sha(p) == data['basePckSha256']), None)
    if base is None: raise ValueError('Required release is no longer in current/old; provide the matching original --base-pck')
    tail = inside(evidence / data['tailFile'], evidence)
    if sha(tail) != data['tailSha256']: raise ValueError('Archived test patch changed')
    target = inside(evidence / data['pckName'], evidence)
    if target.exists(): raise ValueError('Restore destination already exists; archive it again before restoring')
    for name, identity in data.get('removedFiles', {}).items():
        source = inside(base.parent / name, base.parent)
        dest = inside(evidence / name, evidence)
        if not source.is_file() or sha(source) != identity['sha256']: raise ValueError('Replay runtime file missing/changed: ' + name)
        if dest.exists() and sha(dest) != identity['sha256']: raise ValueError('Replay destination changed: ' + name)
    temp = target.with_name(target.name + '.restoring')
    try:
        with base.open('rb') as source, temp.open('xb') as output:
            output.write(bytes.fromhex(data['header'])); source.seek(112)
            while block := source.read(CHUNK): output.write(block)
            with tail.open('rb') as patch:
                while block := patch.read(CHUNK): output.write(block)
        if temp.stat().st_size != data['patchedSize'] or sha(temp) != data['patchedSha256']:
            raise ValueError('Replay reconstruction hash mismatch')
        temp.replace(target)
    finally: temp.unlink(missing_ok=True)
    for name in data.get('removedFiles', {}):
        dest = evidence / name; dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            import shutil
            shutil.copyfile(base.parent / name, dest)
    return target


def cleanup(root, apply=False):
    root = Path(root).resolve(); work = root / '.work'
    with lease(root):
        if running_workspace_executables(root): raise ValueError('A workspace executable is active; exit isolated games before storage maintenance')
        slot, manifest = active(root); base = slot / manifest['pck']
        report = dict(applied=apply, archivedPacks=0, removedFiles=0, reclaimableBytes=0, skipped=[])
        claimed = set()
        for pack in sorted(work.rglob('*.pck')):
            inside(pack, work)
            if pack.stat().st_size < base.stat().st_size: continue
            evidence = pack.parent
            if evidence in claimed:
                report['skipped'].append(str(pack.relative_to(root))); continue
            # Never overwrite a replay record for a different pack in the same folder.
            existing = evidence / 'pack-replay.json'
            previous = None
            if existing.exists():
                previous = json.loads(existing.read_text(encoding='utf-8'))
                if (previous.get('format') != 'pvzhe.test-pack-replay'
                    or previous.get('pckName') != pack.name
                    or previous.get('patchedSha256') != sha(pack)
                    or previous.get('basePckSha256') != manifest['pckSha256']):
                    report['skipped'].append(str(pack.relative_to(root))); continue
            size = pack.stat().st_size
            result = archive_pack(pack, base, evidence, delete=apply, base_sha=manifest['pckSha256'])
            if result is None:
                report['skipped'].append(str(pack.relative_to(root))); continue
            claimed.add(evidence)
            if previous:
                result['removedFiles'] = previous.get('removedFiles', {})
                if apply: save(existing, result)
            report['archivedPacks'] += 1; report['reclaimableBytes'] += size - (evidence / 'test-pack.tail.bin').stat().st_size if apply else size - (result['patchedSize']-result['baseSize'])
            for name, identity in manifest['files'].items():
                if name == manifest['pck']: continue
                candidate = inside(evidence / name, work)
                if candidate.is_file() and candidate.stat().st_size == identity['size'] and sha(candidate) == identity['sha256']:
                    result['removedFiles'][name] = identity; report['removedFiles'] += 1
                    report['reclaimableBytes'] += identity['size']
                    if apply:
                        save(evidence / 'pack-replay.json', result); candidate.unlink()
            if report['archivedPacks'] % 10 == 0:
                print(f"Checked {report['archivedPacks']} packs; {report['reclaimableBytes']/2**30:.2f} GiB reclaimable", file=sys.stderr, flush=True)
        save(work / 'storage-maintenance' / ('applied.json' if apply else 'preview.json'), report)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preview', 'clean', 'restore'])
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--runtime'); parser.add_argument('--base-pck')
    args = parser.parse_args()
    if args.command == 'restore':
        if not args.runtime: parser.error('--runtime is required')
        with lease(args.root): result = str(restore(args.root, args.runtime, args.base_pck))
    else: result = cleanup(args.root, args.command == 'clean')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
