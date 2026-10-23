"""Load the same compiled adapter against old/new host assemblies, not just recompile it."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which('dotnet'), 'Optional .NET SDK unavailable')
class FireRayBinaryTests(unittest.TestCase):
    def test_old_binary_handles_both_released_signatures_and_rejects_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            host = root / 'host'; host.mkdir()
            app = root / 'app'; app.mkdir()
            props = '<TargetFramework>net9.0</TargetFramework><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings>'
            (host / 'Host.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>' + props + '</PropertyGroup></Project>', encoding='utf-8')
            (app / 'App.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>' + props + '</PropertyGroup><ItemGroup><ProjectReference Include="../host/Host.csproj" /></ItemGroup></Project>', encoding='utf-8')
            source = Path(__file__).resolve().parents[1] / 'examples/SuperGatling/FireRayQuery.cs'
            shutil.copyfile(source, app / source.name)
            (app / 'Program.cs').write_text('''using SuperGatlingPea;
try {
    var hit=FireRayQuery.Check(new FireComponent(),new AabbRay2DResource(),37,2);
    if(hit?.Value!=39) throw new Exception("Wrong query arguments or combat filter");
    Console.WriteLine("QUERY_PASS");
} catch(TypeInitializationException error) when(error.InnerException is InvalidOperationException) {
    Console.WriteLine("UNSUPPORTED_REJECTED");
}
''', encoding='utf-8')
            def host_code(parameters, body):
                (host / 'Api.cs').write_text('public class AabbRay2DResource {}\npublic class TowerDefenseCharacter { public int Value; }\npublic class FireComponent { public TowerDefenseCharacter CheckRayHit(' + parameters + ') { ' + body + ' } }', encoding='utf-8')
            def run(*args):
                result = subprocess.run(['dotnet', *map(str, args)], capture_output=True, text=True, encoding='utf-8', errors='replace')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout
            first = 'AabbRay2DResource ray,int flags,int index'
            host_code(first, 'return new() {Value=flags+index};')
            run('build', app / 'App.csproj', '-c', 'Release', '--nologo')
            output = app / 'bin/Release/net9.0'; binary = (output / 'App.dll').read_bytes()
            self.assertIn('QUERY_PASS', run(output / 'App.dll'))
            host_code(first + ',bool combatTargetsOnly=false', 'return new() {Value=combatTargetsOnly ? -1 : flags+index};')
            run('build', host / 'Host.csproj', '-c', 'Release', '--nologo')
            shutil.copyfile(host / 'bin/Release/net9.0/Host.dll', output / 'Host.dll')
            self.assertEqual((output / 'App.dll').read_bytes(), binary)
            self.assertIn('QUERY_PASS', run(output / 'App.dll'))
            host_code('AabbRay2DResource ray,int flags', 'return new() {Value=flags};')
            run('build', host / 'Host.csproj', '-c', 'Release', '--nologo')
            shutil.copyfile(host / 'bin/Release/net9.0/Host.dll', output / 'Host.dll')
            self.assertIn('UNSUPPORTED_REJECTED', run(output / 'App.dll'))
