/* 无浏览器环境下的逻辑自测：node tools/selftest.mjs
   校验题库加载、组卷、判分、错题/收藏/统计、导入导出。 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const ROOT = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');

// --- 最小的浏览器环境替身 -------------------------------------------------
const store = new Map();
const localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k)
};

const sandbox = {
  console,
  localStorage,
  location: { protocol: 'https:', search: '' },
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  Date,
  Math,
  JSON,
  Promise,
  Blob: class {},
  URL: { createObjectURL: () => '', revokeObjectURL: () => {} },
  FileReader: class {},
  document: { addEventListener() {}, querySelector: () => null, querySelectorAll: () => [], createElement: () => ({ style: {}, classList: { add() {}, remove() {} }, appendChild() {} }) },
  fetch: (url) => {
    const file = path.join(ROOT, url);
    if (!fs.existsSync(file)) return Promise.resolve({ ok: false, status: 404 });
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(JSON.parse(fs.readFileSync(file, 'utf8'))) });
  }
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

for (const f of ['assets/js/store.js', 'assets/js/ui.js', 'assets/js/bank.js']) {
  vm.runInContext(read(f), sandbox, { filename: f });
}

const { Store, UI, Bank } = sandbox;

let pass = 0, fail = 0;
function check(name, cond, extra = '') {
  if (cond) { pass++; console.log('  ok   ' + name); }
  else { fail++; console.log('  FAIL ' + name + (extra ? '  -> ' + extra : '')); }
}

console.log('\n[1] 题库加载');
const data = await Bank.load();
const qs = data.questions;
check('题目总数 = ' + qs.length, qs.length > 2000);
check('每题都有答案', qs.every((q) => !!q.ans));
check('每题都有合法题型', qs.every((q) => ['judge', 'single', 'multi'].includes(q.type)));
check('ID 唯一', new Set(qs.map((q) => q.id)).size === qs.length);
check('meta.counts 与实际一致', Object.entries(data.meta.counts).every(([k, v]) => {
  const [lv, type] = k.split('/');
  return qs.filter((q) => String(q.lv) === lv && q.type === type).length === v;
}));

console.log('\n[2] 按级别 / 题型筛选');
const l3 = Bank.filter({ levels: [3] });
const l4 = Bank.filter({ levels: [4] });
const single = Bank.filter({ types: ['single'] });
const l3single = Bank.filter({ levels: [3], types: ['single'] });
check('三级 ' + l3.length + ' 题', l3.every((q) => q.lv === 3) && l3.length === 1496);
check('四级 ' + l4.length + ' 题', l4.every((q) => q.lv === 4) && l4.length === 750);
check('只刷单选题 ' + single.length + ' 题', single.every((q) => q.type === 'single') && single.length === 1237);
check('三级单选 ' + l3single.length + ' 题', l3single.every((q) => q.lv === 3 && q.type === 'single') && l3single.length === 737);
check('三级+四级相加 = 总数', l3.length + l4.length === qs.length);

console.log('\n[2b] 章节');
check('每题都有章和节', qs.every((q) => q.ch && q.sec));
const secs = Bank.sectionList();
// 三级 9 节 + 四级 8 节，其中"基本要求/职业道德""基本要求/基础知识"两级同名，合并后 15 个
check('章节数 = 15（三级9 + 四级8，2 节同名合并）', secs.length === 15, String(secs.length));
check('同名章节能同时覆盖两级',
  secs.some((s) => (s.lv[3] || 0) > 0 && (s.lv[4] || 0) > 0));
check('章节题量之和 = 总题数',
  secs.reduce((s, x) => s + x.total, 0) === qs.length,
  String(secs.reduce((s, x) => s + x.total, 0)));
check('每个章节都能筛出对应题目', secs.every((it) => {
  const got = Bank.filter({ secs: [it.key] });
  return got.length === it.total && got.every((q) => Bank.secKey(q) === it.key);
}));
const secL4 = Bank.filter({ levels: [4] });
check('四级章节只含四级题', secs.filter((s) => (s.lv[4] || 0) > 0).every((it) =>
  Bank.filter({ levels: [4], secs: [it.key] }).every((q) => q.lv === 4)));
check('四级题量 = 四级各章节之和',
  secL4.length === secs.reduce((s, x) => s + (x.lv[4] || 0), 0));
const g3 = Bank.sectionGroups({ levels: [3], types: ['single'] });
check('章节分组：三级 9 节 / 5 章', g3.reduce((s, g) => s + g.items.length, 0) === 9 && g3.length === 5,
  g3.map((g) => g.ch).join(','));
const oneSec = g3[0].items[0];
check('章节分组计数与筛选一致',
  oneSec.count === Bank.filter({ levels: [3], types: ['single'], secs: [oneSec.key] }).length);
const onlySec = Bank.build({ mode: 'order', secs: [secs[0].key], count: 0 });
check('按章节组卷只出该章节题', onlySec.length === secs[0].total &&
  onlySec.every((id) => Bank.secKey(Bank.byId(id)) === secs[0].key));

console.log('\n[3] 组卷模式');
const order20 = Bank.build({ mode: 'order', count: 20 });
check('顺序 20 题', order20.length === 20 && order20[0] === Bank.filter({})[0].id);
const allIds = Bank.build({ mode: 'order', count: 0 });
check('全部 = 总题数', allIds.length === qs.length);
const r1 = Bank.build({ mode: 'random', count: 30 });
const r2 = Bank.build({ mode: 'random', count: 30 });
check('随机 30 题', r1.length === 30);
check('两次随机顺序不同', r1.join() !== r2.join());
check('随机结果无重复', new Set(r1).size === 30);
const filtered = Bank.build({ mode: 'order', types: ['judge'], levels: [4], count: 0 });
check('四级判断题共 ' + filtered.length + ' 题', filtered.every((id) => { const q = Bank.byId(id); return q.lv === 4 && q.type === 'judge'; }));

console.log('\n[4] 判分');
const jq = qs.find((q) => q.type === 'judge');
check('判断题答对', UI.isCorrect(jq, [jq.ans]));
check('判断题答错', !UI.isCorrect(jq, [jq.ans === '√' ? '×' : '√']));
const sq = qs.find((q) => q.type === 'single' && q.ans === 'C');
check('单选题答对', UI.isCorrect(sq, ['C']));
check('单选题答错', !UI.isCorrect(sq, ['A']));
const mq = qs.find((q) => q.type === 'multi' && q.ans === 'ABD');
check('多选题全对', UI.isCorrect(mq, ['B', 'D', 'A']));
check('多选题少选判错', !UI.isCorrect(mq, ['A', 'B']));
check('多选题多选判错', !UI.isCorrect(mq, ['A', 'B', 'C', 'D']));
check('未作答判错', !UI.isCorrect(mq, []));

console.log('\n[5] 错题本 / 收藏 / 统计');
const wrongQ = qs.find((q) => q.type === 'single');
Store.record(wrongQ.id, false);
Store.record(wrongQ.id, false);
Store.record(wrongQ.id, true);
check('错题进入错题本', Store.wrongIds().indexOf(wrongQ.id) >= 0);
check('错题统计 2 错 1 对', Store.stats()[wrongQ.id].w === 2 && Store.stats()[wrongQ.id].r === 1);
check('收藏切换开', Store.toggleFav(wrongQ.id) === true && Store.isFav(wrongQ.id));
check('收藏切换关', Store.toggleFav(wrongQ.id) === false && !Store.isFav(wrongQ.id));
Store.removeWrong(wrongQ.id);
check('移除错题', Store.wrongIds().indexOf(wrongQ.id) < 0);

const s = Store.summary(qs.length);
check('汇总含正确率', s.right === 1 && s.wrong === 2 && s.rate === 33);

console.log('\n[6] 错题模式组卷');
const another = qs.find((q) => q.type === 'judge');
Store.record(another.id, false);
const wrongSet = Bank.build({ mode: 'wrong', count: 0 });
check('错题模式只出错过题', wrongSet.length === 1 && wrongSet[0] === another.id);
const weak = Bank.build({ mode: 'weak', levels: [4], types: ['single'], count: 0 });
check('智能优先出题数量正确', weak.length === Bank.filter({ levels: [4], types: ['single'] }).length);
const unseen = Bank.build({ mode: 'unseen', count: 0 });
{
  const st = Store.stats();
  const firstSeen = unseen.findIndex((id) => st[id]);
  const tail = unseen.slice(firstSeen);
  check('未做过优先：没做过的排在前面', unseen.slice(0, firstSeen).every((id) => !st[id]));
  check('未做过优先：做过的集中在末尾', tail.every((id) => st[id]) && tail.length === Object.keys(st).length);
}

console.log('\n[7] 备份导入导出');
Store.record(qs[5].id, true);
const backup = Store.exportAll();
check('导出结构正确', backup.type === 'ai-trainer-quiz-backup' && !!backup.stats);
Store.resetProgress();
check('清空后无记录', Object.keys(Store.stats()).length === 0 && Store.wrongIds().length === 0);
Store.importAll(backup);
check('导入后统计恢复', Store.stats()[qs[5].id] && Store.stats()[qs[5].id].r === 1);
let threw = false;
try { Store.importAll({ type: 'nope' }); } catch (e) { threw = true; }
check('非法备份被拒绝', threw);

console.log('\n[8] 答案来源标注');
const srcs = new Set(qs.map((q) => q.src));
check('来源标记都在已知集合内', [...srcs].every((s) => ['official', 'consensus', 'reviewed', 'gz', 'ww', 'ai'].includes(s)), [...srcs].join(','));
check('AI 补答有提示文案', UI.srcInfo('ai').note.indexOf('仅供参考') >= 0);
check('所有题目都能解析出选项', qs.every((q) => UI.optionList(q).length >= 2));
check('解析覆盖率 > 90%', qs.filter((q) => q.exp).length / qs.length > 0.9);

console.log('\n结果：' + pass + ' 通过，' + fail + ' 失败');
process.exit(fail ? 1 : 0);
