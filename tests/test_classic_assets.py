import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
from classic_assets import Pak, decode_reanim, export_bundle, research, resolved, safe_path


def pak_bytes(files):
    header=bytearray(struct.pack("<II",0xBAC04AC0,0))
    for name,data in files.items():
        b=name.encode("gbk")
        header.extend(bytes((0,len(b)))+b+struct.pack("<IQ",len(data),0))
    header.append(128)
    return bytes(header)+b"".join(files.values())


def reanim_bytes(hidden=False, duplicate=False):
    def string(s):
        b=s.encode("utf-8");return struct.pack("<I",len(b))+b
    raw=bytearray(b"\0"*8+struct.pack("<IfII",2,12.,0,12))
    raw.extend(struct.pack("<III",0,0,2)*2)
    for name,image in [("anim_idle",""),("anim_idle" if duplicate else "末轨","IMAGE_REANIM_TEST")]:
        raw.extend(string(name)+struct.pack("<I",44))
        raw.extend(struct.pack("<8fIII",1,2,0,0,1,1,0,.5,0,0,0))
        raw.extend(struct.pack("<8fIII",0,-10000,-10000,-10000,-10000,-10000,-1 if hidden and image else -10000,-10000,0,0,0))
        raw.extend(string(image)+string("")+string(""))
        raw.extend(string("")+string("")+string(""))
    return struct.pack("<II",0xDEADFED4,len(raw))+zlib.compress(raw)


class ClassicAssetsTests(unittest.TestCase):
    def test_pak_xor_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"main.pak"
            data=pak_bytes({"reanim/test.png":b"pixels"})
            p.write_bytes(data.translate(bytes(x^247 for x in range(256))))
            pak=Pak(p)
            self.assertEqual(pak.read("REANIM/test.png"),b"pixels")
            records=pak.extract(["reanim/test.png"],Path(d)/"out")
            self.assertEqual(records[0]["size"],6)
            self.assertEqual((Path(d)/"out/reanim/test.png").read_bytes(),b"pixels")
            p.write_bytes(data[:-1])
            with self.assertRaises(ValueError):Pak(p)

    def test_paths_do_not_escape(self):
        for name in ["../x", "C:/x", "/x", "a/../x", "a\\..\\x"]:
            with self.assertRaises(ValueError):safe_path(name)

    def test_gbk_exact_name_not_description_mention(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); props=p/"props";props.mkdir()
            data="[KEY]\n中文植物\n[KEY_DESCRIPTION]\n威力20\n[OTHER]\n有人提及中文植物\n".encode("gbk")
            (props/"PlantStrings.txt").write_bytes(data)
            (p/"a.pak").write_bytes(pak_bytes({"properties/PlantStrings.txt":data,"compiled/Key.reanim.compiled":b"a"}))
            result=research(Pak(p/"a.pak"),props,"中文植物")
            self.assertEqual([m["key"] for m in result["matches"]],["KEY"])
            self.assertTrue(result["sources"][0]["sameAsPak"])
            self.assertEqual(result["matches"][0]["animationCandidates"],["compiled/Key.reanim.compiled"])
            (props/"PlantStrings.txt").write_bytes(data+b"\n")
            self.assertFalse(research(Pak(p/"a.pak"),props,"中文植物")["sources"][0]["sameAsPak"])

    def test_raw_tracks_inheritance_zero_and_last_string(self):
        doc=decode_reanim(reanim_bytes())
        self.assertEqual(doc["tracks"][-1]["name"],"末轨")
        frames=list(resolved(doc["tracks"][-1]))
        self.assertEqual(frames[1]["x"],0)
        self.assertEqual(frames[1]["y"],2)
        self.assertEqual(frames[1]["image"],"IMAGE_REANIM_TEST")
        self.assertEqual(frames[1]["a"],.5)
        broken=bytearray(reanim_bytes());struct.pack_into("<I",broken,4,1)
        with self.assertRaises(ValueError):decode_reanim(broken)

    def test_missing_dependency_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"a.pak").write_bytes(pak_bytes({"compiled/test.reanim.compiled":reanim_bytes()}))
            result=export_bundle(Pak(p/"a.pak"),"compiled/test.reanim.compiled",p/"bundle")
            self.assertEqual(result["unresolvedImages"][0]["image"],"IMAGE_REANIM_TEST")

    def test_dat_written_bytes_and_input_integrity(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Optional conversion requires Pillow")
        from io import BytesIO
        from reanim_dat import convert
        from classic_assets import Reader
        im=Image.new("RGBA",(2,3),(255,0,0,128)); stream=BytesIO();im.save(stream,format="PNG")
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"a.pak").write_bytes(pak_bytes({"compiled/test.reanim.compiled":reanim_bytes(hidden=True),"reanim/test.png":stream.getvalue()}))
            export_bundle(Pak(p/"a.pak"),"compiled/test.reanim.compiled",p/"bundle")
            result=convert(p/"bundle",p/"out")
            self.assertEqual(result["clipsHalfOpen"],{"anim_idle":[0,2]})
            r=Reader((p/"out/animation.dat").read_bytes())
            fps,frames,w,h,n=r.unpack("fHHHQ")
            self.assertEqual((fps,frames),(12,2));self.assertEqual(n,w*h*4)
            pixels=r.take(n)
            self.assertEqual(pixels[(w+1)*4:(w+1)*4+4],bytes((255,0,0,128)))
            self.assertEqual(r.unpack("H")[0],2);self.assertEqual(r.string(),"IMAGE_REANIM_TEST");r.take(16)
            self.assertEqual(r.string(),"__pvz_control__");rect=r.unpack("4f")
            self.assertEqual(pixels[(int(rect[1])*w+int(rect[0]))*4:(int(rect[1])*w+int(rect[0]))*4+4],bytes(4))
            self.assertEqual(r.unpack("H")[0],2)
            for layer,expected_media in [("anim_idle",1),("末轨",0)]:
                self.assertEqual(r.string(),layer)
                for frame in range(2):
                    self.assertEqual(r.unpack("HH"),(1,1 if layer=="末轨" and frame==1 else expected_media))
                    matrix=r.unpack("6f");self.assertEqual(matrix[4],1 if frame==0 else 0)
                    self.assertEqual(r.unpack("I")[0],0xffffff80)
            self.assertEqual(r.unpack("H")[0],1);self.assertEqual(r.string(),"anim_idle")
            self.assertEqual(r.unpack("HHH"),(0,2,0));self.assertEqual(r.pos,len(r.data))
            (p/"bundle/files/reanim/test.png").write_bytes(b"changed")
            with self.assertRaises(ValueError):convert(p/"bundle",p/"out")

    def test_duplicate_layers_require_explicit_index_mapping(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Optional conversion requires Pillow")
        from io import BytesIO
        from reanim_dat import convert
        stream=BytesIO();Image.new("RGBA",(1,1),(255,0,0,255)).save(stream,format="PNG")
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"a.pak").write_bytes(pak_bytes({"compiled/test.reanim.compiled":reanim_bytes(duplicate=True),"reanim/test.png":stream.getvalue()}))
            export_bundle(Pak(p/"a.pak"),"compiled/test.reanim.compiled",p/"bundle")
            before=(p/"bundle/raw-reanim.json").read_bytes()
            with self.assertRaises(ValueError):convert(p/"bundle",p/"out")
            result=convert(p/"bundle",p/"out",{"1":"face"})
            self.assertEqual(result["layers"],["anim_idle","face"])
            self.assertEqual(result["sourceLayers"][1],{"index":1,"sourceName":"anim_idle","targetName":"face"})
            self.assertEqual((p/"bundle/raw-reanim.json").read_bytes(),before)
            for mapping in [{"2":"outside"},{"1":""},{"1":"anim_idle"}]:
                with self.assertRaises(ValueError):convert(p/"bundle",p/"out",mapping)


if __name__=="__main__":unittest.main()
