"""Isolated release-only drag verification, with another live Mod using the same convention."""
import json
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[2]
EXAMPLE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from runtime_test import test
from runtime_diagnostics import assess
from ui_layout_feedback import latest
import mod

DRIVER='''extends Node
var started=false
func _process(_delta):
    if started: return
    var b=get_tree().root.find_child("StartButton",true,false)
    if b is BaseButton and b.is_visible_in_tree() and not b.disabled:
        started=true
        b.emit_signal("pressed")
'''

NORMAL_DRIVER=DRIVER+'''
var accepted=false
var moved=false
var frames=0
var diagnosed=false
func _ready():
    process_mode=Node.PROCESS_MODE_ALWAYS
    get_tree().root.gui_embed_subwindows=true
func _physics_process(_delta):
    var root=get_tree().root
    var profile=root.find_child("DialogBoxNewUser",true,false)
    if not accepted and profile != null and profile.get("nameLineEdit") != null:
        profile.get("nameLineEdit").text="DragNormal"
        profile.get("readyButtonNewUser").emit_signal("pressed")
        accepted=true
    var b=root.find_child("DragDemoHello",true,false)
    if not accepted or b == null or profile != null or not b.is_visible_in_tree(): return
    if moved:
        frames+=1
        if frames<3:return
        if abs(b.offset_right+64)>0.1:
            print("AUDIT_TEST_ERROR: production drag offset ",b.offset_right)
            get_tree().quit(2)
            return
        print("DRAG_PRODUCTION_PASS: ordinary package, no Mod test args; middle drag retained")
        get_tree().quit()
        return
    var point=b.get_global_transform_with_canvas()*(b.size/2)
    root.gui_embed_subwindows=true
    var motion=InputEventMouseMotion.new()
    motion.position=point
    motion.global_position=point
    root.push_input(motion,true)
    var hovered=root.gui_get_hovered_control()
    if not diagnosed:
        print("DRAG_NORMAL_DIAGNOSTIC: point=",point," hovered=",hovered," accepted=",accepted)
        diagnosed=true
    if hovered!=b and (hovered==null or not b.is_ancestor_of(hovered)):return
    var down=InputEventMouseButton.new()
    down.button_index=MOUSE_BUTTON_MIDDLE
    down.pressed=true
    down.position=point
    down.global_position=point
    root.push_input(down,true)
    point+=Vector2(-40,20)
    motion=InputEventMouseMotion.new()
    motion.position=point
    motion.global_position=point
    motion.button_mask=MOUSE_BUTTON_MASK_MIDDLE
    root.push_input(motion,true)
    var up=InputEventMouseButton.new()
    up.button_index=MOUSE_BUTTON_MIDDLE
    up.pressed=false
    up.position=point
    up.global_position=point
    root.push_input(up,true)
    moved=true
'''


def run(normal=False):
    base=ROOT/'.work/drag-layout-verification';base.mkdir(parents=True,exist_ok=True)
    lock=base/'test.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        run_dir=base/uuid.uuid4().hex[:8];build=run_dir/'build';build.mkdir(parents=True)
        if normal:
            subprocess.run([sys.executable,str(ROOT/'tools/mod.py'),'build','--example','drag-layout'],check=True)
            mod.select_example('drag-layout')
            runtime=test('drag-layout',package_path=mod.PACKAGE,driver_code=NORMAL_DRIVER,runtime_dir=run_dir/'runtime',required_markers=['DRAG_PRODUCTION_PASS:'])
            print('Production drag evidence:',runtime)
            return
        sources=[EXAMPLE/'Entry.cs',EXAMPLE/'Verification/Smoke.cs',ROOT/'components/RuntimeUi/DragLayout.cs']
        for p in sources:shutil.copyfile(p,build/p.name)
        refs=ROOT/'.work/references'
        (build/'Audit.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net9.0</TargetFramework><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings></PropertyGroup><ItemGroup>'+''.join(
            f'<Reference Include="{n}"><HintPath>{escape(str(refs/(n+".dll")))}</HintPath><Private>false</Private></Reference>' for n in ['PlantsVsZombies','GodotSharp'])+'</ItemGroup></Project>',encoding='utf-8')
        subprocess.run(['dotnet','build',str(build/'Audit.csproj'),'-c','Release','--nologo'],check=True)
        packages=[]
        for mod_id in ['drag-layout-demo','drag-layout-other']:
            manifest=json.loads((EXAMPLE/'mod/mod.json').read_text(encoding='utf-8'));manifest['id']=mod_id
            defaults=json.loads((EXAMPLE/'mod/Assets/ui-layout.json').read_text(encoding='utf-8'));defaults['modId']=mod_id
            if mod_id.endswith('other'):
                for p in defaults['placements'].values():p['rightInset']=400;p['verticalInset']=50
            package=build/(mod_id+'.pmod');packages.append(package)
            with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('mod.json',json.dumps(manifest,ensure_ascii=False));z.writestr('Assets/ui-layout.json',json.dumps(defaults))
                z.write(build/'bin/Release/net9.0/Audit.dll','Runtime/ModAssembly.dll')
        runtime=test('drag-layout',package_path=packages[0],additional_packages=packages[1:],driver_code=DRIVER,
                     runtime_dir=run_dir/'runtime',user_args=['--drag-audit'],required_markers=['DRAG_AUDIT_PASS:'])
        text=(runtime/'game.log').read_text(encoding='utf-8')
        ready=[]
        for line in text.splitlines():
            if line.startswith('[Mod:drag-layout-demo] UI_LAYOUT_READY: '):ready.append(json.loads(line.split('UI_LAYOUT_READY: ',1)[1]))
        identity=ready[-1]
        event=latest(text,mod_id='drag-layout-demo',session_id=identity['sessionId'],binary_sha256=identity['binarySha256'],
                     scene_id='main-menu',layout_id='default',component_id='hello')
        assert event and event['persisted'] and abs(event['rightInset']-177.75)<.1
        assert '[Mod:drag-layout-other] UI_LAYOUT_READY:' in text
        assert '[Mod:drag-layout-other] UI_LAYOUT_CHANGED:' in text
        assert len([s for s in text.splitlines() if s.startswith('[Mod:drag-layout-demo] UI_LAYOUT_CHANGED:')])==5
        info=json.loads((runtime/'identity.json').read_text(encoding='utf-8'))
        userdata=Path(info['userdata']);state=userdata/'Mods/enabled_mods.json'
        state.write_text(json.dumps(dict(schemaVersion=2,enabledIds=['drag-layout-demo','drag-layout-other'],preferredOrder=['drag-layout-demo','drag-layout-other'])),encoding='utf-8')
        command=info['command'].copy();command[command.index('--log-file')+1]=str(runtime/'restart.log');command+=['--drag-restart']
        try:
            with (runtime/'restart-stdout.log').open('w',encoding='utf-8') as output:subprocess.run(command,cwd=runtime,stdout=output,stderr=subprocess.STDOUT,timeout=120,check=True)
        finally:state.unlink(missing_ok=True)
        report=assess((runtime/'restart.log').read_text(encoding='utf-8'),['DRAG_RESTART_PASS:'])
        assert report['passed'],report
        report.update(filteredEvent=event,liveMods=2)
        mod.write_json(runtime/'drag-assessment.json',report)
        print('Drag evidence:',runtime)
    finally:
        os.close(fd);lock.unlink(missing_ok=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--normal',action='store_true')
    run(parser.parse_args().normal)
