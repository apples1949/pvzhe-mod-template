"""Offline, independently falsifiable boundary assertions. Does not launch the game."""
import math

CASES={'distance-octants':8,'deploy-native':3,'native-retarget':1,'weak-retarget':1,'lob-native':2,'pending-target':9}


def check_documents(documents,plans,required=None):
    selected=CASES if required is None else {key:CASES[key] for key in required}
    assert selected and set(documents)==set(selected),'Missing or unexpected boundary evidence'
    summary=[]
    for case,count in selected.items():
        d=documents[case];assert d['case']==case,'Case identity mismatch'
        births=d['births'];assert len(births)==count,(case,'birth count',len(births),count)
        items={i['id']:i for g in plans[case]['groups'] for i in g['items']}
        for b in births:
            assert b['item'] in items,'Unknown emitted item'
            assert -.001<=b['actual']-b['intended']<.07,(case,'cadence')
        if case in ('distance-octants','deploy-native'):
            limit=.5 if case=='distance-octants' else .25
            assert d['hits']==0 and not d['remaining'],'Distance cleanup did not finish'
            assert len(d['ranges'])==count and len(d['terminals'])==count,'Missing native distance terminals'
            for r in d['ranges']:
                assert abs(r['limit']-limit)<1e-6 and limit<r['distance']<=limit+r['step']+.001,'Wrong fractional distance'
            for t in d['terminals']:
                assert t['fireLength']==0 and abs(t['checkDistance']-d['gridWidth']*limit)<.01,'Fractional sentinel/distance mapping'
                b=next(b for b in births if b['generation']==t['generation'])
                expected=[b['root'][i]+items[b['item']]['launch']['offset'][i] for i in (0,1)]
                assert math.dist(t['distanceOrigin'],expected)<.1,'Wrong distance reference point'
            if case=='distance-octants':
                headings=sorted(round(math.degrees(math.atan2(b['velocity'][1],b['velocity'][0])))%360 for b in births)
                assert headings==list(range(0,360,45)),'Missing octant'
            else:
                assert len(d['early'])==3 and all(s['deployed'] and s['hitOver'] and s['fireLength']==-1 and s['nativeTracking'] for s in d['early']),'Deployment did not suppress native hit/distance'
        elif case=='native-retarget':
            assert d['before'] and d['after'] and d['turned'],'Missing tracking phases'
            assert all(s['nativeTracking'] and s['targetId']==d['backupId'] for s in d['after']),'Native target not reacquired'
            assert any(s['velocity'][0]<0 for s in d['turned']),'Native tracking did not turn around'
            assert not d['remaining'] and len(d['terminals'])==1,'Native no-target cleanup missing'
        elif case=='weak-retarget':
            assert d['before'] and d['after'] and d['invalidOnly'] and d['replacement'],'Missing weak phases'
            assert all(not s['nativeTracking'] and s['age']<.5 and math.dist(s['velocity'],births[0]['velocity'])<.1 for s in d['before']),'Delay changed initial flight'
            assert all(s['nativeTracking'] and s['age']>=.5 and s['targetId']==d['backupId'] for s in d['after']),'Delayed host target not acquired'
            assert any(s['velocity'][1]<-1 for s in d['after']),'Delayed tracking did not turn'
            assert all(abs(math.hypot(*s['velocity'])-300)<.1 for s in d['after']),'Delayed speed changed'
            assert any(s['age']<.5 and not s['nativeTracking'] for s in d['samples']),'Missing delayed pre-activation sample'
            assert any(s['age']>=.5 and s['nativeTracking'] for s in d['samples']),'Missing delayed host activation sample'
            assert all(s['targetId']==0 for s in d['invalidOnly']),'Weak retained disabled/near-death target'
            assert all(s['targetId']==d['thirdId'] for s in d['replacement']),'Weak failed to find new target'
            if d.get('ownerDeathReacquire'):
                assert d['sourceDeadSamples']>0,'Missing airborne processing after owner death'
        elif case=='lob-native':
            assert len(d['before'])==1 and len(d['after'])==2,'Missing lob phases'
            original=d['before'][0];later=next(s for s in d['after'] if s['generation']==original['generation'])
            assert math.dist(original['catapultTarget'],later['catapultTarget'])<.01,'Lob endpoint followed moving target'
            assert math.dist(original['velocity'],later['velocity'])<.1,'Lob ground velocity followed target'
            assert abs(births[0]['flightTime']-births[1]['flightTime'])<.001,'Group multiplier changed lob flight time'
            assert math.dist(d['after'][0]['catapultTarget'],d['after'][1]['catapultTarget'])>50,'Second lob did not use a fresh snapshot'
            for b in births:
                expected=math.sqrt(.3)+math.sqrt(2*(300+b['z'])/2000)
                assert abs(b['flightTime']-expected)<.001,'Non-native catapult time'
        else:
            assert d['pauseFrozen'] is True and .65<=d['targetArrival']<.79,'Wrong no-target/pause preconditions'
            for b in births:
                round_start=b['intended']-items[b['item']]['time']
                assert round_start>=.8-1e-6,'A volley started without an eligible target'
                assert any(abs(round_start-t)<1e-6 for t in (.8,1,1.2)),'Unexpected round'
        summary.append(dict(case=case,births=count,passed=True))
    return summary
