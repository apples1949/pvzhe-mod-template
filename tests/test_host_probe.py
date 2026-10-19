"""Exercise reflection discovery using a tiny assembly, without game files."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("dotnet"), "HostProbe integration requires the .NET SDK")
class HostProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sdks = subprocess.run(["dotnet", "--list-sdks"], check=True, capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
        if not any(line.lstrip().startswith("9.") for line in sdks.splitlines()):
            raise unittest.SkipTest("HostProbe integration requires the .NET 9 SDK")
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name)
        # An isolated output also avoids contending with a development/runtime build.
        cls.probe = cls.folder / "probe"
        shutil.copytree(ROOT / "tools/HostProbe", cls.probe,
                        ignore=shutil.ignore_patterns("bin", "obj"))
        cls.fixture = cls.folder / "fixture"
        cls.fixture.mkdir()
        (cls.fixture / "Fixture.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
            '<TargetFramework>net9.0</TargetFramework>'
            '<AssemblyName>PlantsVsZombies</AssemblyName>'
            '</PropertyGroup></Project>', encoding="utf-8")
        (cls.fixture / "Types.cs").write_text("""
namespace PVZHE.ModEditor.ModSystem {
    public interface IXWModRuntimeEntry {}
    public class XWModRuntimeApi {}
    public class XWModManifest {}
}
public enum SampleKind { First = 2, Second = 7 }
public class ProbeExample {
    public static double Optional(int count = 3, bool ready = true) => count;
    public void References(out int result, ref string text) { result = 1; }
    public void NullValue(string text = null) {}
}
""", encoding="utf-8")
        for project in (cls.probe / "HostProbe.csproj", cls.fixture / "Fixture.csproj"):
            subprocess.run(["dotnet", "build", str(project), "-c", "Release", "--nologo"],
                           check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        cls.executable = cls.probe / "bin/Release/net9.0/HostProbe.dll"
        cls.references = cls.fixture / "bin/Release/net9.0"

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def query(self, *args):
        result = subprocess.run(["dotnet", str(self.executable), str(self.references), *args],
                                check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return json.loads(result.stdout)

    def test_method_details_distinguish_static_defaults_and_reference_parameters(self):
        entry = self.query("--types", "ProbeExample")[0]
        self.assertTrue(any("Optional" in method for method in entry["methods"]))
        methods = {method["name"]: method for method in entry["methodDetails"]}
        optional = methods["Optional"]
        self.assertTrue(optional["isStatic"])
        self.assertEqual([p["name"] for p in optional["parameters"]], ["count", "ready"])
        self.assertEqual([p["defaultValue"] for p in optional["parameters"]], ["3", "True"])
        self.assertTrue(all(p["isOptional"] for p in optional["parameters"]))
        self.assertTrue(methods["NullValue"]["parameters"][0]["hasDefaultValue"])
        self.assertIsNone(methods["NullValue"]["parameters"][0]["defaultValue"])
        references = methods["References"]
        self.assertFalse(references["isStatic"])
        self.assertTrue(references["parameters"][0]["isOut"])
        self.assertFalse(references["parameters"][1]["isOut"])
        self.assertEqual(references["parameters"][1]["type"], "System.String&")

    def test_member_filter_limits_large_type_output(self):
        entry = self.query("--types", "ProbeExample", "--member", "optIONAL")[0]
        self.assertEqual([m["name"] for m in entry["methodDetails"]], ["Optional"])
        self.assertEqual(len(entry["methods"]), 1)
        self.assertFalse(entry["fields"])

    def test_enum_values_and_partial_name_discovery(self):
        entry = self.query("--types", "SampleKind")[0]
        self.assertEqual(entry["enumValues"], {"First": 2, "Second": 7})
        discovery = self.query("--find-types", "probeEXAMPLE")
        self.assertEqual(discovery["loaderErrors"], [])
        self.assertEqual([t["name"] for t in discovery["matches"]], ["ProbeExample"])
        self.assertFalse(self.query("--types", "MissingType")[0]["present"])


if __name__ == "__main__":
    unittest.main()
