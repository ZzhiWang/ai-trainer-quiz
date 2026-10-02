/* 公共 UI：主题、提示条、来源徽标、题目渲染辅助 */
window.UI = (function () {
  'use strict';

  var SRC = {
    official: { label: '官方答案', cls: 'src-official', note: '来自官方模拟试卷答案区。' },
    consensus: { label: '多源一致', cls: 'src-consensus', note: '两个以上题库来源答案一致。' },
    reviewed: { label: '已复核', cls: 'src-reviewed', note: '多个来源存在分歧，已人工逐题复核裁定。' },
    gz: { label: '题库答案', cls: 'src-referenced', note: '来自第三方题库答案，未经官方确认。' },
    ww: { label: '题库答案', cls: 'src-referenced', note: '来自第三方题库答案，未经官方确认。' },
    bank: { label: '题库答案', cls: 'src-referenced', note: '来自第三方题库答案，未经官方确认。' },
    n9: { label: '大赛题库答案', cls: 'src-referenced', note: '来自第九届全国职工职业技能大赛公开理论题库，未经官方确认，请与官方资料核对。' },
    ai: { label: 'AI 生成', cls: 'src-ai', note: '此题的原始题库中没有答案，答案由 AI 生成，仅供参考。' }
  };

  var TYPE_LABEL = { judge: '判断题', single: '单选题', multi: '多选题' };

  function srcInfo(src) { return SRC[src] || SRC.bank; }
  function typeLabel(type) { return TYPE_LABEL[type] || type; }

  /* ---------------------------------------------------------------- 主题 */
  function applyTheme() {
    var s = Store.settings();
    var want = s.theme;
    if (want === 'auto') {
      want = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', want);
    var btn = document.querySelector('[data-theme-toggle]');
    if (btn) btn.textContent = want === 'dark' ? '☀️' : '🌙';
  }

  function bindThemeToggle() {
    var btn = document.querySelector('[data-theme-toggle]');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var cur = document.documentElement.getAttribute('data-theme');
      Store.saveSettings({ theme: cur === 'dark' ? 'light' : 'dark' });
      applyTheme();
    });
  }

  /* ---------------------------------------------------------------- 提示 */
  var toastEl, toastTimer;
  function toast(msg) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'toast';
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('show'); }, 1900);
  }

  /* ---------------------------------------------------------------- 工具 */
  function esc(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  function fmtTime(ms) {
    var s = Math.max(0, Math.floor(ms / 1000));
    var m = Math.floor(s / 60);
    return (m < 10 ? '0' : '') + m + ':' + ((s % 60) < 10 ? '0' : '') + (s % 60);
  }

  /* 判断/单选的答案文本 */
  function answerText(q) {
    if (q.type === 'judge') return q.ans === '√' ? '正确（√）' : '错误（×）';
    return q.ans;
  }

  function optionList(q) {
    if (q.type === 'judge') {
      return [{ key: '√', text: '正确' }, { key: '×', text: '错误' }];
    }
    return Object.keys(q.opts).map(function (k) { return { key: k, text: q.opts[k] }; });
  }

  function isCorrect(q, picked) {
    if (!picked || !picked.length) return false;
    var sorted = picked.slice().sort().join('');
    if (q.type === 'judge') return sorted === q.ans;
    return sorted === q.ans;
  }

  function qs(name) {
    var m = new RegExp('[?&]' + name + '=([^&]*)').exec(location.search);
    return m ? decodeURIComponent(m[1]) : null;
  }

  return {
    srcInfo: srcInfo,
    typeLabel: typeLabel,
    applyTheme: applyTheme,
    bindThemeToggle: bindThemeToggle,
    toast: toast,
    esc: esc,
    shuffle: shuffle,
    fmtTime: fmtTime,
    answerText: answerText,
    optionList: optionList,
    isCorrect: isCorrect,
    qs: qs
  };
})();
