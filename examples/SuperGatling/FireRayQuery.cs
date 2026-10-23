using System.Reflection;

namespace SuperGatlingPea;

// Optional parameters are a source-level convenience, not binary compatibility.
// Resolve the released signature once, rather than binding the DLL to one arity.
internal static class FireRayQuery
{
    static readonly MethodInfo Method = Resolve();
    static readonly bool WithCombatFilter = Method.GetParameters().Length == 4;
    internal static void Validate() { _ = Method; }

    static MethodInfo Resolve()
    {
        Type[] first = [typeof(AabbRay2DResource), typeof(int), typeof(int)];
        var method = typeof(FireComponent).GetMethod("CheckRayHit", [.. first, typeof(bool)])
            ?? typeof(FireComponent).GetMethod("CheckRayHit", first);
        if (method == null || method.IsStatic || method.ReturnType != typeof(TowerDefenseCharacter))
            throw new InvalidOperationException("Unsupported released FireComponent.CheckRayHit signature");
        return method;
    }

    internal static TowerDefenseCharacter? Check(FireComponent source, AabbRay2DResource ray, int flags, int index)
    {
        // Preserve the old ray-query semantics. Catapult-only filtering is separate.
        object[] args = WithCombatFilter ? [ray, flags, index, false] : [ray, flags, index];
        return (TowerDefenseCharacter?)Method.Invoke(source, args);
    }
}
