// Static + behavioural checks on the built robot page.
// Usage: node test_robot_page.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const page = fs.readFileSync(path.join(__dirname, 'docs', 'robot.html'), 'utf8');
let ok = true;
const check = (name, pass, detail = '') => {
  console.log(`  ${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  ' + detail : ''}`);
  ok = ok && pass;
};

console.log(`page: ${(page.length / 1e6).toFixed(2)} MB`);
console.log('\nstructure:');
check('no unfilled placeholders', !/__ROBOTNET__|__FLYBRAIN_JS__/.test(page));
check('charset declared', page.startsWith('<meta charset="utf-8">'));
check('Japanese text intact', page.includes('ハエの脳に体を与える'));
check('links back to the main page', page.includes('href="index.html"'));
check('no external resource references',
      !/(src|href)\s*=\s*["']https?:\/\/(?!github\.com)/.test(page));

const script = page.slice(page.indexOf('<script>') + 8, page.lastIndexOf('</script>'));
const markup = page.slice(0, page.indexOf('<script>'));
const allIds = [...markup.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
const dupes = allIds.filter((id, i) => allIds.indexOf(id) !== i);
const declared = new Set(allIds);
const used = new Set([...script.matchAll(/\$\('([^']+)'\)/g)].map(m => m[1]));
const missing = [...used].filter(id => !declared.has(id));

console.log('\nDOM wiring:');
check('no duplicate element ids', dupes.length === 0, dupes.join(', ') || `${allIds.length} ids`);
check('all referenced element ids exist', missing.length === 0,
      missing.join(', ') || `${used.size} ids checked`);

console.log('\nsyntax:');
try {
  new vm.Script(script, { filename: 'robot-inline.js' });
  check('inline script parses', true, `${(script.length / 1e6).toFixed(2)} MB`);
} catch (e) {
  check('inline script parses', false, e.message);
}

console.log('\nembedded sensorimotor circuit:');
try {
  const engineSrc = script.slice(script.indexOf('const FlyBrain = (() => {'),
                                 script.indexOf('const ROBOTNET ='));
  const dataAt = script.indexOf('const ROBOTNET =');
  const dataSrc = script.slice(dataAt, script.indexOf('\n', dataAt));
  const ctx = { atob: b => Buffer.from(b, 'base64').toString('binary'), module: {}, console };
  vm.createContext(ctx);
  vm.runInContext(engineSrc + '\n' + dataSrc +
                  '\nthis.__net = FlyBrain.decodeNet(ROBOTNET);\nthis.__FB = FlyBrain;', ctx);
  const FB = ctx.__FB, net = ctx.__net, G = net.groups;
  check('network decodes', net.n === 5000,
        `${net.n} neurons, ${net.indices.length.toLocaleString()} synapses`);
  check('both antennae and both motor pools present',
        G.sugarL.length && G.sugarR.length && G.dnL.length > 20 && G.dnR.length > 20,
        `sugar ${G.sugarL.length}L/${G.sugarR.length}R, DN ${G.dnL.length}L/${G.dnR.length}R`);

  const drive = (grp) => {
    let l = 0, r = 0, rt = 0;
    for (let k = 0; k < 2; k++) {
      const b = new FB.Brain(net, 500 + k * 131);
      if (grp) b.setStim(G[grp], 150);
      b.runSteps(1500);
      b.spikes.fill(0);
      const t0 = Date.now();
      b.runSteps(4000);
      rt += 0.4 / ((Date.now() - t0) / 1000) / 2;
      l += G.dnL.reduce((a, i) => a + b.spikes[i], 0) / 0.4 / 2;
      r += G.dnR.reduce((a, i) => a + b.spikes[i], 0) / 0.4 / 2;
    }
    return { l, r, idx: (r - l) / (r + l || 1), rt };
  };
  const L = drive('sugarL'), R = drive('sugarR'), none = drive(null);
  check('a taste on the left leans the output left', L.idx < 0, `index ${L.idx.toFixed(3)}`);
  check('a taste on the right leans the output right', R.idx > 0, `index ${R.idx.toFixed(3)}`);
  check('the two sides are distinguishable', R.idx - L.idx > 0.05,
        `separation ${(R.idx - L.idx).toFixed(3)}; whole brain 0.309`);
  check('no motor output without a stimulus', none.l + none.r === 0, `${none.l + none.r} Hz`);
  console.log(`  info  simulation speed  x${L.rt.toFixed(2)} realtime`);
} catch (e) {
  check('embedded circuit runs', false, e.message);
}

process.exit(ok ? 0 : 1);
