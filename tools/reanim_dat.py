"""Export a verified classic bundle to PVZHE 0.30 DAT, retaining raw timelines.

Requires Pillow. This converts structure, not gameplay or a complete sprite scene.
"""
import argparse
import json
import math
import struct
from pathlib import Path
from classic_assets import digest, resolved, write_json, safe_path


def matrix(f):
    x, y = math.radians(f["kx"]), math.radians(f["ky"])
    return (f["sx"]*math.cos(x), f["sx"]*math.sin(x),
            -f["sy"]*math.sin(y), f["sy"]*math.cos(y), f["x"], f["y"])


def convert(bundle, output, layer_map=None):
    from PIL import Image, __version__ as pillow_version
    bundle, output = Path(bundle), Path(output)
    m = json.loads((bundle/"bundle.json").read_text(encoding="utf-8"))
    if m["unresolvedImages"]:
        raise ValueError("Bundle has unresolved images")
    for record in m["files"]:
        if digest((bundle/"files"/safe_path(record["path"])).read_bytes()) != record["sha256"]:
            raise ValueError("Bundle file changed: " + record["path"])
    from classic_assets import decode_reanim, inspect_animation
    # Re-decode checked source, rather than trusting an editable intermediate JSON.
    source = (bundle/"files"/safe_path(m["animation"])).read_bytes()
    if digest(source) != m["animationSha256"]:
        raise ValueError("Source animation identity mismatch")
    doc = decode_reanim(source)
    if set(inspect_animation(doc)["images"]) != set(m["imageMap"]):
        raise ValueError("Image mapping does not cover the actual animation")
    layer_map = layer_map or {}
    if not isinstance(layer_map, dict):
        raise ValueError("Layer map must be an object keyed by source track index")
    for index, name in layer_map.items():
        if not str(index).isdigit() or str(int(index)) != str(index) or not 0 <= int(index) < len(doc["tracks"]):
            raise ValueError("Invalid layer-map source track index: " + str(index))
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Layer-map names must be nonempty strings")
    tracks = [({**t, "name": layer_map.get(str(i), t["name"])}, list(resolved(t)))
              for i, t in enumerate(doc["tracks"])]
    frame_count = max(len(f) for _,f in tracks)
    if frame_count > 65535 or any(len(f) != frame_count for _,f in tracks):
        raise ValueError("This exporter requires equal track lengths within uint16")
    if len({t["name"] for t,_ in tracks}) != len(tracks):
        raise ValueError("Duplicate layer names require an explicit rename mapping")
    for _,frames in tracks:
        for f in frames:
            if f.get("font") or f.get("text") or f["f"] > 0:
                raise ValueError("Text/font or sprite-cell f>0 needs an explicit adapter")
    images = []
    for name,path in sorted(m["imageMap"].items()):
        image = Image.open(bundle/"files"/safe_path(path)).convert("RGBA")
        images.append((name,image))
    if not images:
        raise ValueError("No images")
    # PVZHE 0.30 removes media 65535 while hydrating DAT into packed frames.
    # A valid transparent media keeps non-drawing attachment/root-motion poses.
    control_name = "__pvz_control__"
    if control_name in m["imageMap"]:
        raise ValueError("Reserved control media name collision")
    images.append((control_name, Image.new("RGBA", (1, 1))))
    # Deterministic shelf packing, with a transparent gutter to prevent filtering bleed.
    width = max(2048, max(i.width+2 for _,i in images))
    rects, x, y, row = {}, 1, 1, 0
    for name,image in images:
        if x+image.width+1 > width:
            x=1; y+=row+2; row=0
        rects[name]=(x,y,image.width,image.height)
        x+=image.width+2; row=max(row,image.height)
    height = y+row+1
    if width > 16384 or height > 16384 or len(images) >= 65535:
        raise ValueError("Atlas exceeds this exporter's limits")
    atlas = Image.new("RGBA",(width,height))
    for name,image in images:
        atlas.paste(image,rects[name][:2])
    ids = {name:i for i,(name,_) in enumerate(images)}
    data = bytearray()
    def put(fmt,*values): data.extend(struct.pack("<"+fmt,*values))
    def string(value):
        b=value.encode("utf-8"); put("I",len(b)); data.extend(b)
    put("fHHHQ",doc["fps"],frame_count,width,height,width*height*4)
    data.extend(atlas.tobytes())
    put("H",len(images))
    for name,_ in images:
        string(name); put("4f",*rects[name])
    put("H",len(tracks))
    # Reanim tracks are back-to-front; preserve that order for DAT layers.
    for track,frames in tracks:
        string(track["name"])
        for f in frames:
            image=f.get("image")
            # Hidden image layers may still be attachment tracks. Retain their pose.
            put("HH",1,ids[image] if image and f["f"] >= 0 else ids[control_name])
            put("6f",*matrix(f))
            put("I",0xffffff00 | round(max(0.,min(1.,f["a"]))*255))
    clips = {}
    for track,frames in tracks:
        if track["name"].lower().startswith("anim_"):
            active=[i for i,f in enumerate(frames) if f["f"]>=0]
            if active:
                clips[track["name"]]=[min(active),max(active)+1]
    put("H",len(clips))
    for name,(start,end) in clips.items():
        string(name); put("HH",start,end)
    put("H",0)  # Source has no game fire-event contract; binding is a separate step.
    output.mkdir(parents=True,exist_ok=True)
    target=output/"animation.dat"; target.write_bytes(data)
    atlas.save(output/"atlas.png")
    result={"target":"PVZHE 0.30 DAT", "exporterVersion":2, "pakSha256":m["pakSha256"],
            "sourceAnimationSha256":m["animationSha256"],"datSha256":digest(data),
            "pillowVersion":pillow_version,"frameCount":frame_count,"fps":doc["fps"],
            "layers":[t["name"] for t,_ in tracks],"clipsHalfOpen":clips,
            "sourceLayers":[{"index":i,"sourceName":t["name"],"targetName":tracks[i][0]["name"]}
                            for i,t in enumerate(doc["tracks"])],
            "atlasSize":[width,height],"mediaCount":len(images),"controlMedia":control_name,
            "unbound":["sprite scene and part-following", "fire timing/events", "gameplay", "card/almanac"],
            "notes":["Raw tracks retained; no custom_idle/custom_shoot", "Matrix interpolation may differ between engines"]}
    write_json(output/"conversion.json",result)
    return result


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle",required=True); p.add_argument("--out",required=True)
    p.add_argument("--layer-map",help="UTF-8 JSON object mapping original zero-based track indices to unique layer names")
    a=p.parse_args()
    mapping=json.loads(Path(a.layer_map).read_text(encoding="utf-8")) if a.layer_map else None
    print(json.dumps(convert(a.bundle,a.out,mapping),ensure_ascii=False))
