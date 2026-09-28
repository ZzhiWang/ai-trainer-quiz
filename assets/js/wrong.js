/* 错题本 / 收藏夹：列表、搜索、筛选、展开看解析、一键重刷 */
(function () {
  'use strict';

  var tab = 'wrong';
  var keyword = '';
  var filter = { levels: [3, 4], types: ['judge', 'single', 'multi'] };
  var openIds = {};

  function $(id) { return document.getElementById(id); }

  function items() {
    var ids = tab === 'wrong' ? Store.wrongIds() : Store.favIds();
    var stats = Store.stats();
    var list = ids.map(function (id) { return Bank.byId(id); }).filter(Boolean);

    list = list.filter(function (q) {
      return filter.levels.indexOf(q.lv) >= 0 && filter.types.indexOf(q.type) >= 0;
    });
    if (keyword) {
      var kw = keyword.toLowerCase();
      list = list.filter(function (q) {
        return (q.stem + ' ' + Object.keys(q.opts).map(function (k) { return q.opts[k]; }).join(' '))
          .toLowerCase().indexOf(kw) >= 0;
      });
    }
    // 错题按最近答错时间倒序
    var wmap = {};
    if (tab === 'wrong') Store.wrongIds().forEach(function (id) { wmap[id] = true; });
    list.sort(function (a, b) {
      var sa = stats[a.id] || { ts: 0 };
      var sb = stats[b.id] || { ts: 0 };
      return (sb.ts || 0) - (sa.ts || 0);
    });
    return list;
  }

  function chip(label, active) {
    var b = document.createElement('button');
    b.className = 'chip';
    b.type = 'button';
    b.setAttribute('aria-pressed', active ? 'true' : 'false');
    b.textContent = label;
    return b;
  }

  function renderFilters() {
    var box = $('filters');
    box.innerHTML = '';
    [3, 4].forEach(function (lv) {
      var b = chip(lv === 3 ? '三级' : '四级', filter.levels.indexOf(lv) >= 0);
      b.addEventListener('click', function () {
        var i = filter.levels.indexOf(lv);
        if (i >= 0) { if (filter.levels.length > 1) filter.levels.splice(i, 1); }
        else filter.levels.push(lv);
        render();
      });
      box.appendChild(b);
    });
    [['judge', '判断题'], ['single', '单选题'], ['multi', '多选题']].forEach(function (t) {
      var b = chip(t[1], filter.types.indexOf(t[0]) >= 0);
      b.addEventListener('click', function () {
        var i = filter.types.indexOf(t[0]);
        if (i >= 0) { if (filter.types.length > 1) filter.types.splice(i, 1); }
        else filter.types.push(t[0]);
        render();
      });
      box.appendChild(b);
    });
  }

  function render() {
    $('tabWrong').textContent = '错题本（' + Store.wrongIds().length + '）';
    $('tabFav').textContent = '收藏夹（' + Store.favIds().length + '）';
    $('tabWrong').setAttribute('aria-selected', tab === 'wrong' ? 'true' : 'false');
    $('tabFav').setAttribute('aria-selected', tab === 'fav' ? 'true' : 'false');

    var list = items();
    $('practiceBtn').textContent = '开始重刷（' + list.length + ' 题）';
    $('practiceBtn').disabled = list.length === 0;

    var box = $('list');
    box.innerHTML = '';
    if (!list.length) {
      box.innerHTML = '<div class="empty">' +
        (tab === 'wrong' ? '还没有错题。去刷几道题吧。' : '还没有收藏题目。答题时点右上角 ☆ 收藏。') +
        '</div>';
      return;
    }

    list.forEach(function (q) {
      var d = document.createElement('div');
      d.className = 'list-item';
      var st = Store.stats()[q.id] || { r: 0, w: 0 };
      var src = UI.srcInfo(q.src);
      var open = !!openIds[q.id];

      var head = document.createElement('div');
      head.className = 'lt';
      head.style.cursor = 'pointer';
      head.textContent = q.stem;
      head.addEventListener('click', function () {
        openIds[q.id] = !open;
        render();
      });
      d.appendChild(head);

      var meta = document.createElement('div');
      meta.className = 'lm';
      meta.innerHTML =
        '<span class="tag lv' + q.lv + '">' + (q.lv === 3 ? '三级' : '四级') + '</span>' +
        '<span>' + UI.typeLabel(q.type) + '</span>' +
        (tab === 'wrong' ? '<span>错 <b>' + st.w + '</b> 次 / 对 <b>' + st.r + '</b> 次</span>' : '') +
        '<span class="tag ' + src.cls + '">' + src.label + '</span>' +
        '<span>' + (open ? '收起 ▲' : '查看答案解析 ▼') + '</span>';
      d.appendChild(meta);

      if (open) {
        var detail = document.createElement('div');
        detail.style.marginTop = '12px';
        var html = '';
        UI.optionList(q).forEach(function (o) {
          var isAns = q.type === 'judge' ? q.ans === o.key : q.ans.indexOf(o.key) >= 0;
          html += '<div style="padding:6px 0;font-size:14.5px;' + (isAns ? 'color:var(--ok);font-weight:600' : 'color:var(--text-soft)') + '">' +
            o.key + '. ' + UI.esc(o.text) + (isAns ? '　✓ 正确答案' : '') + '</div>';
        });
        if (q.exp) {
          html += '<div style="margin-top:10px;font-size:14px;color:var(--text-soft);white-space:pre-wrap">' + UI.esc(q.exp) + '</div>';
        }
        html += '<div style="margin-top:10px;font-size:12.5px;color:var(--text-dim)">答案来源：' + src.label + '。' + src.note + '</div>';

        var btns = document.createElement('div');
        btns.className = 'btn-row';
        btns.style.marginTop = '12px';
        var rm = document.createElement('button');
        rm.className = 'icon-btn';
        rm.textContent = tab === 'wrong' ? '从错题本移除' : '取消收藏';
        rm.addEventListener('click', function (e) {
          e.stopPropagation();
          if (tab === 'wrong') Store.removeWrong(q.id); else Store.toggleFav(q.id);
          UI.toast('已移除');
          render();
        });
        var single = document.createElement('button');
        single.className = 'icon-btn';
        single.textContent = '只刷这一题';
        single.addEventListener('click', function (e) {
          e.stopPropagation();
          startWith([q.id]);
        });
        btns.appendChild(rm);
        btns.appendChild(single);

        detail.innerHTML = html;
        detail.appendChild(btns);
        d.appendChild(detail);
      }

      box.appendChild(d);
    });
  }

  function startWith(filterFn) {
    var ids;
    if (Array.isArray(filterFn)) ids = filterFn;
    else ids = items().map(function (q) { return q.id; });
    if (!ids.length) { UI.toast('列表为空'); return; }
    Store.saveSession({
      ids: ids, idx: 0, picks: {}, graded: {}, optOrder: {},
      mode: tab === 'wrong' ? 'wrong' : 'fav',
      filters: filter, startedAt: Date.now(), finished: false
    });
    location.href = 'practice.html';
  }

  function boot() {
    if (window.__wrongBooted) return;
    window.__wrongBooted = true;
    UI.applyTheme();
    UI.bindThemeToggle();
    Bank.load().then(function () {
      var m = UI.qs('tab');
      if (m === 'fav') tab = 'fav';
      $('tabWrong').addEventListener('click', function () { tab = 'wrong'; render(); });
      $('tabFav').addEventListener('click', function () { tab = 'fav'; render(); });
      $('search').addEventListener('input', function (e) { keyword = e.target.value.trim(); render(); });
      $('practiceBtn').addEventListener('click', function () { startWith(); });
      $('clearBtn').addEventListener('click', function () {
        var label = tab === 'wrong' ? '错题本' : '收藏夹';
        var n = tab === 'wrong' ? Store.wrongIds().length : Store.favIds().length;
        if (!n) { UI.toast(label + '已经是空的'); return; }
        if (!confirm('确定清空' + label + '里的 ' + n + ' 道题吗？')) return;
        if (tab === 'wrong') Store.clearWrong();
        else Store.favIds().forEach(function (id) { Store.toggleFav(id); });
        UI.toast('已清空');
        render();
      });
      renderFilters();
      render();
    }).catch(function (err) { UI.toast(err.message); });
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
