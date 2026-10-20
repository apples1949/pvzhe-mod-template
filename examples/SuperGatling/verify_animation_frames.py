"""Image-space motion gate for this example's fixed 800x444 animation fixture.

This dark helmet probe is deliberately specific to the fixture. It is not a
universal character detector and must not be reused after changing its camera,
plant position, palette or capture resolution without recalibration.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

REGION = (240, 190, 315, 222)


def measure(path):
    with Image.open(path) as image:
        if image.size != (800, 444):
            raise ValueError("Unexpected capture size: " + str(image.size))
        pixels = image.convert("RGB")
        points = []
        for y in range(REGION[1], REGION[3]):
            for x in range(REGION[0], REGION[2]):
                r, g, b = pixels.getpixel((x, y))
                if r < 45 and g < 45 and b < 60:
                    points.append(x)
        if len(points) < 40:
            raise ValueError("Helmet probe missing in " + path.name)
        return {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "minX": min(points), "maxX": max(points), "meanX": sum(points) / len(points)}


def assess(runtime):
    groups = {}
    for label in ("idle", "negative-detached"):
        frames = sorted(runtime.glob("audit-animation-" + label + "-*.png"))
        if len(frames) < (20 if label == "idle" else 10):
            raise ValueError("Incomplete image sequence: " + label)
        samples = [measure(frame) for frame in frames]
        groups[label] = {"samples": samples,
                         "meanXSpan": max(s["meanX"] for s in samples) - min(s["meanX"] for s in samples),
                         "leftXSpan": max(s["minX"] for s in samples) - min(s["minX"] for s in samples)}
    positive, negative = groups["idle"], groups["negative-detached"]
    return {"passed": positive["meanXSpan"] >= 4 and positive["leftXSpan"] >= 4 and negative["meanXSpan"] < 3,
            "scope": "fixed fixture helmet screen-X, default capture resolution; not node coordinates",
            "region": REGION, "groups": groups,
            "runtimeIdentity": json.loads((runtime / "identity.json").read_text(encoding="utf-8")),
            "checkerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = assess(args.runtime)
    except (ValueError, OSError) as error:
        result = {"passed": False, "error": str(error), "groups": {}}
    (args.runtime / "image-assessment.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "screenXSpans": {
        label: group["meanXSpan"] for label, group in result["groups"].items()},
        "error": result.get("error")}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
