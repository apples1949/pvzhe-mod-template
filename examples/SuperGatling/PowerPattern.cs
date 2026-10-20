using Godot;
using PVZHE.ModEditor.ModSystem;
namespace SuperGatlingPea;

// Compiled from design/attacks/power.json after explicit editor confirmation.
public sealed class PowerPattern
{
    public readonly record struct Shot(double Time, Vector2 Offset, Vector2 Velocity,float TrackingStrength);
    public Shot[] Shots { get; }
    public double RoundIntervalSeconds { get; }
    public int RoundCount { get; }
    PowerPattern(Shot[] shots,double interval,int rounds) { Shots=shots;RoundIntervalSeconds=interval;RoundCount=rounds; }
    public static PowerPattern Load(XWModRuntimeContext context)
    {
        using var file=Godot.FileAccess.Open(Path.Combine(context.PackageRoot,"Assets","power-pattern.json"),Godot.FileAccess.ModeFlags.Read);
        if(file==null) throw new IOException("Missing power-pattern.json");
        var json=new Json();
        if(json.Parse(file.GetAsText())!=Error.Ok) throw new InvalidDataException("Invalid power pattern JSON");
        var root=json.Data.AsGodotDictionary();
        if(root["schemaVersion"].AsInt32()!=3) throw new InvalidDataException("Unsupported power pattern");
        double interval=root["roundIntervalSeconds"].AsDouble();
        double window=root["emissionWindowSeconds"].AsDouble();
        int rounds=root["roundCount"].AsInt32(),perRound=root["shotsPerRound"].AsInt32();
        if(double.IsNaN(interval)||double.IsInfinity(interval)||interval<.1||interval>30||window<=0||window>60||rounds<1||perRound<1)
            throw new InvalidDataException("Invalid power cadence");
        var values=root["shots"].AsGodotArray();
        if(values.Count==0 || values.Count>6000 || (long)rounds*perRound!=values.Count) throw new InvalidDataException("Invalid power shot count");
        var shots=new Shot[values.Count]; double previous=0;
        for(int i=0;i<values.Count;i++) {
            var item=values[i].AsGodotDictionary(); double time=item["time"].AsDouble();
            var offset=item["offset"].AsGodotArray(); var velocity=item["velocity"].AsGodotArray();
            if(double.IsNaN(time)||double.IsInfinity(time)||time<previous||time>60||offset.Count!=2||velocity.Count!=2)
                throw new InvalidDataException("Invalid power shot");
            float strength=item["trackingStrength"].AsSingle();
            if(float.IsNaN(strength)||strength<0||strength>2)throw new InvalidDataException("Invalid tracking strength");
            shots[i]=new Shot(time,new Vector2(offset[0].AsSingle(),offset[1].AsSingle()),new Vector2(velocity[0].AsSingle(),velocity[1].AsSingle()),strength);
            previous=time;
        }
        return new PowerPattern(shots,interval,rounds);
    }
}
