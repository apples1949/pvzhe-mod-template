using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;

var dir = Path.GetFullPath(args[0]);
AssemblyLoadContext.Default.Resolving += (_, name) =>
    File.Exists(Path.Combine(dir, name.Name + ".dll"))
        ? AssemblyLoadContext.Default.LoadFromAssemblyPath(Path.Combine(dir, name.Name + ".dll")) : null;
var host = AssemblyLoadContext.Default.LoadFromAssemblyPath(Path.Combine(dir, "PlantsVsZombies.dll"));
const string ns = "PVZHE.ModEditor.ModSystem.";
var contract = host.GetType(ns + "IXWModRuntimeEntry", true)!;
var api = host.GetType(ns + "XWModRuntimeApi", true)!;
var manifest = host.GetType(ns + "XWModManifest", true)!;
if (args.Length > 1)
{
    var mod = AssemblyLoadContext.Default.LoadFromAssemblyPath(Path.GetFullPath(args[1]));
    var entry = mod.GetType(args[2], true)!;
    if (!contract.IsAssignableFrom(entry) || entry.GetConstructor(Type.EmptyTypes) == null)
        throw new InvalidOperationException("Entry must implement the released host contract with a public empty constructor.");
    Console.WriteLine("Entry contract verified against released assembly.");
}
else
{
    Console.WriteLine(JsonSerializer.Serialize(new
    {
        assemblyVersion = host.GetName().Version?.ToString(),
        runtimeApiVersion = api.GetField("CurrentVersion")!.GetRawConstantValue(),
        schemaVersion = manifest.GetField("CurrentSchemaVersion")!.GetRawConstantValue(),
        entryMethods = contract.GetMethods().Select(m => m.ToString()),
        manifestFields = manifest.GetProperties().Select(p => p.Name),
        extensionTypes = new[] { "XWModHooks", "XWModLifetime", "XWModPresentationService", "XWModContentApi", "XWModRuntimeContext" }
            .Select(name => host.GetType(ns + name)).OfType<Type>()
            .Select(t => new { t.FullName, methods = t.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly).Select(m => m.ToString()) })
    }, new JsonSerializerOptions { WriteIndented = true }));
}
