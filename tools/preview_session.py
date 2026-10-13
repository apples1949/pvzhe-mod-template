"""Bind a freshly captured placement config to the prepared release and Mod DLL."""
import argparse
import json
from pathlib import Path
from game_cache import GameCache, sha, save
from placement_model import Session


def bind(config_path, assembly, work, output):
    config_path, assembly, work, output = (Path(p).resolve() for p in (config_path,assembly,work,output))
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    release = json.loads((work / "release.json").read_text(encoding="utf-8"))
    cache = GameCache(work,release)
    # Absolute asset paths preserve resolution when output is in a separate session directory.
    for layout in config["layouts"]:
        if layout.get("background"):
            layout["background"] = str((config_path.parent/layout["background"]).resolve())
        for item in layout["objects"]:
            if item.get("image"):
                item["image"] = str((config_path.parent/item["image"]).resolve())
    config.setdefault("context", {})["previewProvenance"] = dict(workDir=str(work),
        releaseCacheKey=cache.key,modAssembly=str(assembly),modAssemblySha256=sha(assembly))
    Session(config,output.parent)
    save(output,config)
    return cache.key


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",required=True)
    parser.add_argument("--mod-assembly",required=True)
    parser.add_argument("--work",default=str(Path(__file__).resolve().parents[1]/".work"))
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    try:
        key=bind(args.config,args.mod_assembly,args.work,args.output)
        print("Bound preview to release cache:",key)
    except (ValueError,KeyError,OSError) as error:
        parser.exit(2,f"Preview preparation failed: {error}\n")

if __name__=="__main__":main()
