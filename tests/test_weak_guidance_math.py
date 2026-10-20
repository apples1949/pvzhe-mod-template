import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from attack_plan import new_item,steer_angle

class WeakGuidanceMathTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("dotnet"),"Optional .NET SDK unavailable")
    def test_csharp_response_matches_editor_for_strength_and_angular_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=Path(__file__).resolve().parents[1]/"examples/SuperGatling/WeakGuidanceMath.cs"
            shutil.copyfile(source,root/"WeakGuidanceMath.cs")
            (root/"MathTest.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net9.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings></PropertyGroup></Project>')
            (root/"Program.cs").write_text('''using SuperGatlingPea;
using System.Globalization;
CultureInfo.CurrentCulture=CultureInfo.InvariantCulture;
foreach(double strength in new double[]{0,.5,1,1.5,2})
foreach(double degrees in new double[]{-170,-90,0,10,90,170})
Console.WriteLine($"TURN:{strength}|{degrees}|{WeakGuidanceMath.Turn(0,degrees*Math.PI/180,strength,1.0/30):R}");
''')
            result=subprocess.run(["dotnet","run","--project",str(root/"MathTest.csproj"),"-c","Release"],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            rows=[line[5:].split("|") for line in result.stdout.splitlines() if line.startswith("TURN:")]
            self.assertEqual(len(rows),30)
            for strength,degrees,actual in rows:
                guide=new_item()["guidance"];guide["trackingStrength"]=float(strength)
                self.assertAlmostEqual(float(actual),steer_angle(0,math.radians(float(degrees)),guide,1/30),places=10)
