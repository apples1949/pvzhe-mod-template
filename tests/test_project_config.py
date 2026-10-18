import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mod


class ProjectConfigTests(unittest.TestCase):
    def write_config(self, root, **changes):
        value = {"schemaVersion": 1, "project": "src/MyMod/MyMod.csproj", "assemblyName": "MyMod"}
        value.update(changes)
        (root / "mod-project.json").write_text(json.dumps(value), encoding="utf-8")

    def test_default_and_feature_lab_are_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.multiple(mod, ROOT=root, EXAMPLE="hello-world"):
                self.assertEqual(mod.build_target(), (root / "src/HelloMod/HelloMod.csproj", "HelloMod"))
                (root / "mod-project.json").write_text("invalid", encoding="utf-8")
                with self.assertRaises(ValueError):
                    mod.build_target()
            with patch.multiple(mod, ROOT=root, EXAMPLE="feature-lab"):
                self.assertEqual(mod.build_target(), (root / "examples/FeatureLab/FeatureLab.csproj", "FeatureLab"))

    def test_invalid_config_never_falls_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "src/MyMod/MyMod.csproj"
            project.parent.mkdir(parents=True)
            project.write_text("<Project />")
            with patch.multiple(mod, ROOT=root, EXAMPLE="hello-world"):
                for changes in ({"schemaVersion": True}, {"schemaVersion": 2}, {"extra": "ignored?"},
                                {"project": "../outside.csproj"}, {"project": str(project)},
                                {"project": "missing.csproj"}, {"assemblyName": "../Host"},
                                {"assemblyName": "GodotSharp"}, {"assemblyName": "PlantsVsZombies"},
                                {"assemblyName": "MyMod.dll"}, {"assemblyName": ""}):
                    self.write_config(root, **changes)
                    with self.subTest(changes=changes), self.assertRaises(ValueError):
                        mod.build_target()
                self.write_config(root)
                self.assertEqual(mod.build_target(), (project, "MyMod"))

    def test_build_packages_selected_assembly_and_records_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "src/MyMod/MyMod.csproj"
            project.parent.mkdir(parents=True)
            project.write_text("<Project />")
            self.write_config(root)
            output = project.parent / "bin/Release/net9.0/MyMod.dll"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"MZ-selected-assembly")
            wrong = root / "src/HelloMod/bin/Release/net9.0/HelloMod.dll"
            wrong.parent.mkdir(parents=True)
            wrong.write_bytes(b"MZ-wrong-default")
            manifest = {"id": "test.project", "name": "Project", "author": "Tester", "version": "0.1.0",
                        "runtimeAssembly": "Runtime/ModAssembly.dll", "runtimeEntryType": "MyMod.Entry"}
            dist = root / "dist"
            package = dist / "test.project.pmod"
            with patch.multiple(mod, ROOT=root, DIST=dist, PACKAGE=package, EXAMPLE="hello-world"), \
                    patch.object(mod, "manifest", return_value=manifest), \
                    patch.object(mod, "verify_references", return_value={}), \
                    patch.object(mod, "probe_build"), patch.object(mod, "run") as run:
                mod.build(SimpleNamespace())
                self.assertEqual(run.call_args_list[0].args[2], project)
                with zipfile.ZipFile(package) as archive:
                    self.assertEqual(set(archive.namelist()), {"mod.json", "Runtime/ModAssembly.dll"})
                    self.assertEqual(archive.read("Runtime/ModAssembly.dll"), b"MZ-selected-assembly")
                info = json.loads((dist / "build-info.json").read_text(encoding="utf-8"))
                self.assertEqual(info["assemblyName"], "MyMod")
                self.assertEqual(info["project"], "src/MyMod/MyMod.csproj")


if __name__ == "__main__":
    unittest.main()
