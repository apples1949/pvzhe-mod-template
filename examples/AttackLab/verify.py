"""Build immutable snapshots and collect/check real released-host attack evidence."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
import mod
from runtime_test import test
from attack_web import compile_recipe

DRIVER='''extends Node
var started=false
func _ready(): process_mode=Node.PROCESS_MODE_ALWAYS
func _process(_delta):
    if started: return
    var button=get_tree().root.find_child("StartButton",true,false)
    if button is BaseButton and button.is_visible_in_tree() and not button.disabled:
        started=true
        button.emit_signal("pressed")
'''


def assess(run,only=None):
    """Offline evidence judgement; never launches the host."""
    run=Path(run)
    userdata=Path((run/'userdata-path.txt').read_text(encoding='utf-8'))
    identity=json.loads((run/'identity.json').read_text(encoding='utf-8'))
    for name,expected_hash in json.loads((run.parent/'design-hashes.json').read_text(encoding='utf-8')).items():
        assert hashlib.sha256((run.parent/name).read_bytes()).hexdigest()==expected_hash,'changed design evidence'
    if '--boundaries' in identity['command']:
        from Verification.boundary_check import check_documents
        documents={p.stem.removeprefix('boundary-'):json.loads(p.read_text(encoding='utf-8')) for p in userdata.glob('boundary-*.json')}
        plans={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (run.parent/'boundary-plans').glob('*.json')}
        for p in userdata.glob('boundary-*.json'):shutil.copyfile(p,run/p.name)
        required={'weak-retarget'} if '--only-weak-boundary' in identity['command'] else None
        if required:assert documents.get('weak-retarget',{}).get('ownerDeathReacquire') is True,'Missing owner-death retarget evidence'
        summary=check_documents(documents,plans,required)
        (run/'boundary-assessment.json').write_text(json.dumps(dict(results=summary,checkerSha256=hashlib.sha256((HERE/'Verification/boundary_check.py').read_bytes()).hexdigest()),indent=2),encoding='utf-8')
        return summary
    required_cases={'fan'} if '--only-fan' in identity['command'] else {'homing'} if '--only-homing' in identity['command'] else {'nested'} if '--only-nested' in identity['command'] else {'starfruit','homing','lob','nested'} if '--second-half' in identity['command'] else {'straight','fan','ring','parallel'}
    captured_selection=[arg.partition('=')[2] for arg in identity['command'] if arg.startswith('--only-case=')]
    if captured_selection:
        assert len(captured_selection)==1 and set(captured_selection)<=required_cases,'Invalid capture selection'
        required_cases=set(captured_selection)
    if only is not None:
        assert only and set(only)<=required_cases,'Offline scope must be a nonempty subset of the captured cases'
        required_cases=set(only)
    totals={'straight':6,'fan':50,'ring':12,'parallel':20,'starfruit':15,'homing':13,'lob':4,'nested':36}
    summary=[]
    for raw in sorted(userdata.glob('attack-lab-*.json')):
        shutil.copyfile(raw,run/raw.name)
        data=json.loads(raw.read_text(encoding='utf-8'));case=data['case']
        if only is not None and case not in required_cases:continue
        design=json.loads((run.parent/'design'/f'{case}.json').read_text(encoding='utf-8'))
        plan=compile_recipe(design)
        expected=[]
        for group in plan['groups']:
            if not group['enabled']:continue
            start=group.get('startDelaySeconds',0)
            round_id=0
            while start+round_id*group['intervalSeconds']<2.4-1e-8:
                for item in group['items']:
                    if item['enabled']:expected.append((group['id'],item['id'],round(start+round_id*group['intervalSeconds']+item['time'],7),item))
                round_id+=1
        births=data['births'];assert len(births)==len(expected)==totals[case],(case,'count',len(births),len(expected))
        # Same-time ordering across groups is intentionally irrelevant.
        actual=sorted(births,key=lambda x:(x['group'],x['item'],x['intended']))
        expected.sort(key=lambda x:(x[0],x[1],x[2]))
        for b,(group,item_id,when,item) in zip(actual,expected):
            assert b['group']==group and b['item']==item_id,(case,'identity')
            assert abs(b['intended']-when)<1e-6,(case,'scheduled time',b,when)
            assert -.001<=b['actual']-when<.055,(case,'actual cadence',b['actual'],when)
            if item['trajectory']['kind']=='straight' and not item['guidance']['initialAim']:
                offset=item['launch'].get('deployment',{}).get('offset',item['launch']['offset'])
                assert math.dist(b['position'],[b['root'][i]+offset[i] for i in (0,1)])<.1,(case,'birth offset')
                speed=item['trajectory']['speed'];angle=math.radians(item['trajectory']['direction'])
                assert math.dist(b['velocity'],[math.cos(angle)*speed,math.sin(angle)*speed])<.1,(case,'birth direction/speed')
            if item['trajectory']['kind']=='straight' and item['guidance']['initialAim'] and 'target' in b:
                frame=item['launch'].get('aimFrame')
                if frame:
                    center=[b['root'][i]+frame['centerOffset'][i] for i in (0,1)]
                    aim=math.atan2(b['target'][1]-center[1],b['target'][0]-center[0]);local=frame['localOffset']
                    position=[center[0]+math.cos(aim)*local[0]-math.sin(aim)*local[1],center[1]+math.sin(aim)*local[0]+math.cos(aim)*local[1]]
                else:
                    position=[b['root'][i]+item['launch']['offset'][i] for i in (0,1)]
                    aim=math.atan2(b['target'][1]-position[1],b['target'][0]-position[0])
                heading=aim+math.radians(item['trajectory']['direction']);speed=item['trajectory']['speed']
                assert math.dist(position,b['position'])<.1,'initial aim origin frame'
                assert math.dist(b['velocity'],[math.cos(heading)*speed,math.sin(heading)*speed])<.1,'initial aim heading'
        items={item['id']:item for g in plan['groups'] for item in g['items']}
        skipped={}
        trace_path=userdata/f'motion-trace-{case}.json'
        if not trace_path.exists() and case=='nested':trace_path=userdata/'motion-trace.json' # Historical evidence only.
        if case=='nested' or case=='fan' and '--only-fan' in identity['command'] or '--only-case='+case in identity['command']:
            assert trace_path.exists(),'Missing required per-frame motion evidence'
        if case in ('nested','fan','ring','straight') and trace_path.exists():
            trace=json.loads(trace_path.read_text(encoding='utf-8'))
            shutil.copyfile(trace_path,run/trace_path.name)
            previous={};birth_by_generation={b['generation']:b for b in births}
            terminal_frames={t['frame'] for t in data.get('terminals',[])}
            for row in trace:
                generation=row['generation'];before=previous.get(generation);previous[generation]=row
                item=items[birth_by_generation[generation]['item']]
                if before is None or item['launch'].get('deployment'):continue
                displacement=[row['x']-before['x'],row['y']-before['y']]
                normal=[row['vx']*row['delta'],row['vy']*row['delta']]
                if math.dist(displacement,normal)<.1:continue
                assert math.hypot(*displacement)<.1,(case,'unexpected native movement',row)
                assert row['physicsFrame']-1 in terminal_frames,(case,'motion skipped without lifecycle evidence',row)
                skipped.setdefault(generation,[]).append((row['age'],row['delta']))
        for sample in data['samples']:
            item=items[sample['item']];potential=[b for b in births if b['item']==sample['item'] and ('generation' not in sample or b['generation']==sample['generation'])]
            assert potential,(case,'unattributed motion')
            t=sample['age'];trajectory=item['trajectory'];guide=item['guidance'];speed=trajectory['speed']
            if trajectory['kind']=='straight' and not guide['initialAim'] and not item['launch'].get('deployment') and guide['trackingStrength']==0:
                elapsed=t-sum(dt for age,dt in skipped.get(sample.get('generation'),[]) if age<=t+1e-8)
                error=min(math.dist(sample['position'],[b['position'][i]+b['velocity'][i]*elapsed for i in (0,1)]) for b in potential)
                assert error<speed*.055+1,(case,'actual motion',error)
            if trajectory['kind']=='parabola':
                b=potential[0];scale=1
                assert 'catapultSpeedScale' not in trajectory,'native catapult must not be rescaled'
                expected_time=math.sqrt(.3)+math.sqrt(2*(300+b['z'])/2000)
                assert abs(b['flightTime']-expected_time)<.001,'native catapult flight time'
                expected_velocity=[(b['target'][0]-10-b['position'][0])/b['flightTime'],(b['target'][1]-b['position'][1])/b['flightTime']]
                assert math.dist(b['velocity'],expected_velocity)<.1,'native snapshot offset and velocity'
                discrete=b['z']-b['ySpeed']*t-1000*t*t-1000*t/data['physicsTicksPerSecond']
                assert abs(sample['z']-discrete)<.1,'native semi-implicit vertical integration'
                assert abs(sample['ySpeed']-(b['ySpeed']+2000*t*scale))<1,(case,'vertical time scale')
                continuous=b['z']-b['ySpeed']*t*scale-1000*(t*scale)**2
                # Released host uses semi-implicit steps; web preview is continuous.
                assert abs(sample['z']-continuous)<1000*t*scale**2*.055+1,(case,'parabolic height')
                assert math.dist(sample['position'],[b['position'][i]+b['velocity'][i]*t for i in (0,1)])<math.hypot(*b['velocity'])*.055+1,(case,'parabolic horizontal motion')
            if guide['trackingStrength']>0:
                assert abs(math.hypot(*sample['velocity'])-speed)<.1,(case,'guidance speed changed')
        if case in ('straight','ring'):
            assert data['hits']==0 and data['ranges'], 'short range must expire before the distant target'
            for r in data['ranges']:
                assert abs(r['limit']-2.5)<1e-6,'fractional grid distance must survive mapping'
                assert r['limit']<=r['distance']<r['limit']+r['step']+.001,'range exceeded native step budget'
        if case=='parallel':
            assert data['deploymentSamples']>0
            samples=[s for s in data['samples'] if s['deployment']]
            assert samples and all(s['hitOver'] for s in samples),'deployment must suppress hit processing'
        if case=='homing':
            assert data['guidanceSamples']>0 and data['hits']>0 and data['targetHP']<1000000
            delayed=[s for s in data['samples'] if s['item']=='weak-shot-0']
            early=[s for s in delayed if s['age']<.5]
            later=[s for s in delayed if s['age']>=.55]
            assert early and all(not s['nativeTracking'] and abs(math.degrees(math.atan2(s['velocity'][1],s['velocity'][0]))-70)<.1 for s in early),'Delay did not keep launch direction'
            assert later and all(s['nativeTracking'] for s in later),'Delay did not enable host tracking'
            assert all(s['nativeTracking'] for s in data['samples'] if s['item']=='strong-shot-0'),'strong tracking must be owned by host'
            strong=next(s for s in data['samples'] if s['item']=='strong-shot-0')
            assert abs(abs(math.degrees(math.atan2(strong['velocity'][1],strong['velocity'][0])))-180)>10,'strong guidance did not turn around'
        if case=='lob':
            speeds={b['group']:math.hypot(*b['velocity']) for b in births}
            assert len(speeds)==2 and all(b['flightTime']>1 and b['z']>70 for b in births)
            # Both real native arcs advance, not only an emitted launch request.
            assert any(s['z']>200 for s in data['samples'])
        summary.append(dict(case=case,births=len(births),hits=data['hits'],samples=len(data['samples']),motionChecked=True,
                            nativeSkippedMotionSteps=sum(map(len,skipped.values())),continuousTimeMatch=False if skipped else None,passed=True))
    if {s['case'] for s in summary}!=required_cases:raise ValueError('Missing or unexpected case evidence')
    report='business-assessment.json' if only is None else 'business-assessment-'+'-'.join(sorted(required_cases))+'.json'
    (run/report).write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


def build(run,audit,boundaries=False):
    folder=run/'build';folder.mkdir(parents=True)
    for source in HERE.glob('*.cs'):shutil.copyfile(source,folder/source.name)
    if audit:
        for source in (HERE/'Verification').glob('*.cs'):shutil.copyfile(source,folder/source.name)
    refs=ROOT/'.work/references'
    project='<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net9.0</TargetFramework><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings><AssemblyName>AttackLab</AssemblyName></PropertyGroup><ItemGroup>'+''.join(f'<Reference Include="{n}"><HintPath>{escape(str(refs/(n+".dll")))}</HintPath><Private>false</Private></Reference>' for n in ('PlantsVsZombies','GodotSharp'))+'</ItemGroup></Project>'
    (folder/'AttackLab.csproj').write_text(project,encoding='utf-8')
    subprocess.run(['dotnet','build',str(folder/'AttackLab.csproj'),'-c','Release','--nologo'],check=True)
    binary=folder/'bin/Release/net9.0/AttackLab.dll'
    if not audit:
        contents=binary.read_bytes()
        for token in ('RunAudit','RunBoundaries','MotionTrace','Births','attack.lab.audit','AuditPlans'):
            assert token.encode() not in contents and token.encode('utf-16le') not in contents,'audit code leaked into production DLL'
    subprocess.run(['dotnet','run','--project',str(ROOT/'tools/HostProbe'),'--',str(refs),str(binary),'AttackLab.Entry'],check=True,stdout=subprocess.DEVNULL)
    package=run/'attack-lab.pmod';manifest=json.loads((HERE/'mod/mod.json').read_text(encoding='utf-8'))
    (run/'design').mkdir()
    for recipe in (HERE/'design').glob('*.json'):
        shutil.copyfile(recipe,run/'design'/recipe.name)
        plan=compile_recipe(json.loads(recipe.read_text(encoding='utf-8')))
        assert plan==json.loads((HERE/'mod/Assets'/recipe.name).read_text(encoding='utf-8')), 'stale compiled plan'
    if boundaries:
        from Verification.boundary_plans import boundary_designs
        (run/'boundary-design').mkdir();(run/'boundary-plans').mkdir()
        for name,design in boundary_designs().items():
            (run/'boundary-design'/f'{name}.json').write_text(json.dumps(design,indent=2),encoding='utf-8')
            (run/'boundary-plans'/f'{name}.json').write_text(json.dumps(compile_recipe(design),indent=2),encoding='utf-8')
            manifest['resources'].append(f'AuditPlans/{name}.json')
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('mod.json',json.dumps(manifest,ensure_ascii=False));z.write(binary,'Runtime/ModAssembly.dll')
        for name in manifest['resources']:z.write(run/'boundary-plans'/Path(name).name if name.startswith('AuditPlans/') else HERE/'mod'/name,name)
    mod.check_package(package)
    hashes={str(p.relative_to(run)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('design','boundary-design','boundary-plans') for p in (run/folder).glob('*.json')}
    (run/'design-hashes.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    return package


def negative_checks(run):
    """Corrupt copied evidence only; prove the offline checker cannot pass missing/bad results."""
    source=Path(run).resolve();userdata=Path((source/'userdata-path.txt').read_text(encoding='utf-8'))
    identity=json.loads((source/'identity.json').read_text(encoding='utf-8'))
    if '--boundaries' in identity['command']:
        import copy
        from Verification.boundary_check import check_documents
        documents={p.stem.removeprefix('boundary-'):json.loads(p.read_text(encoding='utf-8')) for p in userdata.glob('boundary-*.json')}
        plans={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (source.parent/'boundary-plans').glob('*.json')}
        required={'weak-retarget'} if '--only-weak-boundary' in identity['command'] else None
        def judge(documents):
            if required:assert documents.get('weak-retarget',{}).get('ownerDeathReacquire') is True,'Missing owner-death evidence'
            return check_documents(documents,plans,required)
        judge(documents)
        variants=[]
        if required:
            bad=copy.deepcopy(documents);bad['weak-retarget']['births'].pop();variants.append(bad)
            bad=copy.deepcopy(documents);bad['weak-retarget']['ownerDeathReacquire']=False;variants.append(bad)
            bad=copy.deepcopy(documents);bad['weak-retarget']['sourceDeadSamples']=0;variants.append(bad)
            bad=copy.deepcopy(documents);bad.pop('weak-retarget');variants.append(bad)
        else:
            bad=copy.deepcopy(documents);bad['distance-octants']['births'].pop();variants.append(bad)
            bad=copy.deepcopy(documents);bad['deploy-native']['early'][0]['hitOver']=False;variants.append(bad)
            bad=copy.deepcopy(documents);bad['pending-target']['births'][0]['intended']=0;variants.append(bad)
            bad=copy.deepcopy(documents);bad.pop('lob-native');variants.append(bad)
        bad=copy.deepcopy(documents);bad['weak-retarget']['after'][0]['nativeTracking']=False;variants.append(bad)
        for bad in variants:
            try:judge(bad)
            except AssertionError:pass
            else:raise AssertionError('Bad boundary evidence was accepted')
        print('NEGATIVE_PASS: five corrupted boundary results rejected; original evidence untouched');return
    with tempfile.TemporaryDirectory(prefix='negative-',dir=ROOT/'.work/attack-lab') as temporary:
        root=Path(temporary).resolve();assert root.is_relative_to(ROOT/'.work')
        shutil.copytree(source.parent/'design',root/'design');shutil.copyfile(source.parent/'design-hashes.json',root/'design-hashes.json')
        runtime=root/'runtime';runtime.mkdir();data=root/'userdata';data.mkdir()
        shutil.copyfile(source/'identity.json',runtime/'identity.json');(runtime/'userdata-path.txt').write_text(str(data),encoding='utf-8')
        for p in userdata.glob('attack-lab-*.json'):shutil.copyfile(p,data/p.name)
        for p in userdata.glob('motion-trace*.json'):shutil.copyfile(p,data/p.name)
        baseline=assess(runtime)
        traced=next((r for r in baseline if r['nativeSkippedMotionSteps']>0),None)
        if traced:
            evidence=data/('attack-lab-'+traced['case']+'.json');saved=evidence.read_bytes();changed=json.loads(saved);changed['terminals']=[]
            evidence.write_text(json.dumps(changed),encoding='utf-8')
            try:assess(runtime)
            except (AssertionError,ValueError):pass
            else:raise AssertionError('Skipped movement without lifecycle evidence was accepted')
            evidence.write_bytes(saved)
        file=next(data.glob('attack-lab-*.json'));original=file.read_bytes();value=json.loads(original)
        value['births'].pop();file.write_text(json.dumps(value),encoding='utf-8')
        try:assess(runtime)
        except (AssertionError,ValueError):pass
        else:raise AssertionError('Missing emission was accepted')
        file.write_bytes(original);file.unlink()
        try:assess(runtime)
        except (AssertionError,ValueError):pass
        else:raise AssertionError('Missing case evidence was accepted')
    print('NEGATIVE_PASS: altered emission count and missing case were rejected; original evidence untouched')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('case',choices=['first','second','nested','homing','fan','build','normal','assess','negative','boundaries','weak-owner']);parser.add_argument('--run');parser.add_argument('--only-case',choices=['straight','fan','ring','parallel','starfruit','homing','lob','nested']);args=parser.parse_args()
    if args.only_case and args.only_case not in {'first':{'straight','fan','ring','parallel'},'second':{'starfruit','homing','lob','nested'}}.get(args.case,set()):parser.error('--only-case must select a case in first/second')
    if args.case=='assess':print(json.dumps(assess(args.run),indent=2));return
    if args.case=='negative':negative_checks(args.run);return
    base=ROOT/'.work/attack-lab';base.mkdir(exist_ok=True);lock=base/'run.lock'
    handle=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        run=base/(args.case+'-'+uuid.uuid4().hex[:8]);run.mkdir()
        package=build(run,args.case in ('first','second','nested','homing','fan','boundaries','weak-owner'),args.case in ('boundaries','weak-owner'))
        print('RUN_DIR:',run,flush=True)
        if args.case=='build':return
        driver=DRIVER
        if args.case=='normal':driver+='''
var capture_started=false
func _physics_process(_delta):
    var profile=get_tree().root.find_child("DialogBoxNewUser",true,false)
    if profile!=null and profile.get("nameLineEdit")!=null:
        profile.get("nameLineEdit").text="AttackLabNormal"
        profile.get("readyButtonNewUser").emit_signal("pressed")
    if get_tree().current_scene!=null and get_tree().current_scene.name=="MainMenu" and profile==null and not capture_started:
        capture_started=true
        capture.call_deferred()
func capture():
    await get_tree().create_timer(2.0).timeout
    await RenderingServer.frame_post_draw
    get_viewport().get_texture().get_image().save_png("user://attack-lab-normal.png")
    print("ATTACK_LAB_NORMAL_PASS: production DLL, no test user arguments")
    get_tree().quit()
'''
        flags=() if args.case=='normal' else ('--attack-lab-audit',)+ (('--boundaries','--only-weak-boundary') if args.case=='weak-owner' else ('--boundaries',) if args.case=='boundaries' else ('--only-fan',) if args.case=='fan' else ('--only-homing',) if args.case=='homing' else ('--only-nested',) if args.case=='nested' else ('--second-half',) if args.case=='second' else ())
        if args.only_case:flags+=('--only-case='+args.only_case,)
        required=['ATTACK_LAB_READY:', 'ATTACK_LAB_NORMAL_PASS:' if args.case=='normal' else 'ATTACK_LAB_BOUNDARIES_CAPTURED:' if args.case in ('boundaries','weak-owner') else 'ATTACK_LAB_SUITE_PASS:']
        runtime=test(package_path=package,driver_code=driver,runtime_dir=run/'runtime',user_args=flags,required_markers=required)
        if args.case!='normal':print(json.dumps(assess(runtime),indent=2))
    finally:os.close(handle);lock.unlink(missing_ok=True)

if __name__=='__main__':main()
