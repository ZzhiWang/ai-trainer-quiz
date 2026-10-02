/* 本地存储层：进度、错题、收藏、统计、设置。
   全部存在浏览器 localStorage，不需要登录、不上传服务器。 */
window.Store = (function () {
  'use strict';

  var K = {
    stats: 'qz.stats.v1',      // { qid: { r: 答对次数, w: 答错次数, ts: 最后作答时间 } }
    wrong: 'qz.wrong.v1',      // { qid: 时间戳 }
    fav: 'qz.fav.v1',          // { qid: 时间戳 }
    session: 'qz.session.v1',  // 当前这次练习
    settings: 'qz.settings.v1',
    last: 'qz.last.v1'         // 上次的筛选条件，用于"继续上次"
    ,
    // 精华题模块独立进度（新增键，不影响上面的任何旧键）
    essStats: 'qz.ess.stats.v1',
    essWrong: 'qz.ess.wrong.v1',
    essSession: 'qz.ess.session.v1'
  };

  var DEFAULTS = {
    instant: true,      // 选完立即判分
    showExp: true,      // 显示解析
    shuffleOpts: false, // 打乱选项顺序
    theme: 'auto'
  };

  function read(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      if (!raw) return fallback;
      var val = JSON.parse(raw);
      return val == null ? fallback : val;
    } catch (e) {
      return fallback;
    }
  }

  function write(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (e) {
      return false;
    }
  }

  function settings() {
    return Object.assign({}, DEFAULTS, read(K.settings, {}));
  }

  function saveSettings(patch) {
    var s = Object.assign(settings(), patch);
    write(K.settings, s);
    return s;
  }

  function stats() { return read(K.stats, {}); }

  /* scope = 'ess' 时额外写入精华题独立进度，同时仍然更新全库统计（双写） */
  function record(qid, correct, scope) {
    var all = stats();
    var s = all[qid] || { r: 0, w: 0, ts: 0 };
    if (correct) s.r += 1; else s.w += 1;
    s.ts = Date.now();
    all[qid] = s;
    write(K.stats, all);

    var wrong = wrongMap();
    if (correct) {
      // 答对不自动移除错题，但记录一次"已订正"由用户自己决定
    } else {
      wrong[qid] = wrong[qid] || Date.now();
      write(K.wrong, wrong);
    }

    if (scope === 'ess') {
      var es = essStats();
      var e = es[qid] || { r: 0, w: 0, ts: 0 };
      if (correct) e.r += 1; else e.w += 1;
      e.ts = Date.now();
      es[qid] = e;
      write(K.essStats, es);
      if (!correct) {
        var ew = essWrongMap();
        ew[qid] = ew[qid] || Date.now();
        write(K.essWrong, ew);
      }
    }
  }

  /* ------------------------------------------------------ 精华题独立进度 */
  function essStats() { return read(K.essStats, {}); }
  function essWrongMap() { return read(K.essWrong, {}); }
  function essWrongIds() { return Object.keys(essWrongMap()); }
  function removeEssWrong(qid) {
    var w = essWrongMap();
    delete w[qid];
    write(K.essWrong, w);
  }
  function clearEssWrong() { write(K.essWrong, {}); }
  function essSession() { return read(K.essSession, null); }
  function saveEssSession(s) { write(K.essSession, s); }
  function clearEssSession() { try { localStorage.removeItem(K.essSession); } catch (e) {} }

  /* 按分区统计：ids 为该分区的题目 id 集合，size 为分区题量 */
  function summaryFor(ids, size) {
    var all = stats();
    var right = 0, wrong = 0, answered = 0;
    (ids || []).forEach(function (id) {
      var s = all[id];
      if (!s) return;
      answered += 1;
      right += s.r;
      wrong += s.w;
    });
    var total = right + wrong;
    return {
      answered: answered,
      total: total,
      right: right,
      wrong: wrong,
      rate: total ? Math.round((right / total) * 100) : 0,
      coverage: size ? Math.round((answered / size) * 100) : 0,
      wrongCount: wrongIds().length,
      favCount: favIds().length
    };
  }

  /* 精华题模块用的统计（只统计精华模式内的作答） */
  function essSummary(ids, size) {
    var all = essStats();
    var right = 0, wrong = 0, answered = 0;
    (ids || []).forEach(function (id) {
      var s = all[id];
      if (!s) return;
      answered += 1;
      right += s.r;
      wrong += s.w;
    });
    var total = right + wrong;
    return {
      answered: answered,
      total: total,
      right: right,
      wrong: wrong,
      rate: total ? Math.round((right / total) * 100) : 0,
      coverage: size ? Math.round((answered / size) * 100) : 0,
      wrongCount: essWrongIds().length,
      favCount: favIds().length
    };
  }

  function wrongMap() { return read(K.wrong, {}); }
  function wrongIds() { return Object.keys(wrongMap()); }
  function removeWrong(qid) {
    var w = wrongMap();
    delete w[qid];
    write(K.wrong, w);
  }
  function clearWrong() { write(K.wrong, {}); }

  function favMap() { return read(K.fav, {}); }
  function favIds() { return Object.keys(favMap()); }
  function isFav(qid) { return !!favMap()[qid]; }
  function toggleFav(qid) {
    var f = favMap();
    if (f[qid]) delete f[qid]; else f[qid] = Date.now();
    write(K.fav, f);
    return !!f[qid];
  }

  function summary(bankSize) {
    var all = stats();
    var ids = Object.keys(all);
    var right = 0, wrong = 0;
    ids.forEach(function (id) {
      var s = all[id];
      right += s.r;
      wrong += s.w;
    });
    var total = right + wrong;
    return {
      answered: ids.length,
      total: total,
      right: right,
      wrong: wrong,
      rate: total ? Math.round((right / total) * 100) : 0,
      coverage: bankSize ? Math.round((ids.length / bankSize) * 100) : 0,
      wrongCount: wrongIds().length,
      favCount: favIds().length
    };
  }

  function session() { return read(K.session, null); }
  function saveSession(s) { write(K.session, s); }
  function clearSession() { try { localStorage.removeItem(K.session); } catch (e) {} }

  function lastFilters() { return read(K.last, null); }
  function saveLastFilters(f) { write(K.last, f); }

  function exportAll() {
    return {
      type: 'ai-trainer-quiz-backup',
      version: 1,
      exportedAt: new Date().toISOString(),
      stats: stats(),
      wrong: wrongMap(),
      fav: favMap(),
      settings: settings(),
      essStats: essStats(),
      essWrong: essWrongMap()
    };
  }

  function importAll(obj) {
    if (!obj || obj.type !== 'ai-trainer-quiz-backup') {
      throw new Error('不是本网站的备份文件');
    }
    if (obj.stats) write(K.stats, obj.stats);
    if (obj.wrong) write(K.wrong, obj.wrong);
    if (obj.fav) write(K.fav, obj.fav);
    if (obj.settings) write(K.settings, Object.assign({}, DEFAULTS, obj.settings));
    if (obj.essStats) write(K.essStats, obj.essStats);
    if (obj.essWrong) write(K.essWrong, obj.essWrong);
    return true;
  }

  function resetProgress() {
    try {
      localStorage.removeItem(K.stats);
      localStorage.removeItem(K.wrong);
      localStorage.removeItem(K.fav);
      localStorage.removeItem(K.session);
      localStorage.removeItem(K.essStats);
      localStorage.removeItem(K.essWrong);
      localStorage.removeItem(K.essSession);
    } catch (e) {}
  }

  return {
    settings: settings,
    saveSettings: saveSettings,
    stats: stats,
    record: record,
    summaryFor: summaryFor,
    essStats: essStats,
    essSummary: essSummary,
    essWrongIds: essWrongIds,
    removeEssWrong: removeEssWrong,
    clearEssWrong: clearEssWrong,
    essSession: essSession,
    saveEssSession: saveEssSession,
    clearEssSession: clearEssSession,
    wrongIds: wrongIds,
    removeWrong: removeWrong,
    clearWrong: clearWrong,
    favIds: favIds,
    isFav: isFav,
    toggleFav: toggleFav,
    summary: summary,
    session: session,
    saveSession: saveSession,
    clearSession: clearSession,
    lastFilters: lastFilters,
    saveLastFilters: saveLastFilters,
    exportAll: exportAll,
    importAll: importAll,
    resetProgress: resetProgress
  };
})();
