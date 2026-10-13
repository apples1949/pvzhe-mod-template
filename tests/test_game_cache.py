import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from game_cache import GameCache, sha
from placement_model import Session
from preview_session import bind

class FakePack:
    version=4
    engine=[4,7,0]
    def __init__(self,path,files):
        self.path=path;self.data=files
        self.entries={n:{"md5":hashlib.md5(b).hexdigest(),"size":len(b),"offset":0} for n,b in files.items()}
    def read(self,name):return self.data[name]

class CacheTests(unittest.TestCase):
    def setup_cache(self,root):
        pck=root/"game.pck";pck.write_bytes(b"pack-v1")
        pack=FakePack(pck,{"scene.tscn":b'[ext_resource path="res://image.png"]',
            "image.png.import":b'path="res://.godot/imported/image.ctex"\nsource_file="res://image.png"',
            ".godot/imported/image.ctex":b"texture"})
        release={"pck":str(pck),"pckSha256":sha(pck),"assemblies":{}}
        return pack,release,GameCache(root,release,pack)

    def test_dependency_closure_and_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack,release,cache=self.setup_cache(Path(tmp))
            report=cache.fetch(["scene.tscn"],True)
            self.assertEqual(report["extracted"],3);self.assertEqual(report["unresolved"],[])
            with patch.object(pack,"read",side_effect=AssertionError("must reuse")):
                report=cache.fetch(["scene.tscn"],True)
            self.assertEqual(report["extracted"],0);self.assertEqual(report["reused"],3)

    def test_tampered_cache_is_not_silently_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack,release,cache=self.setup_cache(Path(tmp));cache.fetch(["scene.tscn"])
            cache.destination("scene.tscn").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"Cached file changed"):cache.fetch(["scene.tscn"])

    def test_version_change_rejects_old_evidence_and_isolates(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack,release,cache=self.setup_cache(Path(tmp));pack.path.write_bytes(b"pack-v2")
            with self.assertRaisesRegex(ValueError,"PCK changed"):GameCache(Path(tmp),release,pack)
            fresh=dict(release,pckSha256=sha(pack.path));new=GameCache(Path(tmp),fresh,pack)
            self.assertNotEqual(cache.root,new.root);self.assertTrue(cache.root.exists())

    def test_unresolved_dependencies_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack,release,cache=self.setup_cache(Path(tmp));pack.data["scene.tscn"]=b'path="res://missing.font"'
            pack.entries["scene.tscn"]["md5"]=hashlib.md5(pack.data["scene.tscn"]).hexdigest()
            self.assertEqual(cache.fetch(["scene.tscn"],True)["unresolved"],["missing.font"])
            with self.assertRaises(ValueError):cache.fetch(["../escape"])
            with self.assertRaises(ValueError):cache.fetch(["missing.font"])

    def test_assembly_changes_invalidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pack,release,cache=self.setup_cache(root)
            refs=root/"references";refs.mkdir();dll=refs/"Host.dll";dll.write_bytes(b"v1")
            origin=root/"origin.dll";origin.write_bytes(b"v1")
            release["assemblies"]={"Host.dll":{"origin":str(origin),"sha256":sha(dll)}}
            new=GameCache(root,release,pack);self.assertNotEqual(cache.key,new.key)
            origin.write_bytes(b"v2")
            with self.assertRaisesRegex(ValueError,"assembly moved/changed"):GameCache(root,release,pack)

    def test_render_provenance_rejects_changed_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pack,release,cache=self.setup_cache(root)
            (root/"release.json").write_text(json.dumps(release))
            dll=root/"mod.dll";dll.write_bytes(b"v1")
            spec={"schemaVersion":1,"layouts":[{"id":"menu","canvas":{"width":900,"height":500},"objects":[{"id":"button","x":10,"y":10,"width":160,"height":46,"imagePadding":8}]}]}
            source=root/"input.json";source.write_text(json.dumps(spec));output=root/"ready.json"
            with patch("game_cache.Pack",return_value=pack):
                bind(source,dll,root,output);Session.load(output)
                dll.write_bytes(b"v2")
                with self.assertRaisesRegex(ValueError,"old release/component"):Session.load(output)

if __name__=="__main__":unittest.main()
