import {wrap,flatten,CompositionPreview,selectionValue,applySelectionValue,chooseLayers,moveLayers,modifiedLayer,groupDepth,roundParameter,copyLayers,pasteLayers,editLayerProperties} from './composition.mjs';
import {angles,shotTimes,launches,Preview} from './model.mjs';
const $=id=>document.getElementById(id), status=$('status');
let state,recipe,rootDoc,currentNode,lastAttack,sim,images={},paused=false,moving=false,drag=null,dirty=false,locked=false,timelineDuration=5,timelineWindow=-1;
const canvas=$('preview'),ctx=canvas.getContext('2d');
const labels={straight:'直线',fan:'扇形',ring:'环形',lob:'投掷',parallel:'排射',starfruit:'杨桃'};
const targetBase=[];
const collapsedLayers=new Set();let renameId=null,menuId=null,selectedLayers=new Set(),selectionAnchor=null,draggedLayers=null;
function origin(){const offset=recipe.pattern==='lob'?state.originPresets.presets.lobber.origin:recipe.origin;return state.plant.position.map((v,i)=>v+offset[i]);}
function effectiveRecipe(){return {...recipe,radius:recipe.pattern==='lob'?0:recipe.radius,originShotOffsets:recipe.originPreset==='center'&&recipe.pattern==='starfruit'?state.originPresets.presets.center.shotOffsets:undefined};}
function previewEntries(){return flatten(rootDoc).filter(e=>e.path.includes(currentNode.id));}
function reset(){sim=new CompositionPreview(previewEntries(),state,[...targetBase]);sim.step(0,[...targetBase]);}
function announce(text,error=false){status.textContent=text;status.classList.toggle('error',error);}
function sync(){
  for(const b of document.querySelectorAll('[data-pattern]')){const active=b.dataset.pattern===recipe.pattern;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',active);}
  for(const b of document.querySelectorAll('[data-ammo]')){const active=b.dataset.ammo===recipe.ammo;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',active);}
  $('countField').hidden=['straight','lob','starfruit'].includes(recipe.pattern);$('spacingField').hidden=recipe.pattern!=='parallel';$('spreadField').hidden=recipe.pattern!=='fan';
  $('originPreset').value=recipe.originPreset;
  for(const option of $('originPreset').options)option.disabled=!!state.originPresets.presets[option.value]?.patternOnly&&state.originPresets.presets[option.value].patternOnly!==recipe.pattern;
  $('originHint').hidden=recipe.originPreset!=='custom';
  const lob=recipe.pattern==='lob';
  for(const id of ['originSection','ammoSection','directionField','directionHint','rangeField'])$(id).hidden=lob;
  $('angleOffsetField').hidden=lob;
  $('delayField').hidden=lob||recipe.pattern==='straight';
  $('delayNumber').max=5;$('delay').max=5;
  $('trackingField').hidden=lob||recipe.ammo!=='homing';
  $('trackingHint').textContent=recipe.trackingStrength===0?'仅发射时瞄准':recipe.trackingStrength===2?'强追踪 · 持续飞向目标':recipe.trackingStrength===1?'弱追踪 · 有限偏转':recipe.trackingStrength<1?'轻微追踪 · 低偏转力':'增强追踪 · 更快转向';
  $('lobHint').hidden=!lob;document.body.classList.toggle('is-lob',lob);
  for(const [id,value] of [['count',recipe.count],['spread',recipe.spread],['interval',recipe.intervalSeconds],['speed',recipe.speed/300],['radius',recipe.radius],['range',recipe.rangeCells],['direction',recipe.direction],['spacing',recipe.spacing],['angleOffset',recipe.angleOffset],['tracking',recipe.trackingStrength],['delay',recipe.shotDelaySeconds]]){
    $(id).value=roundParameter(value);if(document.activeElement!==$(id+'Number'))$(id+'Number').value=roundParameter(value);
  }
  const intervals=previewEntries().filter(e=>e.enabled).map(e=>e.recipe.intervalSeconds);const interval=intervals.length?Math.min(...intervals):1;timelineDuration=Math.ceil(5/interval)*interval;
  $('timeline').max=timelineDuration;
  timelineWindow=-1;renderTimeline(0);
  const n=angles(recipe).length;
  $('summary').textContent=`${labels[recipe.pattern]} · ${n} 颗${shotTimes(recipe).some(t=>t>0)?'依次发射':'齐射'} · ${recipe.pattern==='lob'?'发射时瞄准':recipe.ammo==='normal'?'普通弹药':'追踪弹药'}`;
  renderComposition();
  const entries=previewEntries().filter(e=>e.enabled);
  $('summary').textContent=currentNode.kind==='group'?`${currentNode.name} · ${entries.length} 个攻击图层`:`${currentNode.name} · ${labels[recipe.pattern]} · 射速 ${Number((entries[0]?.recipe.speed/300||0).toFixed(2))} 倍 · 间隔 ${Number((entries[0]?.recipe.intervalSeconds||0).toFixed(3))} 秒`;

}
function renderTimeline(time){
  const window=Math.floor(time/timelineDuration);if(window===timelineWindow)return;timelineWindow=window;
  const begin=window*timelineDuration,end=begin+timelineDuration,bins=new Map();
  for(const entry of previewEntries().filter(e=>e.enabled)){
    const r=entry.recipe,offsets=shotTimes(r).map(t=>t+(entry.startDelaySeconds??0)),first=Math.max(0,Math.ceil((begin-offsets.at(-1))/r.intervalSeconds));
    for(let k=first;k*r.intervalSeconds<end-1e-9;k++)for(const offset of offsets){
      const at=k*r.intervalSeconds+offset;if(at<begin-1e-9||at>=end-1e-9)continue;
      const bucket=Math.min(299,Math.floor((at-begin)/timelineDuration*300));
      if(!bins.has(bucket))bins.set(bucket,{at,count:0});bins.get(bucket).count++;
    }
  }
  $('timelineTicks').replaceChildren();for(const {at,count} of bins.values()){const tick=document.createElement('span');tick.style.left=((at-begin)/timelineDuration*100)+'%';tick.title=at.toFixed(2)+' 秒 · '+count+' 颗';$('timelineTicks').appendChild(tick);}
}
function change(){dirty=true;try{sync();reset();announce('有未保存的调整');}catch(e){announce(e.message,true);}}
for(const b of document.querySelectorAll('[data-pattern]')) b.onclick=()=>{recipe.pattern=b.dataset.pattern;if(recipe.pattern==='ring'&&recipe.count===5)recipe.count=12;change();};
for(const b of document.querySelectorAll('[data-ammo]'))b.onclick=()=>{recipe.ammo=b.dataset.ammo;change();};
for(const [id,key,factor] of [['count','count',1],['spread','spread',1],['interval','intervalSeconds',1],['speed','speed',300],['radius','radius',1],['range','rangeCells',1],['direction','direction',1],['spacing','spacing',1],['angleOffset','angleOffset',1],['tracking','trackingStrength',1],['delay','shotDelaySeconds',1]]){
  const update=e=>{const input=e.target;if(!input.checkValidity()||input.value===''){announce('请输入范围内的有效数值',true);return;}
    recipe[key]=roundParameter(roundParameter(Number(input.value))*factor);change();};
  $(id).oninput=update;$(id+'Number').oninput=update;
  $(id+'Number').onblur=()=>{$(id+'Number').value=roundParameter(recipe[key]/factor);};
}
function syncPlayback(){const label=paused?'继续':'暂停';$('pause').setAttribute('aria-label',label);$('pause').title=label;$('pause').setAttribute('aria-pressed',paused);$('pause').innerHTML=paused?'<svg viewBox="0 0 24 24"><path d="M8 5l11 7-11 7z"/></svg>':'<svg viewBox="0 0 24 24"><path d="M8 5v14M16 5v14"/></svg>'; }
$('pause').onclick=()=>{paused=!paused;syncPlayback();};
$('targetMove').onclick=()=>{moving=!moving;$('targetMove').setAttribute('aria-pressed',moving);};
$('replay').onclick=()=>reset();
$('timeline').oninput=()=>{const goal=Number($('timeline').value);paused=true;syncPlayback();reset();while(sim.time<goal-1e-9)sim.step(Math.min(.05,goal-sim.time),[...targetBase]);};
$('originPreset').onchange=()=>{const id=$('originPreset').value,p=state.originPresets.presets[id];if(id==='custom'){recipe.originPreset=id;change();return;}if(!p)return;recipe.origin=[...p.origin];recipe.originPreset=id;change();};
$('originPreset').onwheel=e=>e.preventDefault();
function point(event){const r=canvas.getBoundingClientRect();return [(event.clientX-r.left)*canvas.width/r.width,(event.clientY-r.top)*canvas.height/r.height];}
canvas.onpointerdown=e=>{
  if(locked)return;const p=point(e),o=origin();
  if(currentNode.kind==='attack'&&recipe.pattern!=='lob'&&recipe.originPreset==='custom'&&Math.hypot(p[0]-o[0],p[1]-o[1])<20)drag='origin';
  else if(Math.hypot(p[0]-targetBase[0],p[1]-(targetBase[1]-30))<65)drag='target';
  if(drag){canvas.setPointerCapture(e.pointerId);canvas.onpointermove(e);}
};
canvas.onpointermove=e=>{
  if(!drag)return;const p=point(e);p[0]=Math.max(0,Math.min(canvas.width,p[0]));p[1]=Math.max(0,Math.min(canvas.height,p[1]));
  if(drag==='origin'){recipe.origin=p.map((v,i)=>v-state.plant.position[i]);recipe.originPreset='custom';dirty=true;sync();announce('起点已调整');}else targetBase.splice(0,2,...p);reset();
};
canvas.onpointerup=canvas.onpointercancel=()=>{drag=null;};
function actor(key,position){
  const a=state[key],im=images[key];
  if(im){const scale=a.scale||1;ctx.drawImage(im,position[0]-a.imageOrigin[0]*scale,position[1]-a.imageOrigin[1]*scale,im.width*scale,im.height*scale);return;}
  ctx.save();ctx.translate(...position);ctx.fillStyle=key==='plant'?'#5d9348':'#89937f';
  ctx.beginPath();ctx.ellipse(0,-30,25,38,0,0,Math.PI*2);ctx.fill();ctx.fillStyle='#e6ecc7';ctx.fillRect(9,-49,16,13);ctx.restore();
}
function draw(){
  const [w,h]=state.canvas;ctx.clearRect(0,0,w,h);
  if(images.background){const [x,y,right,bottom]=state.backgroundCrop;ctx.drawImage(images.background,x,y,right-x,bottom-y,0,0,w,h);}
  else{ctx.fillStyle='#d8c593';ctx.fillRect(0,0,w,h);const g=state.grid;for(let row=0;row<5;row++)for(let col=0;col<9;col++){ctx.fillStyle=(row+col)%2?'#9cbb72':'#a7c67c';ctx.fillRect(g.begin[0]+col*g.size[0],g.begin[1]+row*g.size[1],g.size[0],g.size[1]);}}
  const target=[targetBase[0],targetBase[1]+(moving?Math.sin(sim.time*.9)*85:0)];
  actor('plant',state.plant.position);actor('target',target);
  const o=origin();ctx.save();ctx.strokeStyle='#ffdb8b99';ctx.lineWidth=1.5;ctx.setLineDash([4,7]);
  for(const shot of (currentNode.kind==='group'||recipe.pattern==='lob'?[]:launches(effectiveRecipe(),o,target))){if(recipe.radius>0){ctx.save();ctx.strokeStyle='#ffffff50';ctx.beginPath();ctx.moveTo(...o);ctx.lineTo(shot.x,shot.y);ctx.stroke();ctx.restore();}ctx.beginPath();ctx.moveTo(shot.x,shot.y);ctx.lineTo(shot.x+Math.cos(shot.angle+recipe.angleOffset*Math.PI/180)*150,shot.y+Math.sin(shot.angle+recipe.angleOffset*Math.PI/180)*150);ctx.stroke();}ctx.restore();
  const highlighted=new Set(flatten(rootDoc).filter(e=>e.path.some(id=>selectedLayers.has(id))).map(e=>e.node.id));
  for(const b of sim.bullets){ctx.save();if(selectedLayers.size&&!highlighted.has(b.layerId))ctx.globalAlpha=.35;ctx.beginPath();ctx.arc(b.x,b.y,5.5,0,Math.PI*2);ctx.fillStyle=(b.pattern==='lob'||b.ammo==='normal')?'#dce889':'#ccb5ed';ctx.fill();ctx.strokeStyle=(b.pattern==='lob'||b.ammo==='normal')?'#628e34':'#8361ac';ctx.lineWidth=2;ctx.stroke();ctx.restore();}
  ctx.save();ctx.strokeStyle='#fff8';ctx.setLineDash([4,5]);if(currentNode.kind==='attack'&&recipe.pattern!=='lob'&&recipe.radius>0){ctx.beginPath();ctx.arc(...o,recipe.radius,0,Math.PI*2);ctx.stroke();}ctx.setLineDash([]);if(currentNode.kind==='attack'&&recipe.pattern!=='lob'&&recipe.originPreset==='custom'){ctx.fillStyle='rgba(255,255,255,.55)';ctx.beginPath();ctx.arc(...o,4,0,Math.PI*2);ctx.fill();}ctx.restore();
  renderTimeline(sim.time);$('timeline').value=sim.time%timelineDuration;$('timelineTime').textContent=sim.time.toFixed(2)+' 秒';
  $('counter').textContent=`在场 ${sim.bullets.length}${sim.evicted?' · 已清理 '+sim.evicted:''}`;
  return target;
}
async function act(action){
  if(locked)return;
  if(action!=='cancel'&&[...document.querySelectorAll('input[type=number]')].some(i=>!i.disabled&&!i.closest('#groupPanel')&&(!i.checkValidity()||i.value===''))){announce('请先修正无效的数值',true);return;}
  locked=true;
  try{const response=await fetch('api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,recipe:rootDoc,sessionId:state.sessionId,transactionId:state.transactionId})});const data=await response.json();if(!response.ok)throw Error(data.error);
    dirty=false;announce(data.status==='draft'?'草稿已保存，尚未采用':data.status==='confirmed'?'方案已确认 · 等待AI落地并验证':data.status==='viewed'?'查看已结束，未采用任何修改':'已取消，原方案未更改');
    if(data.status!=='draft'){paused=true;state.done=true;document.body.classList.add('finished');for(const b of document.querySelectorAll('button,input,select'))b.disabled=true;}
  }catch(e){announce(e.message,true);}finally{locked=false;}
}

function locate(id,node=rootDoc.root,parent=null){if(node.id===id)return {node,parent};if(node.kind==='group')for(const child of node.children){const found=locate(id,child,node);if(found)return found;}return null;}
function selectNode(node){currentNode=node;selectedLayers.clear();selectionAnchor=null;if(node.kind==='attack')selectedLayers.add(node.id);if(node.kind==='attack'){lastAttack=node;recipe=node.recipe;}sync();reset();}
function newAttack(){const r=structuredClone(state.defaultRecipe);r.id=crypto.randomUUID();r.pattern='straight';r.count=1;r.direction=0;r.angleOffset=0;r.shotDelaySeconds=0;return {kind:'attack',id:crypto.randomUUID(),name:'攻击 '+(flatten(rootDoc).length+1),enabled:true,recipe:r};}
function renderComposition(){
  const isGroup=currentNode.kind==='group';$('groupPanel').hidden=!isGroup;$('groupView').disabled=false;$('groupView').setAttribute('aria-current',isGroup?'page':'false');
  for(const section of document.querySelectorAll('[data-attack-section]'))section.hidden=isGroup||(recipe.pattern==='lob'&&['originSection','ammoSection'].includes(section.id));
  $('treePanel').hidden=!isGroup;document.querySelector('.composition-nav').classList.toggle('tree-open',isGroup);
  if(!isGroup)return;
  renderLayerTree();
  renderSelectionProperties();
}

function renderLayerTree(){
  const list=$('layerList');list.setAttribute('aria-multiselectable','true');list.replaceChildren();
  function append(node,parent,depth,inheritedEnabled){
    const row=document.createElement('div');row.className='layer-row'+(selectedLayers.has(node.id)?' selected':'')+(!inheritedEnabled||!node.enabled?' muted-layer':'');row.style.setProperty('--depth',depth);
    row.setAttribute('role','treeitem');row.setAttribute('aria-level',depth+1);row.setAttribute('aria-selected',selectedLayers.has(node.id));row.dataset.nodeId=node.id;
    function selectRow(e){
      if(e.detail>1)return;
      const result=chooseLayers(selectedLayers,node.id,[...list.querySelectorAll('.layer-row')].map(r=>r.dataset.nodeId),selectionAnchor,e);
      selectedLayers=result.selected;selectionAnchor=result.anchor;
      if(node.kind==='attack'){lastAttack=node;recipe=node.recipe;}
      for(const item of list.querySelectorAll('.layer-row')){const selected=selectedLayers.has(item.dataset.nodeId);item.classList.toggle('selected',selected);item.setAttribute('aria-selected',selected);}
      renderSelectionProperties();
    }
    function enter(){if(node.kind==='group'){if(collapsedLayers.has(node.id))collapsedLayers.delete(node.id);else collapsedLayers.add(node.id);renderLayerTree();}else selectNode(node);}
    row.onclick=e=>{if(!e.target.closest('button,input,.layer-menu'))selectRow(e);};row.ondblclick=e=>{if(!e.target.closest('button,input,.layer-menu'))enter();};
    attachLayerDrag(row,node);
    if(node.kind==='group')row.setAttribute('aria-expanded',!collapsedLayers.has(node.id));
    const visible=document.createElement('button');visible.className='layer-visibility';visible.setAttribute('aria-label',`显示 ${node.name}`);visible.setAttribute('aria-pressed',node.enabled);visible.innerHTML='<svg viewBox="0 0 24 24"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>';visible.onclick=()=>{node.enabled=!node.enabled;change();};
    const content=document.createElement('div');content.className='layer-content';
    if(node.kind==='group'){
      const folder=document.createElement('button');folder.className='layer-folder';const closed=collapsedLayers.has(node.id);
      folder.setAttribute('aria-label',`${closed?'展开':'折叠'} ${node.name}`);
      folder.innerHTML=closed?'<svg viewBox="0 0 24 24"><path d="M3 8V6a2 2 0 0 1 2-2h4l3 3h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8Z"/></svg>':'<svg viewBox="0 0 24 24"><path d="M3 10V6a2 2 0 0 1 2-2h4l3 3h7a2 2 0 0 1 2 2v1"/><path d="M3 10h18l-3 10H5L3 10Z"/></svg>';
      folder.onclick=e=>{e.stopPropagation();if(closed)collapsedLayers.delete(node.id);else collapsedLayers.add(node.id);renderLayerTree();};content.append(folder);
    }else{
      const icon=document.createElement('span');icon.className='layer-icon layer-thumbnail';icon.setAttribute('aria-label',labels[node.recipe.pattern]+'缩略图');
      icon.append(document.querySelector(`[data-pattern="${node.recipe.pattern}"] svg`).cloneNode(true));content.append(icon);
    }
    if(renameId===node.id){
      const input=document.createElement('input');input.className='layer-rename';input.value=node.name;input.maxLength=64;input.setAttribute('aria-label',`重命名 ${node.name}`);let finished=false;
      function finish(commit){if(finished)return;finished=true;renameId=null;if(commit&&input.value.trim()){node.name=input.value.trim();change();}else renderLayerTree();}
      input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();finish(true);}if(e.key==='Escape'){e.preventDefault();finish(false);}};input.onblur=()=>finish(true);content.append(input);
    }else{
      const label=document.createElement('button');label.className='layer-name';label.textContent=node.name;label.title=node.name;label.setAttribute('aria-label',`选择 ${node.name}`);label.onclick=e=>{e.stopPropagation();selectRow(e);};label.ondblclick=e=>{e.stopPropagation();enter();};content.append(label);
    }
    if(modifiedLayer(node,state.defaultRecipe??state.recipe)){const mark=document.createElement('span');mark.className='layer-modified';mark.title='倍率不是1或发射延迟不是0';mark.setAttribute('aria-label','属性与默认值不同');content.append(mark);}
    const more=document.createElement('button');more.className='layer-more';more.innerHTML='<svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>';more.classList.toggle('open',menuId===node.id);more.setAttribute('aria-label',`${node.name} 更多操作`);more.setAttribute('aria-haspopup','menu');more.setAttribute('aria-expanded',menuId===node.id);more.onclick=e=>{e.stopPropagation();menuId=menuId===node.id?null:node.id;renderLayerTree();};
    row.append(visible,content,more);list.append(row);
    if(menuId===node.id){
      const menu=document.createElement('div');menu.className='layer-menu';menu.setAttribute('role','menu');
      const rename=document.createElement('button');rename.textContent='重命名';rename.setAttribute('role','menuitem');rename.onclick=e=>{e.stopPropagation();menuId=null;renameId=node.id;renderLayerTree();const input=list.querySelector('.layer-rename');input.focus();input.select();};
      const remove=document.createElement('button');remove.textContent='删除';remove.setAttribute('role','menuitem');remove.disabled=!parent;remove.onclick=e=>{e.stopPropagation();menuId=null;parent.children=parent.children.filter(n=>n!==node);if(!locate(lastAttack.id)){lastAttack=flatten(rootDoc)[0]?.node??lastAttack;recipe=lastAttack.recipe;}if(!locate(currentNode.id))currentNode=parent;for(const id of selectedLayers)if(!locate(id))selectedLayers.delete(id);change();};const edit=document.createElement('button');edit.textContent='进入编辑';edit.setAttribute('role','menuitem');edit.onclick=e=>{e.stopPropagation();menuId=null;selectNode(node);};if(node.kind==='attack')menu.append(edit);menu.append(rename,remove);row.append(menu);
    }
    if(node.kind==='group'&&!collapsedLayers.has(node.id))for(const child of node.children)append(child,node,depth+1,inheritedEnabled&&node.enabled);
  }
  if(modifiedLayer(rootDoc.root)||rootDoc.root.rangeMultiplier!==1)append(rootDoc.root,null,0,true);else for(const child of rootDoc.root.children)append(child,rootDoc.root,0,rootDoc.root.enabled);
  if(!list.children.length){const empty=document.createElement('div');empty.className='empty-layers';empty.textContent='暂无攻击图层';list.append(empty);}
}
function clearDropHint(){for(const row of document.querySelectorAll('.layer-row')){row.classList.remove('drop-before','drop-after','drop-inside');row.removeAttribute('data-drop-label');}}
function attachLayerDrag(row,node){
  row.draggable=node!==rootDoc.root;
  row.ondragstart=e=>{
    if(e.target.closest('input,.layer-more,.layer-visibility,.layer-folder')||!row.draggable){e.preventDefault();return;}
    if(!selectedLayers.has(node.id)){selectedLayers=new Set([node.id]);selectionAnchor=node.id;}
    draggedLayers=[...selectedLayers].filter(id=>id!==rootDoc.root.id);
    if(!draggedLayers.length){e.preventDefault();return;}
    e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',draggedLayers.join(','));
    for(const item of document.querySelectorAll('.layer-row')){const selected=selectedLayers.has(item.dataset.nodeId);item.classList.toggle('selected',selected);item.setAttribute('aria-selected',selected);}renderSelectionProperties();
  };
  function destination(e){const rect=row.getBoundingClientRect(),ratio=(e.clientY-rect.top)/rect.height;return node===rootDoc.root?'inside':node.kind==='group'&&ratio>=.33&&ratio<=.67?'inside':ratio<.5?'before':'after';}
  row.ondragover=e=>{
    if(!draggedLayers)return;e.preventDefault();e.stopPropagation();clearDropHint();
    const placement=destination(e);
    try{moveLayers(rootDoc,draggedLayers,node.id,placement);e.dataTransfer.dropEffect='move';row.classList.add('drop-'+placement);row.dataset.dropLabel=placement==='inside'?`放入「${node.name}」`:`放在「${node.name}」${placement==='before'?'上方':'下方'}`;}
    catch(error){e.dataTransfer.dropEffect='none';}
    const list=$('layerList'),bounds=$('treePanel').getBoundingClientRect();
    if(e.clientY<bounds.top+28)list.closest('aside').scrollTop-=10;else if(e.clientY>Math.min(bounds.bottom,window.innerHeight-80)-28)list.closest('aside').scrollTop+=10;
  };
  row.ondragleave=e=>{if(!row.contains(e.relatedTarget))clearDropHint();};
  row.ondrop=e=>{
    if(!draggedLayers)return;e.preventDefault();e.stopPropagation();const placement=destination(e),ids=draggedLayers;draggedLayers=null;clearDropHint();
    try{const next=moveLayers(rootDoc,ids,node.id,placement),viewId=currentNode.id,attackId=lastAttack.id;rootDoc=next;currentNode=locate(viewId)?.node??rootDoc.root;lastAttack=locate(attackId)?.node??flatten(rootDoc)[0].node;recipe=lastAttack.recipe;if(placement==='inside')collapsedLayers.delete(node.id);change();announce('已更新图层顺序与分组');}
    catch(error){announce(error.message,true);}
  };
  row.ondragend=()=>{draggedLayers=null;clearDropHint();};
}
document.addEventListener('click',e=>{if(menuId&&!e.target.closest('.layer-menu')){menuId=null;renderLayerTree();}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){menuId=null;clearDropHint();if(draggedLayers){draggedLayers=null;return;}selectedLayers.clear();selectionAnchor=null;renderLayerTree();renderSelectionProperties();}});
function editingText(){const el=document.activeElement;return el?.matches('input,textarea,select,[contenteditable=true]')||el?.isContentEditable;}
let layerClipboard=null;
document.addEventListener('copy',e=>{
  if(locked||state?.done||currentNode.kind!=='group'||editingText()||!selectedLayers.size||window.getSelection()?.toString())return;
  const payload=copyLayers(rootDoc,selectedLayers);if(!payload.nodes.length)return;
  const text=JSON.stringify(payload);e.clipboardData?.setData('application/x-pvzhe-attack-layers',text);e.clipboardData?.setData('text/plain',text);e.preventDefault();layerClipboard=payload;announce(`已复制 ${payload.nodes.length} 项`);
});
document.addEventListener('paste',e=>{
  if(locked||state?.done||currentNode.kind!=='group'||editingText())return;
  const text=e.clipboardData?.getData('application/x-pvzhe-attack-layers')||e.clipboardData?.getData('text/plain');
  let payload=layerClipboard;
  if(text){if(text.length>1000000||!text.includes('pvzhe.attack-layers'))return;try{payload=JSON.parse(text);}catch{return;}}
  if(!payload)return;e.preventDefault();
  try{const pasted=pasteLayers(rootDoc,payload,currentNode.id),viewId=currentNode.id,attackId=lastAttack.id;rootDoc=pasted.document;currentNode=locate(viewId).node;lastAttack=locate(attackId)?.node??lastAttack;recipe=lastAttack.recipe;selectedLayers=new Set(pasted.ids);selectionAnchor=pasted.ids[0];collapsedLayers.delete(currentNode.id);change();announce(`已粘贴 ${pasted.ids.length} 项`);}
  catch(error){announce(error.message,true);}
});
$('groupView').onclick=()=>{if(currentNode.kind==='group'){selectedLayers.clear();selectionAnchor=null;renderLayerTree();renderSelectionProperties();}else selectNode(rootDoc.root);};
$('addAttack').onclick=()=>{if(flatten(rootDoc).length>=32){announce('最多32个攻击图层',true);return;}const node=newAttack();currentNode.children.push(node);collapsedLayers.delete(currentNode.id);selectedLayers.clear();selectedLayers.add(node.id);lastAttack=node;recipe=node.recipe;change();announce('已添加独立攻击图层，双击可编辑');};
$('addGroup').onclick=()=>{if(groupDepth(rootDoc,currentNode.id)>=4){announce('已达到攻击组嵌套上限',true);return;}const node={kind:'group',id:crypto.randomUUID(),name:'新攻击组',enabled:true,speedMultiplier:1,rateMultiplier:1,rangeMultiplier:1,children:[]};currentNode.children.push(node);collapsedLayers.delete(currentNode.id);selectedLayers.clear();selectedLayers.add(node.id);change();announce('已添加空攻击组');};

function selectionNodes(){return [...selectedLayers].map(id=>locate(id)?.node).filter(Boolean);}
function renderSelectionProperties(){
  const nodes=selectionNodes();$('selectionLabel').textContent=nodes.length?`已选 ${nodes.length} 项`:'未选择图层';
  for(const [id,key] of [['groupRate','rateMultiplier'],['groupSpeed','speedMultiplier'],['groupDelay','startDelaySeconds']]){
    const value=selectionValue(nodes,key),mixed=nodes.length>0&&value===null;
    $(id+'Warning').hidden=!mixed;if(!mixed)hidePropertyTooltip();$(id).disabled=$(id+'Number').disabled=!nodes.length;
    $(id).classList.toggle('mixed',mixed);$(id).setAttribute('aria-valuetext',mixed?'多个不同值':value??'未选择');
    $(id).value=value===null?1:roundParameter(value);
    if(document.activeElement!==$(id+'Number'))$(id+'Number').value=value===null?'':roundParameter(value);
    $(id+'Number').placeholder=mixed?'不同值':'—';
    if(value!==null&&key!=='startDelaySeconds'){$(id).max=Math.max(10,value);$(id).min=Math.min(.1,value);}
  }
}
const propertyTooltip=$('propertyTooltip');
function hidePropertyTooltip(){propertyTooltip.hidden=true;}
for(const id of ['groupRate','groupSpeed','groupDelay']){
  const warning=$(id+'Warning'),message=warning.querySelector('.mixed-tooltip').textContent;
  warning.onmouseenter=warning.onfocus=()=>{const r=warning.getBoundingClientRect();propertyTooltip.textContent=message;propertyTooltip.hidden=false;const width=Math.min(250,innerWidth-24);propertyTooltip.style.width=width+'px';propertyTooltip.style.left=Math.max(12,Math.min(innerWidth-width-12,r.left-24))+'px';const height=propertyTooltip.getBoundingClientRect().height;propertyTooltip.style.top=Math.max(12,Math.min(innerHeight-height-12,r.top-height-8))+'px';};
  warning.onmouseleave=warning.onblur=hidePropertyTooltip;
}
window.addEventListener('scroll',hidePropertyTooltip,true);window.addEventListener('resize',hidePropertyTooltip);
for(const [id,key] of [['groupRate','rateMultiplier'],['groupSpeed','speedMultiplier'],['groupDelay','startDelaySeconds']]){
  const update=e=>{
    if(e.target.value===''||!e.target.checkValidity())return;
    try{const candidate=editLayerProperties(rootDoc,selectedLayers,key,Number(e.target.value)),viewId=currentNode.id,attackId=lastAttack.id;rootDoc=candidate;currentNode=locate(viewId).node;lastAttack=locate(attackId)?.node??lastAttack;recipe=lastAttack.recipe;change();}
    catch(error){renderSelectionProperties();announce(error.message,true);}
  };
  $(id).oninput=update;$(id+'Number').oninput=update;
  $(id+'Number').onblur=()=>renderSelectionProperties();
}
$('save').onclick=()=>act('save');$('confirm').onclick=()=>act('confirm');$('cancel').onclick=()=>act('cancel');
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
async function start(){
  state=await(await fetch('api/state')).json();rootDoc=wrap(state.recipe);lastAttack=flatten(rootDoc)[0]?.node??{kind:'attack',recipe:structuredClone(state.defaultRecipe)};currentNode=flatten(rootDoc)[0]?.node??rootDoc.root;recipe=lastAttack.recipe;if(currentNode.kind==='attack')selectedLayers.add(currentNode.id);if(!state.target.hitBoxRect)throw Error('素材会话缺少发行受击矩形，请重新运行 attack_preview_prepare.py');canvas.width=state.canvas[0];canvas.height=state.canvas[1];
  if(state.viewOnly){$('modeBadge').textContent='仅查看';$('confirm').textContent='结束查看';$('save').textContent='保存试调';announce('仅查看 · 试调不会修改正式方案');}
  // Older live prototype servers did not include the crop in their state response.
  state.backgroundCrop??=[0,0,...state.canvas];
  for(const [id,p] of Object.entries(state.originPresets.presets)){const option=document.createElement('option');option.value=id;option.textContent=p.label;$('originPreset').appendChild(option);}
  const custom=document.createElement('option');custom.value='custom';custom.textContent='自定义';$('originPreset').appendChild(custom);
  targetBase.push(...state.target.position);$('assetNote').textContent=state.demo?'示意素材':'原版素材';
  for(const [key,url]of Object.entries(state.assets)){images[key]=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('素材加载失败：'+key));im.src=url;});}
  if(images.background){
    const crop=state.backgroundCrop,im=images.background;
    if(!Array.isArray(crop)||crop.length!==4||!crop.every(Number.isFinite))throw Error('缺少有效背景裁剪范围');
    const [x,y,right,bottom]=crop;
    if(x<0||y<0||right>im.width||bottom>im.height||right<=x||bottom<=y||Math.abs((right-x)/(bottom-y)-canvas.width/canvas.height)>.001)throw Error('背景裁剪范围与逻辑画布不匹配，不能拉伸代替');
  }
  const area=document.querySelector('.stage-area'),stage=document.querySelector('.stage');
  function fitStage(){const w=Math.max(1,Math.min(area.clientWidth-2,(area.clientHeight-2)*canvas.width/canvas.height));stage.style.width=(w+2)+'px';stage.style.height=(w*canvas.height/canvas.width+2)+'px';}
  new ResizeObserver(fitStage).observe(area);fitStage();
  sync();reset();if(state.migrationNote)announce(state.migrationNote);if(state.done){document.body.classList.add('finished');for(const b of document.querySelectorAll('button,input,select'))b.disabled=true;announce('本轮已结束，请由AI创建新会话');paused=true;}
  let last=performance.now();function frame(now){const dt=Math.min(.05,(now-last)/1000);last=now;const t=[targetBase[0],targetBase[1]+(moving?Math.sin(sim.time*.9)*85:0)];if(!paused)sim.step(dt,t);draw();requestAnimationFrame(frame);}requestAnimationFrame(frame);
}
start().catch(e=>announce('无法打开预览：'+e.message,true));
