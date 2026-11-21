let active = null;
let revealed = false;
let timer = 0;

function reviewUrl(subject = '', chapter = '', lesson = '', formulaOnly = false) {
  return '#' + ['review', subject, chapter, lesson].filter(Boolean).map(encodeURIComponent).join('/') + (formulaOnly ? '?type=formula' : '');
}

function cardContent(text) {
  // Keep short Unicode equations intact when the surrounding Chinese prose wraps.
  const chunks = text.split(/([a-zA-Z0-9\u0370-\u03ff\u2070-\u209f ()[\],.°′″⁰¹²³⁴⁵⁶⁷⁸⁹ˣ+×·÷/=<>−≥≤≠≈√∫∑→^_-]+)/u);
  return chunks.map((chunk,i) => i % 2 && /[=≥≤≠≈∫∑→]/u.test(chunk)
    ? '<span class="card-formula">' + escapeHtml(chunk.trim()) + '</span>'
    : escapeHtml(chunk)).join('');
}

function reviewMoment(timestamp) {
  return new Intl.DateTimeFormat('zh-CN', {month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit'}).format(timestamp);
}

function curvePanel(scope, states, current) {
  let latest;
  for (const candidate of scope) {
    const stamp = states.get(candidate.id)?.history?.at(-1)?.at;
    if (stamp && (!latest || stamp > states.get(latest.id).history.at(-1).at)) latest = candidate;
  }
  const card = current && states.get(current.id)?.history?.length ? current : latest;
  const history = card ? states.get(card.id).history.slice(-4) :
    [{at:0, span:day}, {at:day, span:2*day}, {at:3*day, span:4*day}];
  const first = history[0].at;
  const last = history.at(-1);
  const end = last.at + last.span;
  const x = time => 64 + 506 * (time - first) / Math.max(1,end - first);
  const y = retention => 20 + 100 * (1-retention);
  const points = [];
  const dots = [];
  history.forEach((event,i) => {
    const until = history[i+1]?.at ?? end;
    for (let k=0;k<=32;k++) {
      const t = event.at + (until-event.at)*k/32;
      const retention = Math.pow(.8, (t-event.at)/Math.max(1,event.span));
      points.push(x(t).toFixed(2)+','+y(retention).toFixed(2));
    }
    dots.push(`<circle cx="${x(event.at)}" cy="20" r="4"><title>${card?reviewMoment(event.at):'第 '+event.at/day+' 天'} · 复习</title></circle>`);
  });
  const title = card ? '最近复习 · '+(card.questionHtml || escapeHtml(card.q)) : '连续记住三次的示例';
  return `<section class="panel curve-panel"><h2>记忆曲线</h2><p class="curve-title">${title}</p>
    <svg viewBox="0 0 600 150" role="img" aria-label="预计记忆保持率随时间下降，每次复习后重新起算">
      <g class="curve-axis"><path d="M64 20H570 M64 40H570 M64 120H570"/><text x="54" y="24">100%</text><text x="54" y="45">80%</text><text x="54" y="124">0%</text></g>
      <polyline class="retention" points="${points.join(' ')}"/><g class="curve-dots">${dots.join('')}</g>
      <text x="64" y="144">${card?reviewMoment(first):'第 0 天'}</text>
      <text x="570" y="144" text-anchor="end">${card?reviewMoment(end):'第 7 天'}</text>
    </svg><p class="subtext">${card?'圆点表示这张卡的复习记录，右端为计划复习时间。':'评分后，这里会显示卡片的复习记录。'}曲线按计划间隔估算保持率，实际掌握程度以回忆结果为准。</p></section>`;
}

function review(id = '', chapter = '', lessonId = '', formulaOnly = false) {
  if (!bySubject(id)) id = '';
  const chapters = curriculum.subjects[id] || [];
  const chapterIndex = Number(chapter)-1;
  const selectedChapter = chapters[chapterIndex];
  if (!selectedChapter) chapter = '';
  if (!selectedChapter?.lessons.some(l => l.id === lessonId)) lessonId = '';
  const allowed = selectedChapter && new Set(selectedChapter.lessons.map(l=>l.id));
  const isFormulaCard = c => c.kind === 'formula' || [c.questionHtml, c.answerHtml].some(html => html?.includes('<math'));
  const scope = cards.filter(c=>(!formulaOnly||isFormulaCard(c))&&(!id||c.subject===id)&&(!allowed||allowed.has(c.lesson))&&(!lessonId||c.lesson===lessonId));
  const states = new Map(cards.map(c => [c.id,schedule(c)]));
  const now = Date.now();
  const fresh = scope.filter(c=>!states.get(c.id));
  const due = scope.filter(c=>states.get(c.id)?.due<=now).sort((a,b)=>states.get(a.id).due-states.get(b.id).due);
  const queue = [...due,...fresh];
  const card = queue.find(c=>c.id===active)||queue[0];
  if (card?.id!==active) revealed = false;
  active = card?.id || null;
  const next = Math.min(...scope.map(c=>states.get(c.id)?.due).filter(t=>t>now));
  const option = (value,label,selected) => `<option value="${escapeHtml(value)}" ${selected?'selected':''}>${escapeHtml(label)}</option>`;
  const filters = `<div class="review-filters">
    <label>学科<select id="review-subject" class="selector">${option('','全部学科',!id)}${subjects.map(s=>option(s.id,s.name,s.id===id)).join('')}</select></label>
    <label>章<select id="review-chapter" class="selector" ${id?'':'disabled'}>${option('','全部章节',!chapter)}${chapters.map((ch,i)=>option(i+1,'第 '+(i+1)+' 章　'+ch.title,i===chapterIndex)).join('')}</select></label>
    <label>小节<select id="review-lesson" class="selector" ${selectedChapter?'':'disabled'}>${option('','全部小节',!lessonId)}${(selectedChapter?.lessons||[]).map((l,i)=>option(l.id,chapter+'.'+(i+1)+'　'+l.title,l.id===lessonId)).join('')}</select></label>
    <label>卡片类型<select id="review-type" class="selector">${option('all','全部卡片',!formulaOnly)}${option('formula','公式与矩阵',formulaOnly)}</select></label></div>`;
  let body = '';
  if (card) {
    const lesson = lessonsById.get(card.lesson);
    const subject = bySubject(card.subject);
    const state = states.get(card.id);
    const step = Math.min((state?.stage??-1)+1,intervals.length-1);
    const link = curriculum.cards[card.id] || [card.lesson];
    body = `<div class="row">${tile(subject)}<b>${subject.name}</b><span class="count">${state?'到期复习':'新卡学习'}</span></div>
      <p class="card-origin">第 ${lesson.number.split('.')[0]} 章 · ${escapeHtml(lesson.chapter)}<br>${lesson.number}　${escapeHtml(lesson.title)}</p>
      <h2>${card.questionHtml || cardContent(card.q)}</h2>${revealed?`<div class="answer">${card.answerHtml || cardContent(card.a)}</div>
      <a class="back" href="${lessonUrl(...link)}">${icon('book')}查看对应小节</a>
      <div class="actions"><button class="btn" data-grade="again">忘记了 · 10 分钟</button><button class="btn" data-grade="hard">模糊 · 1 天</button><button class="btn blue" data-grade="good">记住了 · ${intervals[step]} 天</button></div>`:'<button class="btn blue" id="flip">查看答案</button>'}`;
  } else {
    body = '<h2>'+(scope.length?'本轮复习已完成':'当前范围没有卡片')+'</h2><p class="hint">'+(Number.isFinite(next)?'下次复习时间为 '+reviewMoment(next)+'。':'可展开复习范围，选择其他章节或卡片类型。')+'</p>';
  }
  const stats = subjects.map(s=>{
    const deck=cards.filter(c=>c.subject===s.id);
    const seen=deck.filter(c=>states.get(c.id)).length;
    return `<a href="${reviewUrl(s.id)}" class="review-subject-stat"><span>${s.name}</span><strong>已复习 ${seen} / 共 ${deck.length} 张</strong><progress value="${seen}" max="${deck.length||1}"></progress></a>`;
  }).join('');
  const rangeOpen = app.querySelector('.review-range')?.open;
  const reportOpen = app.querySelector('.review-report')?.open;
  const exit = lessonId ? lessonUrl(lessonId) : id ? subjectUrl(id) : '#home';
  const rangeName = lessonsById.get(lessonId)?.title || selectedChapter?.title || bySubject(id)?.name || '全部学科';
  const reviewed = scope.length - fresh.length;
  document.title = '记忆复习 · 知序';
  app.innerHTML = `<main id="main" tabindex="-1" class="focus-room">
    <div class="focus-frame"><header class="focus-header"><h1>${icon('cards')}记忆复习</h1>
      ${themeButton}<a href="${exit}" class="focus-exit">${icon('left')}退出复习</a></header>
    <div class="focus-stage"><details class="review-range" ${rangeOpen?'open':''}><summary>复习范围<span>${escapeHtml(rangeName)}${formulaOnly?' · 公式与矩阵':''}</span></summary>${filters}</details>
    <section class="reviewCard focus-card" aria-label="当前记忆卡">
      <div class="focus-meter"><p class="review-counts">共 ${scope.length} 张　已复习 ${reviewed} 张　到期 ${due.length} 张　新卡 ${fresh.length} 张</p>
      <progress max="${scope.length||1}" value="${reviewed}" aria-label="当前范围已复习卡片"></progress></div>${body}</section>
    <details class="review-report" ${reportOpen?'open':''}><summary>记忆曲线与学科进度</summary>
      ${curvePanel(scope,states,card)}<section class="panel progress-panel"><h2>各学科复习进度</h2><div class="review-subject-list">${stats}</div></section></details></div>
    </div></main>`;
  app.querySelector('#review-subject').onchange=e=>location.hash=reviewUrl(e.target.value,'','',formulaOnly);
  app.querySelector('#review-chapter').onchange=e=>location.hash=reviewUrl(id,e.target.value,'',formulaOnly);
  app.querySelector('#review-lesson').onchange=e=>location.hash=reviewUrl(id,chapter,e.target.value,formulaOnly);
  app.querySelector('#review-type').onchange=e=>location.hash=reviewUrl(id,chapter,lessonId,e.target.value==='formula');
  const redraw = () => review(id,chapter,lessonId,formulaOnly);
  const flip = app.querySelector('#flip');
  if (flip) flip.onclick=()=>{
    revealed=true;redraw();
    const answer=app.querySelector('.answer');
    answer.tabIndex=-1;
    answer.focus({preventScroll:true});
    if (answer.getBoundingClientRect().top > innerHeight * .8) answer.scrollIntoView({block:'center'});
  };
  app.querySelectorAll('[data-grade]').forEach(button=>button.onclick=()=>{
    const prev=schedule(card);
    const grade=button.dataset.grade;
    const stage=grade==='good'?Math.min((prev?.stage??-1)+1,intervals.length-1):-1;
    const span=grade==='again'?10*minute:grade==='hard'?day:intervals[stage]*day;
    const at=Date.now();
    if (prev?.due>at) { active=null; revealed=false; redraw(); return; }
    const history=[...(prev?.history||[]),{at,span,grade}].slice(-24);
    save(cardKey(card),{due:at+span,stage,history});
    active=null;revealed=false;redraw();
    const question=app.querySelector('.focus-card h2');
    question.tabIndex=-1;
    question.focus();
  });
  clearTimeout(timer);
  if(Number.isFinite(next)) timer=setTimeout(redraw,Math.min(next-now+50,2147483647));
}
