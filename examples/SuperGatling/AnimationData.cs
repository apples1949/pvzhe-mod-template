using Godot;
using PVZHE.ModEditor.ModSystem;

namespace SuperGatlingPea;

/// <summary>
/// 载入本 Mod 自有的 reanim 转换 DAT，并补上宿主精灵需要引用的动作别名。
/// 原始时间轴来自经典版 SuperGatling.reanim.compiled，未被裁剪或合成。
/// </summary>
public static class AnimationDataFactory
{
    // anim_idle control track at source frame 0; checked by prepare_assets.py.
    public static readonly Vector2 StemReference = new(37.6f, 48.7f);
    /// <summary>原始片段（半开区间，来自转换报告 conversion.json）。</summary>
    private static readonly (string Name, int Start, int EndExclusive)[] SourceClips =
    {
        ("anim_idle", 0, 25),
        ("anim_head_idle", 25, 50),
        ("anim_shooting", 50, 75),
        ("anim_power", 75, 87),
    };

    /// <summary>宿主精灵与组件使用的动作名 → 原始半开区间别名。</summary>
    private static readonly (string Name, int Start, int EndExclusive)[] HostAliases =
    {
        ("BodyIdle", 0, 25),
        ("HeadIdle", 25, 50),
        ("HeadFire", 50, 75),
        ("HeadPower", 75, 87),
    };

    public static AdobeAnimateData Load(XWModRuntimeContext context)
    {
        string path = Path.Combine(context.PackageRoot, "Assets", "animation.dat");
        if (!File.Exists(path)) throw new FileNotFoundException("缺少动画数据", path);

        var data = new AdobeAnimateData();
        data.SetAnimeFileForModImport(path);
        data.InitForModImport(path);
        if (!data.HasPackedRuntimeData())
            throw new InvalidDataException("animation.dat 未被宿主读取: " + path);

        context.Log($"SGP_DAT: frames={data.frameMax} fps={data.frameRate} layers={data.layerDictionary.Count} media={data.mediaDictionary.Count} clips={data.clips.Count} events={data.events.Count}");

        WriteClips(data, SourceClips, overwrite: true);
        WriteClips(data, HostAliases, overwrite: true);

        // 0.30 在读取 DAT 时缓存事件帧索引；补写事件后必须让宿主按最终表重建。
        WriteFireEvents(data, FrameCount: 7, FirstFrame: 52, LastFrame: 72);
        data.EventFrameIndices = null;
        return data;
    }

    private static void WriteClips(AdobeAnimateData data, (string Name, int Start, int EndExclusive)[] clips, bool overwrite)
    {
        foreach (var (name, start, endExclusive) in clips)
        {
            var id = new StringName(name);
            if (overwrite || !data.clips.ContainsKey(id))
                data.clips[id] = new Vector2I(start, endExclusive);
        }
    }

    /// <summary>在射击片段内均匀写入 fire 事件；数量即一次攻击的弹数。</summary>
    private static void WriteFireEvents(AdobeAnimateData data, int FrameCount, int FirstFrame, int LastFrame)
    {
        if (FrameCount <= 0) return;
        while (data.events.Count < data.frameMax) data.events.Add(new Godot.Collections.Array());
        for (int index = 0; index < FrameCount; index++)
        {
            int frame = FrameCount == 1
                ? FirstFrame
                : FirstFrame + (int)Math.Round((double)(LastFrame - FirstFrame) * index / (FrameCount - 1));
            var list = data.events[frame];
            list.Add(new Godot.Collections.Dictionary
            {
                { "Command", "fire" },
                { "Argument", string.Empty },
            });
        }
    }
}
