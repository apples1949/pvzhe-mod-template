import {Preview} from './model.mjs';
export const compositionFormat='pvzhe.attack-composition';
export function wrap(recipe){
  if(recipe.format===compositionFormat){const doc=structuredClone(recipe);doc.schemaVersion=2;return doc;}
  const child=structuredClone(recipe);child.id=crypto.randomUUID();
  return {format:compositionFormat,schemaVersion:2,id:recipe.id,character:recipe.character,root:{kind:'group',id:crypto.randomUUID(),name:'攻击组',enabled:true,speedMultiplier:1,rateMultiplier:1,rangeMultiplier:1,children:[{kind:'attack',id:crypto.randomUUID(),name:'攻击 1',enabled:true,recipe:child}]}};
}
export function flatten(doc){
  const out=[];
  function walk(node,factors=[1,1,1],enabled=true,path=[],delay=0){
    if(path.length>5)throw Error('攻击组最多嵌套5层');
    enabled&&=node.enabled;path=[...path,node.id];const localDelay=node.startDelaySeconds??0;if(!Number.isFinite(localDelay)||localDelay<0||localDelay>5)throw Error('发射延迟应为0～5秒');delay+=localDelay;
    if(node.kind==='group')for(const child of node.children)walk(child,factors.map((x,i)=>x*node[['speedMultiplier','rateMultiplier','rangeMultiplier'][i]]),enabled,path,delay);
    else {
      const r={...node.recipe,speed:node.recipe.pattern==='lob'?300:node.recipe.speed*factors[0],intervalSeconds:node.recipe.intervalSeconds/factors[1],rangeCells:node.recipe.rangeCells*factors[2]};
      if(r.speed<1||r.speed>5000||r.intervalSeconds<.01||r.intervalSeconds>60000||r.rangeCells>1000)throw Error('叠加后的射速、攻击间隔或射程超出支持范围');
      out.push({node,recipe:r,enabled,path,startDelaySeconds:delay});
    }
  }
  walk(doc.root);return out;
}
export class CompositionPreview {
  constructor(entries,state,target){
    this.time=0;this.evicted=0;this.serial=0;this.bullets=[];
    this.parts=entries.filter(e=>e.enabled).map(({recipe:r,node,startDelaySeconds=0})=>{
      const offset=r.pattern==='lob'?state.originPresets.presets.lobber.origin:r.origin;
      const recipe={...r,radius:r.pattern==='lob'?0:r.radius,originShotOffsets:r.originPreset==='center'&&r.pattern==='starfruit'?state.originPresets.presets.center.shotOffsets:undefined};
      const preview=new Preview(recipe,state.plant.position.map((v,i)=>v+offset[i]),target,...state.canvas,state.grid.size,state.plant.position,state.target.hitBoxRect.map(v=>v*(state.target.scale||1)));preview.layerId=node.id;preview.next=startDelaySeconds;return preview;
    });
  }
  step(dt,target){
    this.time+=Math.min(.05,Math.max(0,dt));
    for(const p of this.parts){p.step(dt,target);this.evicted+=p.evicted-(p.compositeEvicted??0);p.compositeEvicted=p.evicted;for(const b of p.bullets)if(b.compositeSerial===undefined){b.compositeSerial=this.serial++;b.ammo=p.recipe.ammo;b.pattern=p.recipe.pattern;b.layerId=p.layerId;}}
    this.bullets=this.parts.flatMap(p=>p.bullets).sort((a,b)=>a.born-b.born||a.compositeSerial-b.compositeSerial);
    while(this.bullets.length>1000){const removed=new Set(this.bullets.splice(0,50));for(const p of this.parts)p.bullets=p.bullets.filter(b=>!removed.has(b));this.evicted+=50;}
  }
}

// Local values: groups store multipliers; attacks use pea-speed and 1.5s frequency references.
export function selectionValue(nodes,key){
  const values=nodes.map(n=>key==='startDelaySeconds'?(n[key]??0):n.kind==='group'?n[key]:key==='speedMultiplier'?n.recipe.speed/300:1.5/n.recipe.intervalSeconds);
  return values.length&&values.every(v=>Math.abs(v-values[0])<1e-9)?values[0]:null;
}
export function applySelectionValue(nodes,key,value){
  value=roundParameter(value);
  if(key==='startDelaySeconds'){if(!Number.isFinite(value)||value<0||value>5)throw Error('发射延迟应为0～5秒');for(const node of nodes)node[key]=value;return;}
  if(!['speedMultiplier','rateMultiplier'].includes(key)||!Number.isFinite(value)||value<=0)throw Error('请输入有效倍率');
  if(nodes.some(n=>n.kind==='group'&&(value<.1||value>10)))throw Error('攻击组倍率应在0.1～10之间');
  for(const node of nodes){if(node.kind==='group')node[key]=value;else if(key==='speedMultiplier')node.recipe.speed=value*300;else node.recipe.intervalSeconds=1.5/value;}
}

export function chooseLayers(selected,id,visible,anchor,{ctrlKey=false,metaKey=false,shiftKey=false}={}){
  const additive=ctrlKey||metaKey,next=new Set(additive?selected:[]);
  if(shiftKey&&visible.includes(anchor)&&visible.includes(id)){
    const a=visible.indexOf(anchor),b=visible.indexOf(id);
    for(const key of visible.slice(Math.min(a,b),Math.max(a,b)+1))next.add(key);
    return {selected:next,anchor};
  }
  if(additive&&next.has(id))next.delete(id);else next.add(id);
  return {selected:next,anchor:id};
}
export function moveLayers(document,ids,targetId,placement){
  const candidate=structuredClone(document),index=new Map();
  function visit(node,parent=null,path=[]){index.set(node.id,{node,parent,path});if(node.kind==='group')for(const child of node.children)visit(child,node,[...path,node.id]);}
  visit(candidate.root);
  if(!['before','after','inside'].includes(placement))throw Error('未知放置方式');
  const target=index.get(targetId),chosen=new Set(ids);
  if(!target)throw Error('目标图层不存在');
  if(chosen.has(candidate.root.id))throw Error('根攻击组不能移动');
  const sources=[...index.values()].filter(e=>chosen.has(e.node.id)&&!e.path.some(id=>chosen.has(id)));
  if(!sources.length)throw Error('请选择要移动的图层');
  if(sources.some(e=>e.node.id===targetId||target.path.includes(e.node.id)))throw Error('不能放入自身或自己的子组');
  const destination=placement==='inside'?target.node:target.parent;
  if(!destination||destination.kind!=='group')throw Error('只能放入攻击组，根组外不能插入');
  for(const source of sources)source.parent.children=source.parent.children.filter(n=>n!==source.node);
  const at=placement==='inside'?destination.children.length:destination.children.indexOf(target.node)+(placement==='after'?1:0);
  destination.children.splice(at,0,...sources.map(e=>e.node));
  checkLayerTree(candidate);return candidate;
}

export function modifiedLayer(node){
  return (node.startDelaySeconds??0)!==0||['speedMultiplier','rateMultiplier'].some(key=>Math.abs(selectionValue([node],key)-1)>1e-9);
}
export function groupDepth(document,id){
  function find(node,depth){if(node.id===id)return depth;if(node.kind==='group')for(const child of node.children){const result=find(child,depth+1);if(result!==null)return result;}return null;}
  return find(document.root,0);
}

// UI precision only; do not quantize simulation clocks or imported geometry.
export function roundParameter(value){
  if(!Number.isFinite(value))return value;
  const magnitude=Math.abs(value);
  return Math.sign(value)*Math.round((magnitude+Number.EPSILON*Math.max(1,magnitude))*100)/100||0;
}

export function checkLayerTree(doc){
  let total=0,attacks=0;const ids=new Set(),recipeIds=new Set();
  function visit(node,depth=0){
    if(depth>5)throw Error('攻击组最多嵌套5层');
    if(++total>160)throw Error('图层总数最多160项');
    if(!node||!['group','attack'].includes(node.kind)||typeof node.id!=='string'||!node.id||ids.has(node.id)||typeof node.name!=='string'||!node.name.trim()||node.name.length>64||typeof node.enabled!=='boolean')throw Error('图层数据无效');
    ids.add(node.id);const delay=node.startDelaySeconds??0;if(!Number.isFinite(delay)||delay<0||delay>5)throw Error('发射延迟应为0～5秒');
    if(node.kind==='group'){
      if(!Array.isArray(node.children)||['speedMultiplier','rateMultiplier','rangeMultiplier'].some(k=>!Number.isFinite(node[k])||node[k]<.1||node[k]>10))throw Error('攻击组数据无效');
      for(const child of node.children)visit(child,depth+1);
    }else{
      const r=node.recipe;if(++attacks>32)throw Error('最多32个攻击图层');
      if(!r||r.format!=='pvzhe.attack-recipe'||r.schemaVersion!==19||r.character!==doc.character||typeof r.id!=='string'||recipeIds.has(r.id)||!['straight','fan','ring','starfruit','lob','parallel'].includes(r.pattern)||!['normal','homing'].includes(r.ammo)||!Array.isArray(r.origin)||r.origin.length!==2||!r.origin.every(Number.isFinite))throw Error('攻击方案数据无效');
      recipeIds.add(r.id);
      if(![0,1,2].includes(r.trackingStrength))throw Error('未知追踪方式');
      const limits={speed:[30,3000],intervalSeconds:[.1,60],rangeCells:[0,1000],radius:[0,400],count:[1,120],spread:[0,360],direction:[0,360],spacing:[0,400],angleOffset:[0,360],trackingStrength:[0,2],shotDelaySeconds:[0,5],deploymentSeconds:[0,1]};
      for(const [key,[low,high]] of Object.entries(limits))if(!Number.isFinite(r[key])||r[key]<low||r[key]>high)throw Error('攻击参数无效');
      if(!Number.isInteger(r.count)||!['pea-front','pea-back','center','lobber','puff','custom'].includes(r.originPreset))throw Error('弹数或起点预设无效');
    }
  }
  visit(doc.root);flatten(doc);return doc;
}
export function copyLayers(doc,selected){
  const chosen=new Set(selected),nodes=[];
  function walk(node,covered=false){
    if(chosen.has(node.id)&&!covered){nodes.push(structuredClone(node));return;}
    if(node.kind==='group')for(const child of node.children)walk(child,covered||chosen.has(node.id));
  }
  walk(doc.root);
  return {format:'pvzhe.attack-layers',schemaVersion:1,character:doc.character,nodes};
}
export function pasteLayers(doc,clipboard,destinationId){
  if(clipboard?.format!=='pvzhe.attack-layers'||clipboard.schemaVersion!==1||clipboard.character!==doc.character||!Array.isArray(clipboard.nodes)||!clipboard.nodes.length)throw Error('剪贴板不是当前角色的攻击图层');
  const next=structuredClone(doc);let destination;
  function find(node){if(node.id===destinationId)destination=node;if(node.kind==='group')node.children.forEach(find);}find(next.root);
  if(destination?.kind!=='group')throw Error('请在组视图粘贴图层');
  const names=new Set(destination.children.map(n=>n.name));
  function clone(node){const n=structuredClone(node);n.id=crypto.randomUUID();if(n.kind==='group')n.children=n.children.map(clone);else{n.recipe.id=crypto.randomUUID();}return n;}
  const pasted=clipboard.nodes.map(clone);
  for(const node of pasted){const base=node.name.slice(0,52);let name=base+' 副本',suffix=2;while(names.has(name))name=base+' 副本 '+suffix++;node.name=name;names.add(name);}
  destination.children.push(...pasted);checkLayerTree(next);
  return {document:next,ids:pasted.map(n=>n.id)};
}

export function editLayerProperties(doc,selected,key,value){
  const candidate=structuredClone(doc),ids=new Set(selected),nodes=[];
  function walk(node){if(ids.has(node.id))nodes.push(node);if(node.kind==='group')node.children.forEach(walk);}
  walk(candidate.root);if(!nodes.length)throw Error('请先选择图层');
  applySelectionValue(nodes,key,value);checkLayerTree(candidate);return candidate;
}
