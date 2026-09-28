/* 题库层：加载 data/questions.json，按条件筛选、组卷。 */
window.Bank = (function () {
  'use strict';

  var _data = null;
  var _byId = null;
  var URL = 'data/questions.json';

  function load() {
    if (_data) return Promise.resolve(_data);
    return fetch(URL, { cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('题库文件读取失败（HTTP ' + r.status + '）');
        return r.json();
      })
      .then(function (json) {
        _data = json;
        _byId = {};
        json.questions.forEach(function (q) { _byId[q.id] = q; });
        return _data;
      })
      .catch(function (err) {
        if (location.protocol === 'file:') {
          throw new Error('直接双击打开 HTML 时浏览器不允许读取题库文件。请用本地静态服务器预览：python3 -m http.server');
        }
        throw err;
      });
  }

  function all() { return _data ? _data.questions : []; }
  function meta() { return _data ? _data.meta : null; }
  function byId(id) { return _byId ? _byId[id] : null; }

  /* 按级别 + 题型过滤 */
  function filter(f) {
    f = f || {};
    var levels = f.levels && f.levels.length ? f.levels : [3, 4];
    var types = f.types && f.types.length ? f.types : ['judge', 'single', 'multi'];
    var secs = f.secs && f.secs.length ? f.secs : null;
    return all().filter(function (q) {
      if (levels.indexOf(q.lv) < 0 || types.indexOf(q.type) < 0) return false;
      if (secs && secs.indexOf(secKey(q)) < 0) return false;
      return true;
    });
  }

  function secKey(q) { return q.ch + '::' + q.sec; }

  /* 章节列表（按题库里的官方顺序，章内按节顺序） */
  function sectionList(levels) {
    levels = levels && levels.length ? levels : [3, 4];
    var seen = {};
    var list = [];
    all().forEach(function (q) {
      if (!q.ch || levels.indexOf(q.lv) < 0) return;
      var key = secKey(q);
      var item = seen[key];
      if (!item) {
        item = seen[key] = { key: key, ch: q.ch, sec: q.sec, lv: {}, total: 0 };
        list.push(item);
      }
      item.total += 1;
      item.lv[q.lv] = (item.lv[q.lv] || 0) + 1;
    });
    return list;
  }

  /* 按章分组的章节列表，附带当前筛选条件下的题量 */
  function sectionGroups(f) {
    var list = sectionList(f.levels);
    var groups = [];
    var index = {};
    list.forEach(function (item) {
      var g = index[item.ch];
      if (!g) {
        g = index[item.ch] = { ch: item.ch, items: [] };
        groups.push(g);
      }
      item.count = filter({
        levels: f.levels, types: f.types, secs: [item.key]
      }).length;
      g.items.push(item);
    });
    return groups;
  }

  function countBy(f) {
    var pool = filter(f);
    var out = { total: pool.length, '3': 0, '4': 0, judge: 0, single: 0, multi: 0 };
    pool.forEach(function (q) {
      out[q.lv] += 1;
      out[q.type] += 1;
    });
    return out;
  }

  /* 组卷：返回题目 id 数组 */
  function build(opts) {
    var mode = opts.mode || 'order';
    var pool = filter(opts);
    var stats = Store.stats();
    var list;

    if (mode === 'wrong') {
      var wids = {};
      Store.wrongIds().forEach(function (id) { wids[id] = true; });
      list = pool.filter(function (q) { return wids[q.id]; });
    } else if (mode === 'fav') {
      var fids = {};
      Store.favIds().forEach(function (id) { fids[id] = true; });
      list = pool.filter(function (q) { return fids[q.id]; });
    } else if (mode === 'unseen') {
      var fresh = pool.filter(function (q) { return !stats[q.id]; });
      var seen = pool.filter(function (q) { return !!stats[q.id]; });
      list = fresh.concat(UI.shuffle(seen));
    } else if (mode === 'weak') {
      // 错过的题优先，其次是从没做过的，最后是答对过的
      var wrong = [], fresh2 = [], right = [];
      UI.shuffle(pool).forEach(function (q) {
        var s = stats[q.id];
        if (s && s.w > 0) wrong.push(q);
        else if (!s) fresh2.push(q);
        else right.push(q);
      });
      list = wrong.concat(fresh2, right);
    } else if (mode === 'random') {
      list = UI.shuffle(pool);
    } else {
      list = pool.slice();
    }

    var ids = list.map(function (q) { return q.id; });
    var n = opts.count || 0;
    if (n > 0 && ids.length > n) ids = ids.slice(0, n);
    return ids;
  }

  var MODES = [
    { key: 'order', label: '顺序练习', hint: '按题库原顺序' },
    { key: 'random', label: '随机练习', hint: '打乱全部题目' },
    { key: 'weak', label: '智能优先', hint: '错题→没做过→做过' },
    { key: 'unseen', label: '只刷没做过的', hint: '跳过已做过的题' },
    { key: 'wrong', label: '只刷错题', hint: '来自错题本' },
    { key: 'fav', label: '只刷收藏', hint: '来自收藏夹' }
  ];

  return {
    load: load,
    all: all,
    meta: meta,
    byId: byId,
    filter: filter,
    countBy: countBy,
    build: build,
    secKey: secKey,
    sectionList: sectionList,
    sectionGroups: sectionGroups,
    MODES: MODES
  };
})();
