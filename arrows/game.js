'use strict';
const $ = id => document.getElementById(id);
const board = $('board');
const ns = 'http://www.w3.org/2000/svg';
const key = 'zigzag-arrows.v1';
let saved;
try { saved = JSON.parse(localStorage.getItem(key)); } catch {}
if (!saved || !Array.isArray(saved.wins) || !saved.games || typeof saved.games !== 'object') {
  saved = {level:0,wins:[],games:{}};
}
let variant=0, resizePending=false;
let level, index, pieces, lives, removed, epoch=0, terminal=false;
const layoutVersion="interlock2", shaftWidth=5;
const reward=10, hintPrice=10;
saved.wins=[...new Set(saved.wins.filter(i=>Number.isInteger(i)&&LEVELS[i]))];
const balance=()=>saved.wins.length*reward-(saved.hintsUnlocked?hintPrice:0);
const active=new Set();
let dimensions, hinted=-1, trialUsed=false, earnedReward=false;
function persist() {
  saved.level=index;
  saved.games[index]={layout:layoutVersion,variant,lives,trialUsed,removed:[...removed]};
  try {localStorage.setItem(key, JSON.stringify(saved));} catch {}
}
function el(tag, attrs) {
  const node=document.createElementNS(ns,tag);
  for(const [k,v] of Object.entries(attrs)) node.setAttribute(k,v);
  return node;
}
function direction(a,b) { return [Math.sign(b[0]-a[0]),Math.sign(b[1]-a[1])]; }
function move([x,y],[dx,dy],t) { return [x+dx*t,y+dy*t]; }
function pathGeometry(points) {
  const lengths=[0];
  for(let i=1;i<points.length;i++) {
    const a=points[i-1], b=points[i];
    const length=Math.abs(b[0]-a[0])+Math.abs(b[1]-a[1]);
    lengths.push(lengths[i-1]+length);
  }
  return {points,lengths,length:lengths.at(-1),tip:points.at(-1),dir:direction(points.at(-2),points.at(-1))};
}
function prepare(points) {
  const p=pathGeometry(points);
  p.cells=new Set();
  for(let i=1;i<points.length;i++){
    const dir=direction(points[i-1],points[i]);
    for(let n=0;n<=p.lengths[i]-p.lengths[i-1];n++)
      p.cells.add(move(points[i-1],dir,n).join(','));
  }
  return p;
}
// Keep blockers in distance order so a tap only scans its own exit ray.
function indexBlockers(paths,cols,rows){
  const owners=new Map();
  paths.forEach((path,id)=>path.cells.forEach(cell=>owners.set(cell,id)));
  for(const [id,path] of paths.entries()){
    path.blockers=[];
    let [x,y]=path.tip;
    const [dx,dy]=path.dir;
    for(let step=1;;step++){
      x+=dx;y+=dy;
      if(x<0||y<0||x>=cols||y>=rows)break;
      const owner=owners.get(x+','+y);
      if(owner!==undefined && owner!==id)path.blockers.push({owner,step});
    }
  }
}
function obstacle(id){
  return pieces[id].blockers.find(hit=>!removed.has(hit.owner))?.step ?? Infinity;
}
function prepareVariant(layout,mask){
  const paths=layout.arrows.map(points=>{
    if(!mask)return prepare(points);
    const [sx,sy]=layout.split;
    const right=points[0][0]>=sx, lower=points[0][1]>=sy;
    const flip=(mask>>(2*(Number(right)+2*Number(lower))))&3;
    return prepare(points.map(([x,y])=>[
      flip&1?(right?sx+layout.cols:sx)-1-x:x,
      flip&2?(lower?sy+layout.rows:sy)-1-y:y
    ]));
  });
  indexBlockers(paths,layout.cols,layout.rows);
  return paths;
}
function canClear(paths){
  const cleared=new Set();
  while(cleared.size<paths.length){
    const before=cleared.size;
    paths.forEach((p,i)=>{if(p.blockers.every(hit=>cleared.has(hit.owner)))cleared.add(i)});
    if(before===cleared.size)return false;
  }
  return true;
}
function allQuadrantsLinked(paths,layout){
  const [sx,sy]=layout.split;
  const zones=paths.map(p=>Number(p.tip[0]>=sx)+2*Number(p.tip[1]>=sy));
  const joined=new Set();
  paths.forEach((p,i)=>p.blockers.forEach(({owner})=>{
    if(zones[i]!==zones[owner]){joined.add(zones[i]);joined.add(zones[owner])}
  }));
  return joined.size===4;
}
function shuffleQuadrants(){
  // Reflections keep every path inside its quadrant. Accept only solvable combinations.
  const start=Math.floor(Math.random()*256);
  for(let offset=0;offset<256;offset++){
    const mask=(start+offset)%256;
    if(mask===(variant&255))continue;
    const candidate=prepareVariant(level,mask);
    if(allQuadrantsLinked(candidate,level)&&canClear(candidate)){openLevel(index,true,mask|(variant&256));return}
  }
  // A whole-board reflection preserves every dependency. Swap the left/right
  // quadrant masks as well, so this is an exact reflection of the current game.
  const mirrored=((variant&51)<<2)|((variant&204)>>2);
  openLevel(index,true,mirrored|((variant^256)&256));
}
function pointAt(p,t) {
  for(let i=1;i<p.points.length;i++) {
    if(t<=p.lengths[i]) return move(p.points[i-1],direction(p.points[i-1],p.points[i]),t-p.lengths[i-1]);
  }
  return move(p.tip,p.dir,t-p.length);
}
// Slide a fixed-length window along the original polyline and its outgoing ray.
function paint(p,travel=0) {
  const shape=p.shape;
  const start=pointAt(shape,travel);
  const neck=shape.length+travel-dimensions.headBack;
  const base=pointAt(shape,neck);
  const tip=move(base,p.dir,dimensions.headLength);
  const path=[start];
  for(let i=1;i<shape.points.length;i++) {
    if(shape.lengths[i]>travel && shape.lengths[i]<neck) path.push(shape.points[i]);
  }
  path.push(base);
  const shaft='M'+path.map(pt=>pt.join(' ')).join(' L');
  p.line.setAttribute('d',shaft);
  if(!travel){
    for(const stroke of [p.hit,p.halo]) stroke.setAttribute('d',shaft+' L'+tip.join(' '));
    p.halo.setAttribute('stroke-width',dimensions.halo);
    p.hit.setAttribute('stroke-width',dimensions.hit);
  }
  const perp=[-p.dir[1],p.dir[0]];
  p.head.setAttribute('points',[tip,move(base,perp,dimensions.headHalfWidth),move(base,perp,-dimensions.headHalfWidth)].map(pt=>pt.join(',')).join(' '));
}
function createArrow(p,id) {
  const [dx,dy]=p.dir;
  const dir=dx>0?'右':dx<0?'左':dy>0?'下':'上';
  const g=el('g',{class:'arrow',tabindex:'0',role:'button','aria-label':'箭头 '+(id+1)+'，朝'+dir,'data-id':id});
  const stroke=(color,events)=>el('path',{fill:'none',stroke:color,'stroke-linecap':'round','stroke-linejoin':'round','pointer-events':events});
  p.halo=stroke('#bbdd77','none');p.halo.setAttribute('class','halo');
  p.line=stroke('#171916','none');
  p.line.setAttribute('stroke-width',shaftWidth);
  p.line.setAttribute('vector-effect','non-scaling-stroke');
  p.head=el('polygon',{fill:'#171916'});
  p.hit=stroke('transparent','stroke');
  p.group=g;
  g.append(p.halo,p.line,p.head,p.hit);board.append(g);paint(p);
  g.addEventListener('click',()=>pull(id));
  g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();if(!e.repeat)pull(id);}});
}
function resizeBoard(){
  if(active.size){resizePending=true;return}
  resizePending=false;
  const {width,height}=board.getBoundingClientRect();
  if(!width||!height)return;
  const padding=Math.min(15,Math.min(width,height)*.043);
  const seam=level.split?1:0;
  const dx=(width-2*padding)/(level.cols-1+seam),dy=(height-2*padding)/(level.rows-1+seam);
  const [sx,sy]=level.split || [Infinity,Infinity];
  const cell=Math.min(dx,dy);
  const headLength=Math.min(20,1.06*cell);
  const headBack=Math.min(.92*cell,headLength*.76);
  dimensions={dx,dy,headLength,headBack,headHalfWidth:headLength*Math.tan(Math.PI/12),
    halo:shaftWidth+cell*.22,hit:Math.min(.95*cell,Math.max(.65*cell,29))};
  board.setAttribute('viewBox',`0 0 ${width} ${height}`);
  const dots=board.querySelector('pattern');
  dots.setAttribute('x',padding-dx/2);dots.setAttribute('y',padding-dy/2);
  dots.setAttribute('width',dx);dots.setAttribute('height',dy);
  dots.firstChild.setAttribute('cx',dx/2);dots.firstChild.setAttribute('cy',dy/2);
  if(level.split){
    const cx=padding+sx*dx,cy=padding+sy*dy;
    const halfGap=4;
    board.querySelectorAll('.quadrant-card').forEach((card,i)=>{
      const right=i%2===1,bottom=i>=2;
      const x=right?cx+halfGap:1,y=bottom?cy+halfGap:1;
      const w=(right?width-1:cx-halfGap)-x,h=(bottom?height-1:cy-halfGap)-y;
      for(const rect of card.children){
        rect.setAttribute('x',x);rect.setAttribute('y',y);
        rect.setAttribute('width',w);rect.setAttribute('height',h);
      }
    });
  }
  for(const p of pieces){
    p.shape=pathGeometry(p.points.map(([x,y])=>[padding+(x+Number(x>=sx))*dx,padding+(y+Number(y>=sy))*dy]));
    if(p.group?.isConnected)paint(p);
  }
}
function buildBoard(){
  board.replaceChildren();
  const defs=el('defs',{}), pattern=el('pattern',{id:'dots',x:'-.5',y:'-.5',width:1,height:1,patternUnits:'userSpaceOnUse'});
  pattern.append(el('circle',{cx:'.5',cy:'.5',r:'.95',fill:'#d3d8c9'}));defs.append(pattern);
  board.append(defs);
  board.parentElement.classList.toggle('four-cards',Boolean(level.split));
  if(level.split){
    for(let i=0;i<4;i++){
      const card=el('g',{class:'quadrant-card','pointer-events':'none'});
      card.append(el('rect',{class:'card-face',rx:12}),el('rect',{fill:'url(#dots)',rx:12}));
      board.append(card);
    }
  }else{
    board.append(el('rect',{x:0,y:0,width:'100%',height:'100%',fill:'url(#dots)','pointer-events':'none'}));
  }
  resizeBoard();pieces.forEach((p,id)=>{if(!removed.has(id))createArrow(p,id)});
}
function update(){
  $('level-number').textContent='第 '+(index+1)+' 关';
  $('hearts').setAttribute('aria-label','剩余 '+lives+' 次机会');
  $('hearts').innerHTML='<span aria-hidden="true">'+'♥'.repeat(lives)+'<span class="lost">'+'♥'.repeat(3-lives)+'</span></span>';
  $('hint').textContent=trialUsed&&!saved.hintsUnlocked?'解锁提示':'提示';
}
function openLevel(i,fresh=false,mask){
  epoch++;active.clear();earnedReward=false;hinted=-1;
  index=i;level=LEVELS[i];
  const previous=!fresh && saved.games[i]?.layout===layoutVersion ? saved.games[i] : null;
  const storedMask=mask ?? (!fresh?previous?.variant:i===saved.level?saved.games[i]?.variant:0);
  variant=level.split&&Number.isInteger(storedMask)&&storedMask>=0&&storedMask<512?storedMask:0;
  if(variant&256){
    const {cols,split,arrows}=level;
    level={...level,split:[cols-split[0],split[1]],arrows:arrows.map(p=>p.map(([x,y])=>[cols-1-x,y]))};
  }
  pieces=prepareVariant(level,variant&255);
  trialUsed=Boolean(previous?.trialUsed);
  lives=Number.isInteger(previous?.lives)&&previous.lives>=0&&previous.lives<=3?previous.lives:3;
  removed=new Set((Array.isArray(previous?.removed)?previous.removed:[]).filter(n=>Number.isInteger(n)&&n>=0&&n<pieces.length));
  if(removed.size===pieces.length||lives===0){lives=3;removed.clear();trialUsed=false}
  $('status').textContent=level.split?'四宫格 · 相邻宫格也会阻挡出口。':i===0?'可连续点击前方畅通的箭头。':'';
  buildBoard();update();persist();
}
function dialog(title,message,actions,required=false){
  const modal=$('modal');terminal=required;
  $('modal-title').textContent=title;$('message').textContent=message;
  $('dialog-actions').replaceChildren(...actions.map(([name,action])=>{const b=document.createElement('button');b.className='quiet';b.textContent=name;b.onclick=()=>{modal.close();action?.()};return b}));
  if(!modal.open)modal.showModal();
}
function clearHint(){if(hinted>=0)pieces[hinted].group?.classList.remove('hinted');hinted=-1}
function pull(id){
  if(!lives||active.has(id)||removed.has(id)||$('modal').open)return;
  clearHint();
  const token=epoch,p=pieces[id],block=obstacle(id),free=!Number.isFinite(block);
  const [x,y]=p.shape.tip,[dx,dy]=p.dir;
  const bounds=board.viewBox.baseVal;
  const exit=dx>0?bounds.width-x:dx<0?x:dy>0?bounds.height-y:y;
  active.add(id);
  p.group.classList.add('moving');
  p.group.classList.toggle('blocked',!free);
  if(free){
    removed.add(id);
    p.group.removeAttribute('tabindex');
    if(removed.size===pieces.length&&!saved.wins.includes(index)){
      saved.wins.push(index);
      earnedReward=true;
    }
  }else{
    lives--;
  }
  persist();update();
  const pitch=dx?dimensions.dx:dimensions.dy;
  let steps=block;
  if(!free&&level.split){
    const axis=dx?0:1,split=level.split[axis],tip=p.tip[axis];
    if((tip<split)!==(tip+block*p.dir[axis]<split))steps++;
  }
  const distance=free?p.shape.length+exit+12:Math.max(1,steps*pitch-2*(dimensions.headLength-dimensions.headBack)-5);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const ms=reduced?75:free?Math.min(1200,320+distance/pitch*33):Math.min(780,330+distance/pitch*42);
  const start=performance.now();
  $('status').textContent=free?'':'前方被挡住了。';
  const step=now=>{
    if(token!==epoch)return;
    const t=Math.min(1,(now-start)/ms);
    const travel=free?distance*t*(.72+.28*t):distance*Math.sin(Math.PI*t)**2;
    paint(p,travel);
    if(t<1){requestAnimationFrame(step);return}
    active.delete(id);
    if(free)p.group.remove();
    else{paint(p);p.group.classList.remove('moving')}
    if(active.size)return;
    if(resizePending)resizeBoard();
    if(removed.size===pieces.length){
      const next=Array.from({length:LEVELS.length},(_,k)=>(index+1+k)%LEVELS.length).find(i=>!saved.wins.includes(i));
      dialog(next===undefined?'全部通关':'本关已清空',(next===undefined?'所有折线都找到了出口。':'全部 '+pieces.length+' 支箭头已抽出。')+(earnedReward?'首次通关奖励 '+reward+' 金币。':''),
        [['再玩本关',()=>openLevel(index,true)],next===undefined?['回到第一关',()=>openLevel(0,true)]:['继续挑战',()=>openLevel(next)]],true);
    }else if(!lives){dialog('再试一次','三次机会已用完。先从没有阻挡的箭头开始。',[['重玩本关',()=>openLevel(index,true)]],true)}
  };
  requestAnimationFrame(step);
}
$('modal').addEventListener('cancel',e=>{if(terminal)e.preventDefault()});
function openMenu(){
  const actions=[['玩法',()=>dialog('游戏玩法','可连续点击折线，让多支箭头同时抽出。受阻的箭头会变红并扣除一颗心，清除阻挡后可再次点击。每轮可免费提示一次，首次通关奖励 10 金币，可解锁不限次提示。',[['返回菜单',openMenu],['继续游戏']])]];
  actions.push(['随机四宫格',()=>{
    const options=LEVELS.map((layout,i)=>layout.split&&i!==index?i:-1).filter(i=>i>=0);
    const newLevels=options.filter(i=>!saved.wins.includes(i));
    const pool=newLevels.length?newLevels:options;
    openLevel(pool[Math.floor(Math.random()*pool.length)]);
  }]);
  if(level.split)actions.push(['重排四宫格',()=>dialog('重排四宫格？','重新排列四个区域，从三颗心开始。',[['取消'],['随机重排',shuffleQuadrants]])]);
  if(saved.wins.length)actions.push(['重玩',()=>{
    const played=[...saved.wins].sort((a,b)=>a-b);
    dialog('重玩已通关关卡','选择要重新挑战的关卡。',[...played.map(i=>['第 '+(i+1)+' 关',()=>openLevel(i,true)]),['返回菜单',openMenu]]);
  }]);
  actions.push(['继续游戏']);
  dialog('游戏菜单','金币 '+balance(),actions);
}
$('help').onclick=()=>{if(!active.size)openMenu()};
$('restart').onclick=()=>{if(!active.size)dialog('重新开始本关？','本关的箭头和三次机会都会恢复。',[['继续游戏'],['重新开始',()=>openLevel(index,true)]])};
function showHint(){
  clearHint();hinted=pieces.findIndex((p,i)=>!removed.has(i)&&obstacle(i)===Infinity);
  if(hinted>=0){pieces[hinted].group.classList.add('hinted');$('status').textContent='带有亮色底纹的箭头可以抽出。'}
}
$('hint').onclick=()=>{
  if(active.size)return;
  if(saved.hintsUnlocked || !trialUsed){
    trialUsed=true;persist();update();showHint();return;
  }
  if(balance()<hintPrice){
    dialog('免费提示已使用','本轮有一次免费提示。首次通关可获得 10 金币，解锁后各关均可不限次提示。',[['继续游戏']]);return;
  }
  dialog('解锁不限次提示？','花费 '+hintPrice+' 金币后，所有关卡均可不限次使用提示。',[['取消'],['解锁并提示',()=>{
    saved.hintsUnlocked=true;persist();update();showHint();
  }]]);
};
openLevel(Number.isInteger(saved.level)&&LEVELS[saved.level]?saved.level:0);
new ResizeObserver(resizeBoard).observe(board);
