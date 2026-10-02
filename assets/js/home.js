/* 首页：筛选条件、题量预览、开始刷题 */
(function () {
  'use strict';

  var TYPES = [
    { key: 'judge', label: '判断题' },
    { key: 'single', label: '单选题' },
    { key: 'multi', label: '多选题' }
  ];
  var COUNTS = [10, 20, 50, 100, 0];

  var state = {
    levels: [3, 4],
    types: ['judge', 'single', 'multi'],
    secs: [],          // 空数组 = 全选
    mode: 'order',
    count: 20
  };

  var meta = null;

  function chip(label, active, extra) {
    var b = document.createElement('button');
    b.className = 'chip';
    b.type = 'button';
    b.setAttribute('aria-pressed', active ? 'true' : 'false');
    b.innerHTML = label + (extra ? ' <small>' + extra + '</small>' : '');
    return b;
  }

  /* 题库分区切换（默认分区仍是原来的等级认定题库） */
  function renderSetChips() {
    var box = document.getElementById('setChips');
    if (!box) return;
    box.innerHTML = '';
    var cur = Bank.setKey();
    Bank.SETS.forEach(function (s) {
      var b = chip(s.title, cur === s.key, s.sub);
      b.addEventListener('click', function () {
        if (Bank.setKey() === s.key) return;
        b.disabled = true;
        Bank.useSet(s.key).then(function () {
          Store.saveSettings({ set: s.key });
          state.secs = [];            // 章节键在不同分区之间不通用，重置即可
          state.mode = 'order';
          meta = Bank.meta();
          renderAll();
          renderStats();
          renderSrcTable();
          renderResume();
          UI.toast('已切换到「' + s.title + '」');
        }).catch(function (e) {
          UI.toast('题库加载失败：' + e.message);
        }).then(function () {
          b.disabled = false;
        });
      });
      box.appendChild(b);
    });
    var hint = document.getElementById('setHint');
    if (hint) {
      var d = Bank.setDef(cur) || Bank.SETS[0];
      hint.textContent = '当前：' + d.title + ' · ' + Bank.all().length + ' 题'
        + (cur === 'ess' ? '（精华模式答题会同时记入精华错题本与全库统计）' : '');
    }
  }

  function renderLevelChips() {
    var box = document.getElementById('levelChips');
    box.innerHTML = '';
    var c = Bank.countBy({ types: state.types });
    [3, 4].forEach(function (lv) {
      var b = chip('人工智能训练师（' + (lv === 3 ? '三级' : '四级') + '）',
        state.levels.indexOf(lv) >= 0, c[lv] + ' 题');
      b.addEventListener('click', function () {
        var i = state.levels.indexOf(lv);
        if (i >= 0) { if (state.levels.length > 1) state.levels.splice(i, 1); }
        else state.levels.push(lv);
        state.levels.sort();
        renderAll();
      });
      box.appendChild(b);
    });
  }

  function renderTypeChips() {
    var box = document.getElementById('typeChips');
    box.innerHTML = '';
    var c = Bank.countBy({ levels: state.levels });
    TYPES.forEach(function (t) {
      var b = chip(t.label, state.types.indexOf(t.key) >= 0, c[t.key] + ' 题');
      b.addEventListener('click', function () {
        var i = state.types.indexOf(t.key);
        if (i >= 0) { if (state.types.length > 1) state.types.splice(i, 1); }
        else state.types.push(t.key);
        renderAll();
      });
      box.appendChild(b);
    });
  }

  function renderModeChips() {
    var box = document.getElementById('modeChips');
    box.innerHTML = '';
    var pool = Bank.countBy(state);
    Bank.MODES.forEach(function (m) {
      var extra = '';
      if (m.key === 'wrong') extra = Store.wrongIds().length + ' 题';
      if (m.key === 'fav') extra = Store.favIds().length + ' 题';
      var b = chip(m.label, state.mode === m.key, m.key === 'order' || m.key === 'random' || m.key === 'weak' || m.key === 'unseen' ? pool.total + ' 题' : extra);
      b.title = m.hint;
      b.addEventListener('click', function () {
        state.mode = m.key;
        renderAll();
      });
      box.appendChild(b);
    });
  }

  /* 章节：按章分组，点章名整章切换 */
  function renderSections() {
    var box = document.getElementById('secGroups');
    box.innerHTML = '';
    var groups = Bank.sectionGroups({ levels: state.levels, types: state.types });
    var allKeys = [];
    groups.forEach(function (g) { g.items.forEach(function (it) { allKeys.push(it.key); }); });

    // 选了新级别后，把已经不存在（或还没选）的章节补进来
    if (!state.secs.length) {
      state.secs = allKeys.slice();
    } else {
      state.secs = state.secs.filter(function (k) { return allKeys.indexOf(k) >= 0; });
      if (!state.secs.length) state.secs = allKeys.slice();
    }

    groups.forEach(function (g) {
      var wrap = document.createElement('div');
      wrap.className = 'sec-group';

      var keys = g.items.map(function (it) { return it.key; });
      var selected = keys.filter(function (k) { return state.secs.indexOf(k) >= 0; });
      var count = g.items.reduce(function (s, it) { return s + it.count; }, 0);

      var head = document.createElement('div');
      head.className = 'sec-head';
      head.innerHTML = '<span>' + UI.esc(g.ch) + '</span>';
      var toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.textContent = selected.length === keys.length ? '取消整章' : '选中整章';
      toggle.addEventListener('click', function () {
        if (selected.length === keys.length) {
          state.secs = state.secs.filter(function (k) { return keys.indexOf(k) < 0; });
        } else {
          keys.forEach(function (k) { if (state.secs.indexOf(k) < 0) state.secs.push(k); });
        }
        renderAll();
      });
      head.appendChild(toggle);
      var c = document.createElement('span');
      c.className = 'sec-count';
      c.textContent = count + ' 题';
      head.appendChild(c);
      wrap.appendChild(head);

      var chips = document.createElement('div');
      chips.className = 'chips';
      g.items.forEach(function (it) {
        var b = chip(it.sec, state.secs.indexOf(it.key) >= 0, it.count + ' 题');
        if (!it.count) b.classList.add('dim');
        b.addEventListener('click', function () {
          var i = state.secs.indexOf(it.key);
          if (i >= 0) {
            if (state.secs.length > 1) state.secs.splice(i, 1);
          } else {
            state.secs.push(it.key);
          }
          renderAll();
        });
        chips.appendChild(b);
      });
      wrap.appendChild(chips);
      box.appendChild(wrap);
    });

    // 折叠状态下也能看出当前选了多少章节
    var stateEl = document.getElementById('secState');
    if (stateEl) {
      stateEl.textContent = state.secs.length >= allKeys.length
        ? '全部章节（' + allKeys.length + ' 节）'
        : '已选 ' + state.secs.length + ' / ' + allKeys.length + ' 节';
    }
  }

  function renderCountChips() {
    var box = document.getElementById('countChips');
    box.innerHTML = '';
    var pool = Bank.build(Object.assign({}, state, { count: 0, mode: state.mode === 'wrong' || state.mode === 'fav' ? state.mode : 'order' })).length;
    COUNTS.forEach(function (n) {
      var label = n === 0 ? '全部' : n + ' 题';
      var b = chip(label, state.count === n, '');
      b.addEventListener('click', function () { state.count = n; renderAll(); });
      box.appendChild(b);
    });
    var hint = document.getElementById('poolHint');
    var actual = state.count === 0 ? pool : Math.min(state.count, pool);
    hint.textContent = pool === 0
      ? '当前条件下没有题目，换个筛选条件试试。'
      : '本次将出 ' + actual + ' 题（可选范围内共 ' + pool + ' 题）。';
  }

  function renderPrefs() {
    var s = Store.settings();
    document.querySelectorAll('#prefChips .chip').forEach(function (b) {
      var k = b.getAttribute('data-pref');
      b.setAttribute('aria-pressed', s[k] ? 'true' : 'false');
    });
  }

  function renderStats() {
    var total = Bank.all().length;
    document.getElementById('totalNum').textContent = total;
    var isEss = Bank.setKey() === 'ess';
    var ids = Bank.all().map(function (q) { return q.id; });
    var sum = isEss ? Store.essSummary(ids, total) : Store.summaryFor(ids, total);
    var title = document.getElementById('setTitle');
    if (title) {
      var d = Bank.setDef() || Bank.SETS[0];
      title.textContent = d.title + (d.key === '' ? '（三级 / 四级）' : '');
    }
    var cells = document.querySelectorAll('#statRow .stat');
    cells[0].innerHTML = '<b>' + sum.answered + '</b><span>已做（' + sum.coverage + '%）</span>';
    cells[1].innerHTML = '<b>' + sum.rate + '%</b><span>正确率</span>';
    cells[2].innerHTML = '<b>' + sum.wrongCount + '</b><span>错题</span>';
    cells[3].innerHTML = '<b>' + sum.favCount + '</b><span>收藏</span>';
    document.getElementById('qWrong').textContent = sum.wrongCount + ' 题';
    document.getElementById('qFav').textContent = sum.favCount + ' 题';
  }

  function renderSrcTable() {
    var counts = (meta && meta.answerSources) || {};
    var order = ['official', 'consensus', 'reviewed', 'gz', 'ww', 'n9', 'ai'];
    var names = {
      official: '官方模拟卷答案',
      consensus: '多来源一致',
      reviewed: '人工复核裁定',
      gz: '第三方题库答案',
      ww: '第三方题库答案',
      n9: '大赛公开题库答案',
      ai: 'AI 生成答案'
    };
    var rows = '';
    var used = {};
    order.forEach(function (k) {
      if (!counts[k]) return;
      var label = names[k] || k;
      if (used[label]) { used[label] += counts[k]; return; }
      used[label] = counts[k];
    });
    Object.keys(used).forEach(function (label) {
      rows += '<tr><td>' + label + '</td><td>' + used[label] + ' 题</td></tr>';
    });
    document.getElementById('srcTable').innerHTML = rows;
  }

  function renderResume() {
    var s = Bank.setKey() === 'ess' ? Store.essSession() : Store.session();
    var card = document.getElementById('resumeCard');
    if (!s || !s.ids || !s.ids.length || s.finished) { card.hidden = true; return; }
    var done = Object.keys(s.picks || {}).length;
    card.hidden = false;
    document.getElementById('resumeHint').textContent =
      '上次练习共 ' + s.ids.length + ' 题，已作答 ' + done + ' 题，进度 ' + (s.idx + 1) + '/' + s.ids.length + '。';
  }

  function renderAll() {
    renderSetChips();
    renderLevelChips();
    renderTypeChips();
    renderSections();
    renderModeChips();
    renderCountChips();
    renderPrefs();
    var pool = Bank.build(Object.assign({}, state, { count: 0 })).length;
    document.getElementById('startBtn').disabled = pool === 0;
    document.getElementById('startBtn').textContent = pool === 0
      ? '当前条件下没有题目'
      : '开始刷题（' + (state.count === 0 ? pool : Math.min(state.count, pool)) + ' 题）';
  }

  function start() {
    var ids = Bank.build(state);
    if (!ids.length) { UI.toast('当前条件下没有题目'); return; }
    var isEss = Bank.setKey() === 'ess';
    var sess = {
      ids: ids,
      idx: 0,
      picks: {},
      mode: state.mode,
      filters: { levels: state.levels, types: state.types },
      set: Bank.setKey(),
      scope: isEss ? 'ess' : '',
      startedAt: Date.now(),
      finished: false
    };
    if (isEss) Store.saveEssSession(sess); else Store.saveSession(sess);
    Store.saveLastFilters(state);
    location.href = 'practice.html';
  }

  function bindPrefs() {
    document.querySelectorAll('#prefChips .chip').forEach(function (b) {
      b.addEventListener('click', function () {
        var k = b.getAttribute('data-pref');
        var s = Store.settings();
        Store.saveSettings({ [k]: !s[k] });
        renderPrefs();
      });
    });
  }

  function bindSections() {
    document.getElementById('secAll').addEventListener('click', function () {
      state.secs = [];
      renderAll();
    });
    document.getElementById('secNone').addEventListener('click', function () {
      // 至少保留一个章节，避免空池
      var groups = Bank.sectionGroups({ levels: state.levels, types: state.types });
      var first = groups[0] && groups[0].items[0];
      state.secs = first ? [first.key] : [];
      renderAll();
    });
  }

  function bindData() {
    document.getElementById('exportBtn').addEventListener('click', function () {
      var blob = new Blob([JSON.stringify(Store.exportAll(), null, 2)], { type: 'application/json' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = '刷题进度备份-' + new Date().toISOString().slice(0, 10) + '.json';
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
      UI.toast('已导出备份文件');
    });

    document.getElementById('importBtn').addEventListener('click', function () {
      document.getElementById('importFile').click();
    });

    document.getElementById('importFile').addEventListener('change', function (e) {
      var f = e.target.files && e.target.files[0];
      if (!f) return;
      var fr = new FileReader();
      fr.onload = function () {
        try {
          Store.importAll(JSON.parse(fr.result));
          UI.toast('导入成功');
          renderStats(); renderAll(); renderResume();
        } catch (err) {
          UI.toast('导入失败：' + err.message);
        }
      };
      fr.readAsText(f);
      e.target.value = '';
    });

    document.getElementById('resetBtn').addEventListener('click', function () {
      if (!confirm('确定要清空全部做题进度、错题本和收藏吗？此操作不可恢复。')) return;
      Store.resetProgress();
      UI.toast('已清空');
      renderStats(); renderAll(); renderResume();
    });

    document.getElementById('resumeBtn').addEventListener('click', function () {
      location.href = 'practice.html?resume=1';
    });
    document.getElementById('dropResumeBtn').addEventListener('click', function () {
      if (Bank.setKey() === 'ess') Store.clearEssSession(); else Store.clearSession();
      renderResume();
      UI.toast('已放弃上次练习');
    });

    document.querySelectorAll('[data-go]').forEach(function (b) {
      b.addEventListener('click', function () { location.href = b.getAttribute('data-go'); });
    });
  }

  function boot() {
    if (window.__homeBooted) return;
    window.__homeBooted = true;
    UI.applyTheme();
    UI.bindThemeToggle();

    Bank.load().then(function (data) {
      meta = data.meta;
      var last = Store.lastFilters();
      if (last) {
        state = Object.assign(state, last);
        if (!state.levels || !state.levels.length) state.levels = [3, 4];
        if (!state.types || !state.types.length) state.types = ['judge', 'single', 'multi'];
      }
      renderStats();
      renderAll();
      renderSrcTable();
      renderResume();
      bindPrefs();
      bindSections();
      bindData();
      document.getElementById('startBtn').addEventListener('click', start);
    }).catch(function (err) {
      document.getElementById('startBtn').disabled = true;
      document.getElementById('startBtn').textContent = '题库加载失败';
      UI.toast(err.message);
    });
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
