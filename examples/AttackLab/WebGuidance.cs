namespace AttackLab;

// Delay is measured from projectile creation, including formation deployment.
public static class WebGuidance
{
    public static bool Active(double strength,double age,double delay=.5)
        =>strength==2||strength==1&&age>=delay-1e-9;
}
