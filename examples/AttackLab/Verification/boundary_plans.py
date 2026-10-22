"""Explicit test-only recipes; not player confirmations or production content."""
from attack_web import default_recipe, compile_recipe


def attack(identity, **values):
    r=default_recipe();r.update(id=identity,intervalSeconds=60,originPreset='custom',origin=[0,0],radius=0);r.update(values)
    return dict(kind='attack',id=identity+'-layer',name=identity,enabled=True,recipe=r)


def group(identity,children,**values):
    return dict(kind='group',id=identity,name=identity,enabled=True,speedMultiplier=values.get('speed',1),rateMultiplier=1,
                rangeMultiplier=1,startDelaySeconds=values.get('delay',0),children=children)


def boundary_designs():
    recipes={
        'distance-octants':attack('octants',pattern='ring',count=8,rangeCells=.5),
        'deploy-native':attack('deploy',pattern='parallel',count=3,spacing=90,direction=90,radius=30,rangeCells=.25,ammo='homing'),
        'native-retarget':attack('native',ammo='homing',direction=180),
        'weak-retarget':attack('weak',ammo='homing',trackingStrength=1),
        'pending-target':attack('pending',pattern='fan',count=3,spread=20,shotDelaySeconds=.25),
    }
    recipes['pending-target']['recipe']['intervalSeconds']=.2
    recipes['lob-native']=group('lob-root',[
        attack('lob-base',pattern='lob'),
        group('outer',[group('middle',[group('inner',[attack('lob-extreme',pattern='lob',speed=3000)],speed=10)],speed=10)],speed=10,delay=.25)
    ])
    return {key:dict(format='pvzhe.attack-composition',schemaVersion=2,id='boundary-'+key,character='PlantPeaShooterSingle',
                     root=node if node['kind']=='group' else group(key+'-root',[node])) for key,node in recipes.items()}


def compiled_boundaries():
    return {key:compile_recipe(doc) for key,doc in boundary_designs().items()}
