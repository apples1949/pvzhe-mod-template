import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from ui_layout_feedback import latest, apply_defaults


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.event = dict(schemaVersion=1,modId='my-mod',sessionId='current',binarySha256='a'*64,
            sceneId='menu',layoutId='normal',componentId='hello',sequence=1,anchorX='right',anchorY='top',
            rightInset=32.25,verticalInset=80.5,parentSize=[1080,600],size=[170,46],
            reason='middle-drag',coordinateSpace='parent-logical-pixels',persisted=True)
        self.query=dict(mod_id='my-mod',session_id='current',binary_sha256='a'*64,
            scene_id='menu',layout_id='normal',component_id='hello')
    def line(self,event,prefix=None):
        return f"[Mod:{prefix or event['modId']}] UI_LAYOUT_CHANGED: "+json.dumps(event)
    def test_other_mod_old_session_binary_and_other_controls_are_ignored(self):
        lines=[]
        for key,value in [('modId','other'),('sessionId','old'),('binarySha256','b'*64),('componentId','other'),('layoutId','other'),('sceneId','other')]:
            item=dict(self.event,**{key:value},sequence=200)
            lines.append(self.line(item))
        lines.append(self.line(self.event,prefix='other'))
        self.assertIsNone(latest('\n'.join(lines),**self.query))
        lines.append(self.line(self.event))
        self.assertEqual(latest('\n'.join(lines),**self.query),self.event)
    def test_latest_sequence_dedup_and_conflict(self):
        newer=dict(self.event,sequence=2,rightInset=70)
        text='\n'.join(self.line(e) for e in [newer,self.event,newer])
        self.assertEqual(latest(text,**self.query),newer)
        self.assertIsNone(latest(text,**self.query,after=2))
        with self.assertRaises(ValueError):latest(text+'\n'+self.line(dict(newer,rightInset=80)),**self.query)
    def test_invalid_geometry_or_anchor_rejected(self):
        for changes in [dict(anchorX='left'),dict(rightInset=float('nan')),dict(size=[-1,20]),dict(verticalInset=True)]:
            with self.assertRaises(ValueError):latest(self.line(dict(self.event,**changes)),**self.query)
    def test_import_changes_only_matching_existing_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'layout.json'
            original=dict(schemaVersion=1,modId='my-mod',placements={
                'menu/normal/hello':dict(anchorX='right',anchorY='top',rightInset=2,verticalInset=3),
                'menu/normal/other':dict(anchorX='right',anchorY='top',rightInset=4,verticalInset=5)})
            path.write_text(json.dumps(original),encoding='utf-8')
            apply_defaults(path,self.event)
            data=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(data['placements']['menu/normal/hello']['rightInset'],32.25)
            self.assertEqual(data['placements']['menu/normal/other'],original['placements']['menu/normal/other'])
            before=path.read_bytes()
            for event in [dict(self.event,modId='other'),dict(self.event,componentId='unknown'),dict(self.event,anchorY='bottom')]:
                with self.assertRaises(ValueError):apply_defaults(path,event)
                self.assertEqual(path.read_bytes(),before)
