/* 答题页：渲染题目、判分、翻页、答题卡、交卷 */
(function () {
  'use strict';

  var session = null;
  var settings = null;
  var timerId = null;
  var gradedThisSession = 0;
  var correctThisSession = 0;

  var el = {};

  function $(id) { return document.getElementById(id); }

  function cacheEls() {
    ['barTitle', 'posText', 'accText', 'timerText', 'bar', 'qcard', 'qmeta', 'stem',
      'options', 'feedback', 'qfoot', 'prevBtn', 'nextBtn', 'submitBtn', 'sheet',
      'gridNums', 'favBtn', 'sheetBtn', 'finishBtn', 'closeSheet', 'quizWrap',
      'resultWrap', 'scoreNum', 'scoreText', 'rRight', 'rWrong', 'rTime',
      'againWrong', 'againAll', 'goHome', 'wrongList', 'backBtn'
    ].forEach(function (id) { el[id] = $(id); });
  }

  /* ---------------------------------------------------------------- 会话 */
  function parseFilters() {
    function list(name, fallback) {
      var v = UI.qs(name);
      if (!v) return fallback;
      return v.split(',').filter(Boolean);
    }
    var levels = list('lv', [3, 4]).map(Number).filter(function (n) { return n === 3 || n === 4; });
    var types = list('type', ['judge', 'single', 'multi']).filter(function (t) {
      return ['judge', 'single', 'multi'].indexOf(t) >= 0;
    });
    var count = parseInt(UI.qs('count') || '0', 10) || 0;
    return {
      levels: levels.length ? levels : [3, 4],
      types: types.length ? types : ['judge', 'single', 'multi'],
      mode: UI.qs('mode') || 'order',
      count: count
    };
  }

  function newSession(filters) {
    var ids = Bank.build(filters);
    if (!ids.length) return null;
    return {
      ids: ids,
      idx: 0,
      picks: {},
      graded: {},
      optOrder: {},
      mode: filters.mode,
      filters: { levels: filters.levels, types: filters.types },
      startedAt: Date.now(),
      finished: false
    };
  }

  function curQ() {
    return Bank.byId(session.ids[session.idx]);
  }

  function picked(qid) {
    return session.picks[qid] ? session.picks[qid] : null;
  }

  /* 是否已经判分（多选题选中但没提交不算） */
  function isGraded(qid) {
    return !!(session.graded && session.graded[qid]);
  }

  function displayOptions(q) {
    var list = UI.optionList(q);
    if (!settings.shuffleOpts) return list;
    var order = session.optOrder[q.id];
    if (!order) {
      order = UI.shuffle(list.map(function (o) { return o.key; }));
      session.optOrder[q.id] = order;
    }
    return order.map(function (k) {
      return list.filter(function (o) { return o.key === k; })[0];
    });
  }

  /* ---------------------------------------------------------------- 渲染 */
  function render() {
    var q = curQ();
    if (!q) { finish(); return; }

    var src = UI.srcInfo(q.src);
    el.qmeta.innerHTML =
      '<span class="tag lv' + q.lv + '">' + (q.lv === 3 ? '三级' : '四级') + '</span>' +
      '<span class="tag">' + UI.typeLabel(q.type) + '</span>' +
      (q.tag ? '<span class="tag">' + UI.esc(q.tag) + '</span>' : '') +
      '<span class="tag ' + src.cls + '">' + src.label + '</span>';

    el.stem.textContent = q.stem;
    el.posText.textContent = '第 ' + (session.idx + 1) + ' / ' + session.ids.length + ' 题';
    el.bar.style.width = (((session.idx + 1) / session.ids.length) * 100).toFixed(1) + '%';

    var answer = picked(q.id) || (q.type === 'multi' ? [] : null);
    var answered = isGraded(q.id);

    el.options.innerHTML = '';
    displayOptions(q).forEach(function (o) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'opt';
      b.dataset.key = o.key;
      b.innerHTML = '<span class="key">' + UI.esc(o.key) + '</span><span class="txt">' + UI.esc(o.text) + '</span>';

      var chosen = answer && answer.indexOf(o.key) >= 0;
      if (chosen) b.classList.add('chosen');

      if (answered) {
        b.classList.add('locked');
        var inAns = q.type === 'judge' ? (q.ans === o.key) : q.ans.indexOf(o.key) >= 0;
        if (inAns) b.classList.add('correct');
        else if (chosen) b.classList.add('wrong');
      } else {
        b.addEventListener('click', function () { onPick(q, o.key); });
      }
      el.options.appendChild(b);
    });

    renderFeedback(q, answered);
    renderFoot(q, answered);
    renderFav(q);
    renderAcc();
  }

  function renderFav(q) {
    var on = Store.isFav(q.id);
    el.favBtn.textContent = on ? '★' : '☆';
    el.favBtn.title = on ? '取消收藏' : '收藏本题';
  }

  function renderAcc() {
    el.accText.textContent = gradedThisSession
      ? '本次正确率 ' + Math.round((correctThisSession / gradedThisSession) * 100) + '%'
      : '';
  }

  function renderFoot(q, answered) {
    var last = session.idx >= session.ids.length - 1;
    el.prevBtn.disabled = session.idx === 0;
    el.nextBtn.textContent = last ? '交卷' : '下一题';

    // 还有没判分的作答时才显示"提交"
    var canSubmit = !answered && !!picked(q.id);
    el.submitBtn.hidden = !canSubmit;
  }

  function renderFeedback(q, answered) {
    if (!answered) { el.feedback.innerHTML = ''; return; }

    var pick = picked(q.id) || [];
    var ok = UI.isCorrect(q, pick);
    var src = UI.srcInfo(q.src);

    var html = '<div class="feedback ' + (ok ? 'ok' : 'bad') + '">';
    html += '<div class="verdict ' + (ok ? 'ok' : 'bad') + '">' + (ok ? '回答正确' : '回答错误') + '</div>';
    html += '<div class="ansline">正确答案：<b>' + UI.esc(UI.answerText(q)) + '</b>' +
      (ok ? '' : '　你的答案：<b>' + UI.esc(pick.join('') || '未作答') + '</b>') + '</div>';
    if (settings.showExp && q.exp) {
      html += '<div class="exp">' + UI.esc(q.exp) + '</div>';
    }
    html += '<div class="srcnote">答案来源：' + src.label + '。' + src.note + '</div>';
    html += '</div>';
    el.feedback.innerHTML = html;
  }

  /* ---------------------------------------------------------------- 作答 */
  function onPick(q, key) {
    if (isGraded(q.id)) return;

    if (q.type === 'multi') {
      var now = (session.picks[q.id] || []).slice();
      var i = now.indexOf(key);
      if (i >= 0) now.splice(i, 1); else now.push(key);
      now.sort();
      session.picks[q.id] = now.length ? now : null;
      if (!now.length) delete session.picks[q.id];
      Store.saveSession(session);
      render();
      return;
    }

    if (!settings.instant) {
      session.picks[q.id] = [key];
      Store.saveSession(session);
      render();
      return;
    }
    grade(q, [key]);
  }

  function submit() {
    var q = curQ();
    var pick = picked(q.id);
    if (!pick || !pick.length) { UI.toast('请先选择答案'); return; }
    grade(q, pick);
  }

  function grade(q, pick) {
    session.picks[q.id] = pick.slice().sort();
    session.graded[q.id] = true;
    var ok = UI.isCorrect(q, pick);
    Store.record(q.id, ok);
    gradedThisSession += 1;
    if (ok) correctThisSession += 1;
    Store.saveSession(session);
    render();
    renderGrid();
  }

  /* ---------------------------------------------------------------- 导航 */
  function go(delta) {
    var next = session.idx + delta;
    if (next < 0) return;
    if (next >= session.ids.length) { finish(); return; }
    session.idx = next;
    Store.saveSession(session);
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function jump(i) {
    session.idx = i;
    Store.saveSession(session);
    closeSheet();
    render();
    window.scrollTo({ top: 0 });
  }

  function renderGrid() {
    el.gridNums.innerHTML = '';
    session.ids.forEach(function (id, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = i + 1;
      var q = Bank.byId(id);
      var p = session.picks[id];
      if (p && isGraded(id)) b.classList.add(UI.isCorrect(q, p) ? 'ok' : 'bad');
      else if (p) b.classList.add('done');
      if (i === session.idx) b.classList.add('cur');
      b.addEventListener('click', function () { jump(i); });
      el.gridNums.appendChild(b);
    });
  }

  function openSheet() { renderGrid(); el.sheet.classList.add('open'); }
  function closeSheet() { el.sheet.classList.remove('open'); }

  /* ---------------------------------------------------------------- 结束 */
  function finish() {
    session.finished = true;
    Store.saveSession(session);
    clearInterval(timerId);

    var total = session.ids.length;
    var done = 0, right = 0, wrongs = [];
    session.ids.forEach(function (id) {
      var p = session.picks[id];
      if (!p || !isGraded(id)) return;
      done += 1;
      var q = Bank.byId(id);
      if (UI.isCorrect(q, p)) right += 1;
      else wrongs.push(q);
    });

    var rate = done ? Math.round((right / done) * 100) : 0;
    el.quizWrap.hidden = true;
    el.qfoot.hidden = true;
    el.resultWrap.hidden = false;
    el.scoreNum.textContent = rate + '%';
    el.scoreNum.className = 'score ' + (rate >= 60 ? 'ok' : 'bad');
    el.scoreText.textContent = '共 ' + total + ' 题，作答 ' + done + ' 题，答对 ' + right + ' 题，答错 ' + (done - right) + ' 题。';
    el.rRight.textContent = right;
    el.rWrong.textContent = done - right;
    el.rTime.textContent = UI.fmtTime(Date.now() - session.startedAt);

    el.wrongList.innerHTML = '';
    if (!wrongs.length) {
      el.wrongList.innerHTML = '<div class="empty">本次没有错题，厉害。</div>';
    } else {
      wrongs.forEach(function (q) {
        var d = document.createElement('div');
        d.className = 'list-item';
        d.innerHTML = '<div class="lt">' + UI.esc(q.stem) + '</div>' +
          '<div class="lm"><span class="tag lv' + q.lv + '">' + (q.lv === 3 ? '三级' : '四级') + '</span>' +
          '<span>' + UI.typeLabel(q.type) + '</span>' +
          '<span>正确答案 <b>' + UI.esc(UI.answerText(q)) + '</b></span></div>';
        el.wrongList.appendChild(d);
      });
    }

    el.againWrong.onclick = function () {
      var ids = wrongs.map(function (q) { return q.id; });
      if (!ids.length) { UI.toast('本次没有错题'); return; }
      session = {
        ids: ids, idx: 0, picks: {}, graded: {}, optOrder: {}, mode: 'wrong',
        filters: session.filters, startedAt: Date.now(), finished: false
      };
      Store.saveSession(session);
      restartView();
    };

    el.againAll.onclick = function () {
      session = {
        ids: session.ids.slice(), idx: 0, picks: {}, graded: {}, optOrder: {}, mode: session.mode,
        filters: session.filters, startedAt: Date.now(), finished: false
      };
      Store.saveSession(session);
      restartView();
    };
  }

  function restartView() {
    gradedThisSession = 0; correctThisSession = 0;
    el.resultWrap.hidden = true;
    el.quizWrap.hidden = false;
    el.qfoot.hidden = false;
    render();
    startTimer();
    window.scrollTo({ top: 0 });
  }

  /* ---------------------------------------------------------------- 计时 */
  function startTimer() {
    clearInterval(timerId);
    function tick() {
      if (!session || session.finished) return;
      el.timerText.textContent = UI.fmtTime(Date.now() - session.startedAt);
    }
    tick();
    timerId = setInterval(tick, 1000);
  }

  /* ---------------------------------------------------------------- 事件 */
  function bind() {
    el.prevBtn.addEventListener('click', function () { go(-1); });
    el.nextBtn.addEventListener('click', function () {
      var q = curQ();
      // 有选择但还没判分，先判分再翻页（等价于"选完立即判分"）
      if (q && !isGraded(q.id) && picked(q.id)) grade(q, picked(q.id));
      if (session.idx >= session.ids.length - 1) { finish(); return; }
      go(1);
    });
    el.submitBtn.addEventListener('click', submit);

    el.favBtn.addEventListener('click', function () {
      var q = curQ();
      var on = Store.toggleFav(q.id);
      renderFav(q);
      UI.toast(on ? '已收藏' : '已取消收藏');
    });

    el.sheetBtn.addEventListener('click', openSheet);
    el.closeSheet.addEventListener('click', closeSheet);
    el.sheet.addEventListener('click', function (e) { if (e.target === el.sheet) closeSheet(); });
    el.finishBtn.addEventListener('click', function () { closeSheet(); finish(); });
    el.backBtn.addEventListener('click', function () { location.href = 'index.html'; });
    el.goHome.addEventListener('click', function () { location.href = 'index.html'; });

    document.addEventListener('keydown', function (e) {
      if (el.resultWrap && !el.resultWrap.hidden) return;
      if (e.target && /input|textarea/i.test(e.target.tagName)) return;
      var q = curQ();
      if (!q) return;
      var opts = displayOptions(q);
      var num = parseInt(e.key, 10);
      if (num >= 1 && num <= opts.length) {
        onPick(q, opts[num - 1].key);
        e.preventDefault();
        return;
      }
      var letter = e.key.toUpperCase();
      if (/^[A-E]$/.test(letter) && q.type !== 'judge' && opts.some(function (o) { return o.key === letter; })) {
        onPick(q, letter);
        e.preventDefault();
        return;
      }
      if (e.key === 'Enter') {
        if (!el.submitBtn.hidden) submit();
        else el.nextBtn.click();
        e.preventDefault();
      } else if (e.key === 'ArrowRight') { go(1); }
      else if (e.key === 'ArrowLeft') { go(-1); }
    });
  }

  /* ---------------------------------------------------------------- 启动 */
  function boot() {
    if (window.__practiceBooted) return;
    window.__practiceBooted = true;
    cacheEls();
    UI.applyTheme();
    UI.bindThemeToggle();
    settings = Store.settings();

    Bank.load().then(function () {
      var wantNew = UI.qs('mode') || UI.qs('type') || UI.qs('lv') || UI.qs('count');
      var saved = Store.session();
      if (!wantNew && !UI.qs('resume') && saved && !saved.finished) {
        session = saved;
      } else if (UI.qs('resume') && saved && !saved.finished) {
        session = saved;
      } else {
        session = newSession(parseFilters());
      }

      if (!session || !session.ids || !session.ids.length) {
        UI.toast('没有可练习的题目');
        setTimeout(function () { location.href = 'index.html'; }, 1200);
        return;
      }
      // 清掉已删除题目的 id
      session.ids = session.ids.filter(function (id) { return !!Bank.byId(id); });
      if (!session.ids.length) { location.href = 'index.html'; return; }
      if (!session.graded) session.graded = {};
      if (session.idx >= session.ids.length) session.idx = session.ids.length - 1;

      el.barTitle.textContent = modeTitle(session);
      bind();
      render();
      startTimer();
    }).catch(function (err) {
      UI.toast(err.message);
      el.stem.textContent = '题库加载失败：' + err.message;
    });
  }

  function modeTitle(s) {
    var names = {
      order: '顺序练习', random: '随机练习', weak: '智能优先',
      unseen: '只刷没做过的', wrong: '错题重刷', fav: '收藏重刷'
    };
    var lv = (s.filters && s.filters.levels && s.filters.levels.length === 1)
      ? (s.filters.levels[0] === 3 ? '三级' : '四级') : '三/四级';
    return (names[s.mode] || '刷题') + ' · ' + lv;
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
