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
    return all().filter(function (q) {
      return levels.indexOf(q.lv) >= 0 && types.indexOf(q.type) >= 0;
    });
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
    MODES: MODES
  };
})();
