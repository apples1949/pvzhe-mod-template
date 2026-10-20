namespace SuperGatlingPea;

// Same finite-turn response as the attack editor; not the host's snap-to-target mode.
public static class WeakGuidanceMath
{
    public static double Turn(double angle,double wanted,double strength,double delta)
    {
        if(strength<=0)return angle;
        double maximum,response,falloff;
        if(strength<=1){maximum=120*strength;response=3*strength;falloff=2;}
        else{double blend=strength-1;maximum=120+1320*blend;response=3+21*blend;falloff=2-1.5*blend;}
        double error=(wanted-angle+Math.PI)%(2*Math.PI);
        if(error<0)error+=2*Math.PI;
        error-=Math.PI;
        double alignment=.05+.95*Math.Pow(Math.Max(0,Math.Cos(Math.Abs(error)/2)),falloff);
        double correction=error*(1-Math.Exp(-response*alignment*delta));
        double cap=maximum*Math.PI/180*delta;
        return angle+Math.Clamp(correction,-cap,cap);
    }
}
