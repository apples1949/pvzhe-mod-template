"""Extract a small reuse catalog from released PCK/DLL, without copying game assets."""
import json
import re
from pck import Pack
from mod import ROOT, WORK, PROBE, probe_build, run, verify_references, write_json

COMPONENTS = {
    "main-button": "Prefab/GUI/Button/MainButton.tscn",
    "tips-dialog": "Prefab/GUI/DialogBox/DialogBoxGeneral/DialogBoxTips/DialogBoxTips.tscn",
    "choose-dialog": "Prefab/GUI/DialogBox/DialogBoxGeneral/DialogBoxChoose/DialogBoxChoose.tscn",
    "input-dialog": "Prefab/GUI/DialogBox/DialogBoxGeneral/DialogBoxInput/DialogBoxInput.tscn",
    "dialog-frame": "Prefab/GUI/DialogBox/DialogBoxGeneral/DialogPopup.tscn",
    "theme": "Asset/Theme/MainTheme.tres",
}
TYPES = ["MainButton", "NinePatchButtonBase", "DialogManager", "DialogBoxBase", "DialogBoxTips",
         "DialogBoxChoose", "DialogBoxInput", "LevelCatalogConfig", "LevelChapterConfig", "LevelChooseConfig",
         "TowerDefenseLevelNewConfig", "TowerDefenseLevelSeedBankConfig", "TowerDefenseLevelPacketBankConfig",
         "TowerDefenseLevelPacketConfig", "DragMenuSelectItem", "TowerDefenseManager"] + ["PVZHE.ModEditor.ModSystem." + n for n in (
             "XWModPresentationPoints", "XWModLifecyclePoints", "XWModCharacterPoints", "XWModCharacterSnapshot",
             "XWModSettings", "XWModSettingDefinition", "XWModContentApi", "XWModLevelIdentity",
             "XWModLevelValidation", "XWModEconomyService", "XWModDataService", "XWModCombatService")]


def scene_facts(pack, path):
    if path not in pack.entries:
        return {"path": "res://" + path, "present": False}
    text = pack.read(path).decode("utf-8")
    dependencies = sorted(set(re.findall(r'path="(res://[^"\n]+)"', text)))
    return {"path": "res://" + path, "present": True,
            "nodes": re.findall(r'^\[node[^\n]*', text, re.MULTILINE),
            "dependencies": [{"path": dep, "indexed": any(dep[6:] + suffix in pack.entries
                               for suffix in ("", ".remap", ".import"))} for dep in dependencies],
            "evidence": "static-release-index; runtime status is documented separately"}


def main():
    release = verify_references()
    pack = Pack(release["pck"])
    probe_build()
    api = json.loads(run("dotnet", PROBE, WORK / "references", "--types", *TYPES, capture=True))
    write_json(WORK / "reuse-catalog.json", {"release": release,
               "components": {key: scene_facts(pack, path) for key, path in COMPONENTS.items()}, "types": api})
    print("Release reuse catalog: .work/reuse-catalog.json (paths and interfaces only, no assets)")


if __name__ == "__main__":
    main()
