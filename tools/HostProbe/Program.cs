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
if (args.Length > 1 && args[1] == "--types")
{
    int memberIndex = Array.IndexOf(args, "--member");
    string? memberFilter = null;
    if (memberIndex >= 0)
    {
        if (memberIndex < 3 || memberIndex != args.Length - 2 || string.IsNullOrWhiteSpace(args[^1]))
            throw new ArgumentException("--member requires type names followed by one nonempty member-name fragment.");
        memberFilter = args[^1];
    }
    bool Include(MemberInfo member) => memberFilter == null || member.Name.Contains(memberFilter, StringComparison.OrdinalIgnoreCase);
    var names = memberIndex < 0 ? args.Skip(2) : args.Skip(2).Take(memberIndex - 2);
    Console.WriteLine(JsonSerializer.Serialize(names.Select(name =>
    {
        var type = host.GetType(name);
        const BindingFlags flags = BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;
        return new
        {
            name, present = type != null, baseType = type?.BaseType?.FullName,
            methods = type?.GetMethods(flags).Where(Include).Select(m => m.ToString()),
            methodDetails = type?.GetMethods(flags).Where(Include).Select(m => new
            {
                signature = m.ToString(), name = m.Name, isStatic = m.IsStatic,
                parameters = m.GetParameters().Select(p => new
                {
                    name = p.Name, type = p.ParameterType.FullName, isOut = p.IsOut,
                    isOptional = p.IsOptional, hasDefaultValue = p.HasDefaultValue,
                    defaultValue = p.HasDefaultValue && p.DefaultValue != null ? Convert.ToString(p.DefaultValue, System.Globalization.CultureInfo.InvariantCulture) : null
                })
            }),
            enumValues = type?.IsEnum == true
                ? type.GetFields(flags).Where(f => f.IsLiteral).ToDictionary(f => f.Name, f => f.GetRawConstantValue()) : null,
            properties = type?.GetProperties(flags).Where(Include).Select(p => p.ToString()),
            fields = type?.GetFields(flags).Where(Include).Select(f => f.ToString()),
            events = type?.GetEvents(flags).Where(Include).Select(e => e.ToString())
        };
    }), new JsonSerializerOptions { WriteIndented = true }));
}
else if (args.Length > 1 && args[1] == "--find-types")
{
    if (args.Length != 3 || string.IsNullOrWhiteSpace(args[2]))
        throw new ArgumentException("--find-types requires one nonempty name fragment.");
    Type[] types;
    string[] loaderErrors = Array.Empty<string>();
    try { types = host.GetTypes(); }
    catch (ReflectionTypeLoadException error)
    {
        types = error.Types.OfType<Type>().ToArray();
        loaderErrors = error.LoaderExceptions.Select(e => e?.Message ?? "Unknown loader failure").Distinct().ToArray();
    }
    Console.WriteLine(JsonSerializer.Serialize(new
    {
        matches = types.Where(t => (t.IsPublic || t.IsNestedPublic) &&
            t.Name is not ("MethodName" or "PropertyName" or "SignalName") &&
            (t.FullName ?? t.Name).Contains(args[2], StringComparison.OrdinalIgnoreCase))
            .Select(t => new { name = t.FullName, baseType = t.BaseType?.FullName }),
        loaderErrors
    }, new JsonSerializerOptions { WriteIndented = true }));
}
else if (args.Length > 1)
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
