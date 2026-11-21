'use strict';
const glyphs = {
 game:'<path d="M4 19h6V7h10m-5-5 5 5-5 5"/>',
 grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
 cards:'<rect x="3" y="8" width="15" height="12" rx="2"/><path d="M7 5h12a2 2 0 0 1 2 2v9M7 12h6"/>',
 book:'<path d="M3 4q5-1 9 2 4-3 9-2v15q-5-1-9 2-4-3-9-2zM12 6v15"/>',
 file:'<path d="M5 3h9l5 5v13H5zM14 3v6h5M8 13h8M8 17h6"/>',
 date:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v5m10-5v5M3 11h18"/>',
 user:'<circle cx="12" cy="8" r="3"/><path d="M5 20q0-6 7-6t7 6"/>',
 chev:'<path d="m9 6 6 6-6 6"/>',left:'<path d="m15 6-6 6 6 6"/>',
 search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
 math:'<path d="M3 17h18M6 21V4M3 15c6 1 7-17 11-6s4 6 7-3"/>',
 physics:'<ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(32 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(-32 12 12)"/><circle cx="12" cy="12" r="1"/>',
 chemistry:'<path d="M9 3h6m-5 0v7L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2l-6-9V3M7 15h10"/><path d="M9 18h1"/>',
 mechanics:'<path d="m3 16 17-7M12 14l-4 7h8z"/><circle cx="6" cy="10" r="3"/><path d="M18 3v4m-2-2 2 2 2-2"/>',
 materials:'<path d="m3 7 9-4 9 4-9 4zM3 7v10l9 4 9-4V7M12 11v10m-5-8 2 1m6 2 3-1"/>',
 fluids:'<path d="M4 12c3-4 5 4 8 0s5 4 8 0M4 17c3-4 5 4 8 0s5 4 8 0M10 7c0-2 2-4 2-4s2 2 2 4a2 2 0 0 1-4 0z"/>',
 circuit:'<path d="M2 12h4l2-5 3 10 3-10 3 10 2-5h3"/>',
 signals:'<path d="M2 12h3m2-5v10m4-14v18m4-16v14m4-11v8m2-4h1"/>',
 computing:'<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3"/><rect x="9" y="9" width="6" height="6"/>',
 economics:'<path d="M3 3v18h18M6 15l5-5 4 2 6-7m-5 0h5v5"/>',
 law:'<path d="M12 3v18m-5 0h10M3 7l18-2M6 7l-4 8h8zm12-1-4 8h8z"/>',
 zoom:'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5M7 10h6m-3-3v6"/>'
};
function icon(name,cls=''){return '<svg aria-hidden="true" class="icon '+cls+'" viewBox="0 0 24 24">'+glyphs[name]+'</svg>'}
const subjects=[
 ['math','高等数学','数理基础','向量代数、微积分与微分方程','#4165d9','#eaf0ff'],
 ['physics','大学物理','数理基础','热学、波动与光学','#8853c5','#f1eafb'],
 ['chemistry','普通化学','数理基础','物质结构、化学反应与周期律','#18876c','#e3f4ed'],
 ['mechanics','理论力学','工程力学','静力学、运动学与动力学','#aa671d','#fff1dc'],
 ['materials','材料力学','工程力学','内力、应力与构件变形','#b15555','#ffeded'],
 ['fluids','流体力学','工程力学','流体静力学与流动方程','#1a839b','#e0f4f7'],
 ['circuit','电工电子','电气与信息','电路分析、电机与电子技术','#996326','#fff0dc'],
 ['signals','信号与信息','电气与信息','信号分类、变换与信息传输','#795bbe','#eeeafa'],
 ['computing','计算机技术','电气与信息','计算机系统、网络与数据表示','#426f95','#e7f1fa'],
 ['economics','工程经济','工程管理','资金时间价值与方案评价','#337d6a','#e3f1ec'],
 ['law','法律法规','工程管理','建筑许可、招投标与合同','#806858','#f2ece7']
].map(([id,name,group,summary,color,tint])=>({id,name,group,summary,color,tint}));
const curriculum = window.CURRICULUM;
const docs = Object.values(curriculum.documents);

const lessonsById = new Map();
for (const s of subjects) {
  for (const lesson of courseLessons(s.id)) lessonsById.set(lesson.id, {...lesson, subject:s.id});
}
const lessonOrder = new Map([...lessonsById.keys()].map((id, index) => [id, index]));
const cards = [...(curriculum.lessonCards || []), ...(window.CARDS || []).map(card =>
  ({...card, lesson: curriculum.cards[card.id]?.[0]}))].sort((a, b) =>
  (lessonOrder.get(a.lesson) ?? Infinity) - (lessonOrder.get(b.lesson) ?? Infinity));
const app=document.getElementById('app');
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const style=s=>'style="--color:'+s.color+';--tint:'+s.tint+'"';
const bySubject=id=>subjects.find(s=>s.id===id);
const subjectUrl=id=>'#subject/'+encodeURIComponent(id);
const tile=s=>'<span class="tile" '+style(s)+'>'+icon(s.id)+'</span>';
const day=86400000, minute=60000, intervals=[1,2,4,7,15,30,60,120];
function saved(key){try{return JSON.parse(localStorage.getItem('zhixu.'+key)||'null')}catch{return null}}
function save(key,value){try{localStorage.setItem('zhixu.'+key,JSON.stringify(value))}catch{const n=document.createElement('div');n.className='toast';n.textContent='浏览器未能保存进度，请检查本地存储权限。';document.body.append(n);setTimeout(()=>n.remove(),4000)}}
const cardKey=c=>'review.'+c.id;
function schedule(card){return saved(cardKey(card))}
function loadQueue(id){const now=Date.now(),due=[],fresh=[];for(const c of cards){if(id&&c.subject!==id)continue;const state=schedule(c);if(!state)fresh.push(c);else if(state.due<=now)due.push(c)}due.sort((a,b)=>schedule(a).due-schedule(b).due);return {due,fresh}}
function shell(content,section,crumb,selected=''){
 app.classList.toggle('course-view',Boolean(selected));
 const sideNav=(id,label,url,ico)=>'<a class="navlink '+(section===id?'on':'')+'" href="'+url+'">'+icon(ico)+label+'</a>';
 const gamesNav='<nav class="games-nav" aria-labelledby="games-heading"><p id="games-heading" class="group-label">休闲小游戏</p>'+sideNav('arrows','箭头逃亡','arrows/','game')+'</nav>';
 const trigger = '<button type="button" class="nav-toggle" popovertarget="study-nav" aria-label="打开导航">导航</button>';
 app.innerHTML=trigger+'<aside class="side" id="study-nav" popover aria-label="学习导航"><button class="nav-close" type="button" popovertarget="study-nav" popovertargetaction="hide" aria-label="关闭导航">×</button><a class="brand" href="#home"><img src="assets/mark.svg" alt=""><span><strong>知序</strong><small>STUDY ATLAS</small></span></a><p class="group-label">学习空间</p><nav>'+sideNav('home','学科总览','#home','grid')+sideNav('review','记忆复习','#review','cards')+'</nav><hr class="sidehr"><p class="group-label index-label">学科索引</p><nav class="side-subjects" aria-label="学科索引">'+subjects.map(s=>'<a href="'+subjectUrl(s.id)+'" class="'+(selected===s.id?'current':'')+'"><i class="dot" '+style(s)+'></i>'+s.name+'</a>').join('')+'</nav>'+gamesNav+'<div class="drawer-footer"><div class="date">'+icon('date')+new Intl.DateTimeFormat('zh-CN',{month:'long',day:'numeric',weekday:'long'}).format(new Date())+'</div>'+themeButton+'</div></aside><div class="mainwrap"><main id="main" tabindex="-1">'+content+'</main></div>';
 const drawer = document.getElementById('study-nav');
 drawer.addEventListener('click', event => {
   if (event.target.closest('a')) drawer.hidePopover();
 });
 document.title=crumb+' · 知序';
}
let group='全部',query='';
function home(){
 app.classList.add('home-view');
 const {due,fresh}=loadQueue();
 shell('<section class="hero"><div class="heroText"><div class="kicker"><i></i>工程公共基础</div><h1>工程基础学习手册</h1><p>按学科查阅知识，按记忆节奏复习。</p><a class="btn" href="#review">'+icon('cards')+'开始记忆复习</a><span class="inline-count">'+(due.length?due.length+' 张卡片待复习':fresh.length?fresh.length+' 张新卡待学习':'今日复习已完成')+'</span></div></section><div class="sectionHead"><div><h2>学科目录</h2><p>'+subjects.length+' 门学科 · '+docs.length+' 份学习资料</p></div><label class="search">'+icon('search')+'<input type="search" aria-label="搜索学科或章节" placeholder="搜索学科或章节" value="'+escapeHtml(query)+'"></label></div><div class="tabs" aria-label="学科分类"></div><div id="subjects" class="cards"></div>','home','学科总览');
 app.querySelector('input').oninput=e=>{query=e.target.value;subjectGrid()};
 subjectGrid();
}
function subjectGrid(){
 const groups=['全部',...new Set(subjects.map(s=>s.group))];
 app.querySelector('.tabs').innerHTML=groups.map(g=>'<button class="tab '+(group===g?'on':'')+'" aria-pressed="'+(group===g)+'">'+g+'</button>').join('');
 app.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{group=b.textContent;subjectGrid()});
 const q=query.trim().toLowerCase();
 const items=subjects.filter(s=>(group==='全部'||group===s.group)&&[s.name,s.summary,s.group,...docs.filter(d=>d.subject===s.id).map(d=>d.source+' '+d.title), ...courseLessons(s.id).map(l=>l.chapter+l.title)].join(' ').toLowerCase().includes(q));
 document.querySelector('#subjects').innerHTML=items.length?items.map(s=>'<a class="subject" '+style(s)+' href="'+subjectUrl(s.id)+'"><div class="subjectHead">'+tile(s)+'<span class="cat">'+s.group+'</span></div><h3>'+s.name+'</h3><p>'+s.summary+'</p><div class="meta"><span>'+icon('book')+(curriculum.subjects[s.id]||[]).length+' 章</span><span>'+icon('cards')+cards.filter(c=>c.subject===s.id).length+' 张 · 已复习 '+cards.filter(c=>c.subject===s.id&&schedule(c)).length+' 张</span>'+icon('chev','chev')+'</div></a>').join(''):'<p class="empty">没有匹配的学科或资料，请换个关键词。</p>';
}
function courseLessons(subjectId) {
  return (curriculum.subjects[subjectId] || []).flatMap((chapter, ci) =>
    chapter.lessons.map((lesson, li) => ({...lesson, chapter: chapter.title, number: (ci+1)+'.'+(li+1)})));
}
function lessonUrl(id, anchor='') {
  return '#lesson/' + encodeURIComponent(id) + (anchor ? '/' + encodeURIComponent(anchor) : '');
}
function lastLesson(subjectId) {
  const recent = saved('lesson.' + subjectId);
  if (recent && lessonsById.get(recent)?.subject === subjectId) return recent;
  for (const [id, doc] of Object.entries(curriculum.documents)) {
    if (doc.subject !== subjectId) continue;
    const old = saved('read.' + id);
    if (Number.isInteger(old) && doc.links[old]) return doc.links[old][0];
  }
  return null;
}
function subject(s) {
  const chapters = curriculum.subjects[s.id] || [];
  const lessons = courseLessons(s.id);
  const resumeId = lastLesson(s.id);
  const deck = cards.filter(card=>card.subject===s.id);
  const outline = chapters.map((chapter, ci) => {
    const links = chapter.lessons.map((lesson, li) => `
      <a class="lesson-link" href="${lessonUrl(lesson.id)}">
        <span class="section-number">${ci+1}.${li+1}</span>
        <span>${escapeHtml(lesson.title)}</span>${icon('chev','chev')}
      </a>`).join('');
    const open = resumeId ? chapter.lessons.some(l=>l.id===resumeId) : ci===0;
    return `<details class="chapter-group" ${open?'open':''}>
      <summary><span class="chapter-number">第 ${ci+1} 章</span><strong>${escapeHtml(chapter.title)}</strong>
        <small>${chapter.lessons.length} 节</small>${icon('chev','chev')}</summary>
      <div class="chapter-links"><a class="chapter-review" href="${reviewUrl(s.id, ci+1)}">${icon('cards')}复习本章</a>${links}</div></details>`;
  }).join('');
  shell(`<a class="back" href="#home">${icon('left')}学科目录</a>
    <div class="pageHeading"><h1>${s.name}</h1>
    <div class="actions"><a class="btn" href="#review/${s.id}">${icon('cards')}复习本学科</a>
      ${lessons.length ? '<a class="btn blue" href="'+lessonUrl(resumeId || lessons[0].id)+'">'+(resumeId?'继续学习':'开始学习')+'</a>' : ''}
    </div></div>
    <div class="sectionHead"><div><h2>章节目录</h2><p>${chapters.length} 章 · ${lessons.length} 节 · 共 ${deck.length} 张卡片 · 已复习 ${deck.filter(schedule).length} 张</p></div></div>
    <label class="search fullSearch">${icon('search')}<input id="topic" type="search" aria-label="搜索本学科章节和正文" placeholder="搜索章节或知识点"></label>
    <div id="hits" aria-live="polite"></div>
    <div class="chapter-list">${outline}</div>`, 'home', s.name, s.id);
  const results = app.querySelector('#hits');
  const list = app.querySelector('.chapter-list');
  app.querySelector('#topic').oninput = e => {
    const term = e.target.value.trim().toLowerCase().replace(/\s/g,'');
    list.hidden = !!term;
    if (!term) { results.replaceChildren(); return; }
    const hits = [];
    for (const lesson of lessons) {
      const titleMatch = (lesson.chapter+lesson.title).toLowerCase().replace(/\s/g,'').includes(term);
      const match = lesson.parts.find(part=>part.text.toLowerCase().replace(/\s/g,'').includes(term));
      if (!titleMatch && !match) continue;
      const text = match?.text.replace(/\s/g,'') || '';
      const i = text.toLowerCase().indexOf(term);
      const excerpt = match ? text.slice(Math.max(0,i-16),i+term.length+45) : lesson.chapter;
      hits.push(`<a class="doc" href="${lessonUrl(lesson.id,titleMatch?'':match.anchor)}">${icon('book')}
      <span><b>${lesson.number}　${escapeHtml(lesson.title)}</b><small>${escapeHtml(excerpt)}</small></span>${icon('chev','chev')}</a>`);
    }
    results.innerHTML = hits.length ? '<p class="hint">找到 '+hits.length+' 个小节</p><div class="docList">'+hits.join('')+'</div>' :
      '<p class="hint">未找到匹配的小节，请试试更短的关键词。</p>';
  };
}

function reader(lesson, anchor) {
  const s = bySubject(lesson.subject);
  const chapters = curriculum.subjects[s.id];
  const lessons = courseLessons(s.id);
  const pos = lessons.findIndex(l=>l.id===lesson.id);
  save('lesson.'+s.id,lesson.id);
  const options = chapters.map((ch, i)=>`<optgroup label="第 ${i+1} 章　${escapeHtml(ch.title)}">`+
    ch.lessons.map((l, j)=>`<option value="${l.id}" ${l.id===lesson.id?'selected':''}>${i+1}.${j+1}　${escapeHtml(l.title)}</option>`).join('')+'</optgroup>').join('');
  const nav = (item, label) => item ? `<a class="btn" href="${lessonUrl(item.id)}">${label}</a>` :
    `<button class="btn" disabled>${label}</button>`;
  shell(`<a class="back" href="${subjectUrl(s.id)}">${icon('left')}${s.name} · 章节目录</a>
    <div class="pageHeading"><h1>${lesson.number}　${escapeHtml(lesson.title)}</h1><div class="actions"><a class="btn" href="${reviewUrl(s.id,lesson.number.split('.')[0],lesson.id)}">${icon('cards')}复习本节</a></div></div>
    <nav class="readerTools" aria-label="小节导航"><div class="actions">
      ${nav(lessons[pos-1],'上一节')}<select class="selector" aria-label="选择章节">${options}</select>
      ${nav(lessons[pos+1],'下一节')}</div></nav>
    <article class="reading-shell"><div class="study-text" id="reading-content" aria-busy="true"></div></article>
    <div class="lesson-end">${lessons[pos+1]?'<a class="btn" href="'+lessonUrl(lessons[pos+1].id)+'">下一节　'+escapeHtml(lessons[pos+1].title)+'</a>':
      '<a class="btn" href="'+subjectUrl(s.id)+'">返回章节目录</a>'}</div>`, 'home', s.name, s.id);
  app.querySelector('select').onchange = e=>location.hash=lessonUrl(e.target.value);
  const targetAnchor = lesson.parts.some(part=>part.anchor===anchor) ? anchor : '';
  loadLesson(lesson, targetAnchor, app.querySelector('#reading-content'));
}
async function loadLesson(lesson, anchor, target) {
  const src = 'library/lessons/' + lesson.id + '.html';
  if (location.protocol === 'file:') {
    const frame = document.createElement('iframe');
    frame.className = 'reading-local';
    frame.title = lesson.title;
    frame.src = src + (anchor ? '#' + anchor : '');
    target.replaceChildren(frame);
    target.setAttribute('aria-busy', 'false');
    return;
  }
  target.innerHTML = '<p class="reading-status">正在载入正文…</p>';
  try {
    const response = await fetch(src);
    if (!response.ok) throw new Error(String(response.status));
    const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
    const article = parsed.querySelector('[data-reading-page]');
    if (!article?.textContent.trim()) throw new Error('Empty lesson');
    if (target.isConnected) {
      target.replaceChildren(...article.childNodes);
      if (anchor && anchor !== 'part-1') target.querySelector('#'+anchor)?.scrollIntoView({block:'start'});
    }
  } catch {
    if (target.isConnected) {
      target.innerHTML = '<p class="reading-status">正文未能载入。</p><button class="btn">重新载入</button>';
      target.querySelector('button').onclick = ()=>loadLesson(lesson,anchor,target);
    }
  } finally {
    target.setAttribute('aria-busy','false');
  }
}
function route(){app.classList.remove('home-view','course-view');clearTimeout(timer);active=null;revealed=false;const [path,queryString]=location.hash.slice(1).split('?');let parts;try{parts=path.split('/').map(decodeURIComponent)}catch{parts=[]}
 const [page,id,detail]=parts;
 if(page==='subject' && bySubject(id)) subject(bySubject(id));
 else if(page==='lesson' && lessonsById.has(id)) reader(lessonsById.get(id),detail);
 else if(page==='read' && Object.hasOwn(curriculum.documents,id)) {
   const doc=curriculum.documents[id];
   const index=Math.max(0,Math.min(doc.links.length-1,parseInt(detail,10)||0));
   const link=doc.links[index];
   location.replace(link ? lessonUrl(...link) : subjectUrl(doc.subject));
   return;
 } else if(page==='review') review(id,detail,parts[3],new URLSearchParams(queryString).get('type')==='formula');
 else home();
 window.scrollTo(0,0);
}
document.querySelector('.skip').addEventListener('click',event=>{
 event.preventDefault();
 document.querySelector('main')?.focus();
});
window.addEventListener('hashchange',route);
window.addEventListener('storage',e=>{if(e.key?.startsWith('zhixu.review.')&&location.hash.startsWith('#review'))route()});
route();
