"""Select a single Mod/session/component's runtime drag feedback; importing defaults is explicit."""
import argparse
import json
import math
from pathlib import Path
import re
import time

LINE = re.compile(r'^\[Mod:([^\]\r\n]+)\] UI_LAYOUT_CHANGED: (\{.*\})$')


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def latest(text, *, mod_id, session_id, binary_sha256, scene_id, layout_id, component_id, after=0):
    """No inference of owner/session from whichever Mod happens to log last."""
    found = {}
    for line in text.splitlines():
        match = LINE.fullmatch(line.strip())
        if not match or match[1] != mod_id:
            continue
        try:
            event = json.loads(match[2])
        except (ValueError, TypeError):
            continue
        expected = dict(modId=mod_id, sessionId=session_id, binarySha256=binary_sha256,
                        sceneId=scene_id, layoutId=layout_id, componentId=component_id)
        if any(event.get(key) != value for key, value in expected.items()):
            continue
        seq = event.get('sequence')
        if type(seq) is not int or seq <= after:
            continue
        if (event.get('schemaVersion') != 1 or event.get('coordinateSpace') != 'parent-logical-pixels'
                or event.get('anchorX') != 'right' or event.get('anchorY') not in ('top', 'bottom')
                or event.get('reason') not in ('middle-drag', 'reset-default')
                or type(event.get('persisted')) is not bool):
            raise ValueError('Unsupported matching layout feedback')
        if any(not finite(event.get(key)) or abs(event[key]) > 100000 for key in ('rightInset', 'verticalInset')):
            raise ValueError('Invalid layout offsets')
        for key in ('parentSize', 'size'):
            value = event.get(key)
            if not isinstance(value, list) or len(value) != 2 or any(not finite(n) or n <= 0 or n > 100000 for n in value):
                raise ValueError('Invalid logical dimensions')
        if seq in found and found[seq] != event:
            raise ValueError('Conflicting events for the same sequence')
        found[seq] = event
    return found[max(found)] if found else None


def apply_defaults(path, event):
    """Update one predeclared slot only; do not create or switch Mod identities."""
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1 or data.get('modId') != event['modId']:
        raise ValueError('Defaults belong to another Mod/schema')
    slot = '/'.join(event[k] for k in ('sceneId', 'layoutId', 'componentId'))
    if slot not in data['placements']:
        raise ValueError('Unknown component/layout; declare it before importing')
    old = data['placements'][slot]
    if old.get('anchorY') != event['anchorY']:
        raise ValueError('Vertical layout policy changed; review before importing')
    data['placements'][slot] = {k: event[k] for k in ('anchorX', 'anchorY', 'rightInset', 'verticalInset')}
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', required=True)
    for field in ('mod-id', 'session-id', 'binary-sha256', 'scene-id', 'layout-id', 'component-id'):
        parser.add_argument('--'+field, required=True)
    parser.add_argument('--after', type=int, default=0)
    parser.add_argument('--wait-seconds', type=float, default=0)
    parser.add_argument('--output', help='Save this one filtered event locally')
    parser.add_argument('--apply-defaults', help='Explicitly update this project defaults JSON')
    args = parser.parse_args()
    if not 0 <= args.wait_seconds <= 60 or args.after < 0:
        parser.error('wait-seconds must be 0..60, after must be nonnegative')
    query = {k: getattr(args, k) for k in ('mod_id','session_id','binary_sha256','scene_id','layout_id','component_id')}
    deadline = time.monotonic() + args.wait_seconds
    while True:
        path = Path(args.log)
        event = latest(path.read_text(encoding='utf-8', errors='replace') if path.exists() else '', after=args.after, **query)
        if event is not None or time.monotonic() >= deadline:
            break
        time.sleep(.2)
    if event is None:
        print(json.dumps(dict(status='waiting', message='尚无匹配的位置更改反馈'), ensure_ascii=False))
        return
    if args.apply_defaults:
        apply_defaults(args.apply_defaults, event)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(event, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status='changed', event=event), ensure_ascii=False))


if __name__ == '__main__':
    main()
