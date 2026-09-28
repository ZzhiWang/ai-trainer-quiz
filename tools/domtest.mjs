/* 真实 DOM 测试（jsdom）：把三个页面跑起来并模拟点击。
   依赖 jsdom，仅用于开发验证：npm i jsdom --prefix /tmp/domtest
   运行：node tools/domtest.mjs */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let JSDOM, VirtualConsole;
try {
  ({ JSDOM, VirtualConsole } = require('/tmp/domtest/node_modules/jsdom'));
} catch (e) {
  console.error('未找到 jsdom，请先执行：npm i jsdom --prefix /tmp/domtest');
  process.exit(2);
}

const ROOT = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');

let pass = 0, fail = 0;
function check(name, cond, extra = '') {
  if (cond) { pass++; console.log('  ok   ' + name); }
  else { fail++; console.log('  FAIL ' + name + (extra ? '  -> ' + extra : '')); }
}

const jsErrors = [];

function makeDom(page) {
  let html = read(page).replace(/<script src="[^"]+"><\/script>/g, '');
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => {
    // 忽略 jsdom 未实现的页面跳转
    if (/Not implemented: navigation/.test(e.message)) return;
    jsErrors.push(e.message);
  });
  const dom = new JSDOM(html, {
    url: 'https://quiz.local/' + page,
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(win) {
      win.fetch = (url) => {
        const file = path.join(ROOT, String(url));
        if (!fs.existsSync(file)) {
          return Promise.resolve({ ok: false, status: 404, json: () => Promise.reject(new Error('404')) });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(JSON.parse(fs.readFileSync(file, 'utf8')))
        });
      };
      win.confirm = () => true;
      win.scrollTo = () => {};
    }
  });
  const w = dom.window;
  for (const f of ['assets/js/store.js', 'assets/js/ui.js', 'assets/js/bank.js']) {
    const s = w.document.createElement('script');
    s.textContent = read(f);
    w.document.head.appendChild(s);
  }
  const pageJs = { 'index.html': 'assets/js/home.js', 'practice.html': 'assets/js/practice.js', 'wrong.html': 'assets/js/wrong.js' }[page];
  return { dom, w, pageJs };
}

async function run(page, seed) {
  const { w, pageJs } = makeDom(page);
  if (seed) seed(w);
  const s = w.document.createElement('script');
  s.textContent = read(pageJs);
  w.document.head.appendChild(s);
  w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
  await new Promise((r) => setTimeout(r, 120));
  return w;
}

const tick = () => new Promise((r) => setTimeout(r, 60));
const q = (w, sel) => w.document.querySelector(sel);
const qa = (w, sel) => Array.from(w.document.querySelectorAll(sel));
const text = (w, sel) => (q(w, sel) ? q(w, sel).textContent.trim() : null);
const click = (el) => el && el.dispatchEvent(new el.ownerDocument.defaultView.MouseEvent('click', { bubbles: true }));

/* ============================================================ 首页 */
console.log('\n[首页 index.html]');
{
  const w = await run('index.html');
  check('题库总数渲染为 2254', text(w, '#totalNum') === '2254', text(w, '#totalNum'));
  check('级别按钮 2 个', qa(w, '#levelChips .chip').length === 2);
  check('题型按钮 3 个', qa(w, '#typeChips .chip').length === 3);
  check('模式按钮 6 个', qa(w, '#modeChips .chip').length === 6);
  check('开始按钮可用', !q(w, '#startBtn').disabled);
  check('开始按钮显示题量', /开始刷题（20 题）/.test(text(w, '#startBtn')), text(w, '#startBtn'));
  check('来源表有数据行', qa(w, '#srcTable tr').length >= 4);

  // 只选单选题
  const typeChips = qa(w, '#typeChips .chip');
  click(typeChips[0]); // 取消判断题
  click(typeChips[2]); // 取消多选题
  await tick();
  check('只勾选单选题后，按钮仍是 20 题', /开始刷题（20 题）/.test(text(w, '#startBtn')), text(w, '#startBtn'));
  check('池子提示显示筛选后的题量', /1244/.test(text(w, '#poolHint')), text(w, '#poolHint'));

  click(q(w, '#startBtn'));
  await tick();
  const sess = JSON.parse(w.localStorage.getItem('qz.session.v1'));
  check('开始刷题写入了会话', !!sess && sess.ids.length === 20);
  const allSingle = sess.ids.every((id) => w.Bank.byId(id).type === 'single');
  check('会话里全是单选题（按题型刷题生效）', allSingle);

  // 切到随机模式
  const w2 = await run('index.html');
  click(qa(w2, '#modeChips .chip')[1]);
  await tick();
  click(q(w2, '#startBtn'));
  await tick();
  const s2 = JSON.parse(w2.localStorage.getItem('qz.session.v1'));
  check('随机模式会话已建立', !!s2 && s2.ids.length === 20 && s2.mode === 'random');

  // 题量选全部
  const w3 = await run('index.html');
  click(qa(w3, '#countChips .chip')[4]);
  await tick();
  check('全部题量按钮文案正确', /2254/.test(text(w3, '#poolHint')), text(w3, '#poolHint'));
}

/* ============================================================ 答题页 */
console.log('\n[答题页 practice.html]');
{
  let ids = [];
  // 直接从题库文件挑 3 道不同题型的题（jsdom 每个实例的 localStorage 是隔离的）
  const all = JSON.parse(read('data/questions.json')).questions;
  const singleQ = all.find((x) => x.type === 'single');
  const judgeQ = all.find((x) => x.type === 'judge');
  const multiQ = all.find((x) => x.type === 'multi' && x.ans.length === 3);
  ids = [singleQ.id, judgeQ.id, multiQ.id];
  const w2 = await run('practice.html', (win) => {
    win.localStorage.setItem('qz.session.v1', JSON.stringify({
      ids, idx: 0, picks: {}, graded: {}, optOrder: {},
      mode: 'order', filters: { levels: [3, 4], types: ['judge', 'single', 'multi'] },
      startedAt: Date.now(), finished: false
    }));
  });
  const q0 = w2.Bank.byId(ids[0]);

  check('题干渲染正确', text(w2, '#stem') === q0.stem);
  check('选项数量与题目一致', qa(w2, '#options .opt').length === Object.keys(q0.opts).length);
  check('题号显示 1/3', /第 1 \/ 3 题/.test(text(w2, '#posText')), text(w2, '#posText'));
  check('显示级别与题型标签', /三级|四级/.test(text(w2, '#qmeta')) && /单选题/.test(text(w2, '#qmeta')));
  check('显示答案来源标签', qa(w2, '#qmeta .tag').length >= 3);

  // 故意选错
  const wrongKey = Object.keys(q0.opts).find((k) => k !== q0.ans);
  const wrongBtn = qa(w2, '#options .opt').find((b) => b.dataset.key === wrongKey);
  click(wrongBtn);
  await tick();
  check('选错后立即判分', /回答错误/.test(text(w2, '#feedback')));
  check('选项标记了正确答案', qa(w2, '#options .opt.correct').length === 1);
  check('选项标记了错误选择', qa(w2, '#options .opt.wrong').length === 1);
  check('错题进入错题本', JSON.parse(w2.localStorage.getItem('qz.wrong.v1') || '{}')[q0.id] != null);
  check('统计已记录', !!JSON.parse(w2.localStorage.getItem('qz.stats.v1'))[q0.id]);

  // 收藏
  click(q(w2, '#favBtn'));
  await tick();
  check('收藏按钮变为 ★', text(w2, '#favBtn') === '★');
  check('收藏写入存储', !!JSON.parse(w2.localStorage.getItem('qz.fav.v1'))[q0.id]);

  // 下一题 -> 判断题
  click(q(w2, '#nextBtn'));
  await tick();
  const q1 = w2.Bank.byId(ids[1]);
  check('翻到判断题', text(w2, '#stem') === q1.stem);
  check('判断题是两个选项', qa(w2, '#options .opt').length === 2);
  const okBtn = qa(w2, '#options .opt').find((b) => b.dataset.key === q1.ans);
  click(okBtn);
  await tick();
  check('答对后显示回答正确', /回答正确/.test(text(w2, '#feedback')));

  // 下一题 -> 多选题
  click(q(w2, '#nextBtn'));
  await tick();
  const q2 = w2.Bank.byId(ids[2]);
  check('翻到多选题', text(w2, '#stem') === q2.stem);
  const keys = q2.ans.split('');
  click(qa(w2, '#options .opt').find((b) => b.dataset.key === keys[0]));
  await tick();
  check('多选题选中一个后不判分', text(w2, '#feedback') === '' || q(w2, '#feedback').innerHTML === '');
  check('多选题选中后出现提交按钮', !q(w2, '#submitBtn').hidden);
  click(qa(w2, '#options .opt').find((b) => b.dataset.key === keys[1]));
  click(qa(w2, '#options .opt').find((b) => b.dataset.key === keys[2]));
  await tick();
  check('多选题选中项高亮 3 个', qa(w2, '#options .opt.chosen').length === 3);
  click(q(w2, '#submitBtn'));
  await tick();
  check('多选题提交后判分', /回答正确/.test(text(w2, '#feedback')));

  // 答题卡
  click(q(w2, '#sheetBtn'));
  await tick();
  check('答题卡打开', q(w2, '#sheet').classList.contains('open'));
  check('答题卡题号 3 个', qa(w2, '#gridNums button').length === 3);
  check('答对题号标绿', qa(w2, '#gridNums button.ok').length === 2);
  check('答错题号标红', qa(w2, '#gridNums button.bad').length === 1);

  // 交卷
  click(q(w2, '#finishBtn'));
  await tick();
  check('结果页显示', !q(w2, '#resultWrap').hidden);
  check('正确率 67%', text(w2, '#scoreNum') === '67%', text(w2, '#scoreNum'));
  check('答对 2 题', text(w2, '#rRight') === '2');
  check('答错 1 题', text(w2, '#rWrong') === '1');
  check('列出本次错题', qa(w2, '#wrongList .list-item').length === 1);
}

/* ============================================================ 错题本 */
console.log('\n[错题本 wrong.html]');
{
  const w = await run('wrong.html', (win) => {
    win.localStorage.setItem('qz.stats.v1', JSON.stringify({
      'L4-S-1151': { r: 0, w: 3, ts: Date.now() },
      'L3-J-0001': { r: 1, w: 1, ts: Date.now() }
    }));
    win.localStorage.setItem('qz.wrong.v1', JSON.stringify({
      'L4-S-1151': Date.now(), 'L3-J-0001': Date.now()
    }));
    win.localStorage.setItem('qz.fav.v1', JSON.stringify({ 'L3-M-0601': Date.now() }));
  });
  check('错题标签统计为 2', /错题本（2）/.test(text(w, '#tabWrong')), text(w, '#tabWrong'));
  check('收藏标签统计为 1', /收藏夹（1）/.test(text(w, '#tabFav')), text(w, '#tabFav'));
  check('列表渲染 2 条', qa(w, '#list .list-item').length === 2, String(qa(w, '#list .list-item').length));
  check('重刷按钮题量正确', /开始重刷（2 题）/.test(text(w, '#practiceBtn')), text(w, '#practiceBtn'));

  // 展开第一条看解析
  const head = q(w, '#list .list-item .lt');
  click(head);
  await tick();
  const itemHtml = q(w, '#list .list-item').innerHTML;
  check('展开后显示答案', /正确答案/.test(itemHtml));
  check('展开后有移除按钮', /从错题本移除/.test(itemHtml));

  // 切到收藏夹
  click(q(w, '#tabFav'));
  await tick();
  check('收藏夹列表 1 条', qa(w, '#list .list-item').length === 1);
  check('收藏夹按钮文案切换', /开始重刷（1 题）/.test(text(w, '#practiceBtn')));

  // 点击开始重刷 -> 写入会话
  click(q(w, '#practiceBtn'));
  await tick();
  const sess = JSON.parse(w.localStorage.getItem('qz.session.v1'));
  check('重刷写入会话', !!sess && sess.ids.length === 1 && sess.mode === 'fav');
}

console.log('\n页面脚本运行时错误：' + (jsErrors.length ? jsErrors.join(' | ') : '无'));
check('无未捕获的脚本错误', jsErrors.length === 0, jsErrors.join(' | '));

console.log('\n结果：' + pass + ' 通过，' + fail + ' 失败');
process.exit(fail ? 1 : 0);
