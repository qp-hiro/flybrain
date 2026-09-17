// Static checks on the built page: the inline script must parse, the data
// placeholders must be gone, and the embedded engine must still simulate.
//
// Usage: node test_page.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const page = fs.readFileSync(path.join(__dirname, 'docs', 'index.html'), 'utf8');
let ok = true;
const check = (name, pass, detail = '') => {
  console.log(`  ${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  ' + detail : ''}`);
  ok = ok && pass;
};

console.log(`page: ${(page.length / 1e6).toFixed(2)} MB`);
console.log('\nstructure:');
check('no unfilled placeholders',
      !/__VIZ_DATA__|__SUBNET__|__FLYBRAIN_JS__/.test(page));
check('charset declared', page.startsWith('<meta charset="utf-8">'));
check('Japanese text intact', page.includes('ショウジョウバエ全脳'));
check('single inline script', (page.match(/<script>/g) || []).length === 1);
check('no external resource references',
      !/(src|href)\s*=\s*["']https?:\/\/(?!github\.com|codex\.flywire\.ai)/.test(page));

const script = page.slice(page.indexOf('<script>') + 8, page.lastIndexOf('</script>'));
const markup = page.slice(0, page.indexOf('<script>'));

// every element the script reaches for must actually exist in the markup
console.log('\nDOM wiring:');
const declared = new Set([...markup.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]));
const used = new Set([...script.matchAll(/(?:\$\(|getElementById\()'([^']+)'/g)].map(m => m[1]));
const allIds = [...markup.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
const dupes = allIds.filter((id, i) => allIds.indexOf(id) !== i);
check('no duplicate element ids', dupes.length === 0,
      dupes.length ? 'duplicated: ' + [...new Set(dupes)].join(', ') : `${allIds.length} ids`);
const missing = [...used].filter(id => !declared.has(id));
check('all referenced element ids exist',
      missing.length === 0,
      missing.length ? 'missing: ' + missing.join(', ') : `${used.size} ids checked`);
const unused = [...declared].filter(id => !used.has(id) && !/^(hero|rig|gamesec|logicsec)$/.test(id));
if (unused.length) console.log(`  note  unreferenced ids in markup: ${unused.join(', ')}`);
console.log('\nsyntax:');
try {
  new vm.Script(script, { filename: 'page-inline.js' });
  check('inline script parses', true, `${(script.length / 1e6).toFixed(2)} MB`);
} catch (e) {
  check('inline script parses', false, e.message);
}

// the engine and the network data are embedded in that script; pull them out
// and run them to prove the shipped page can actually simulate.
console.log('\nembedded engine:');
try {
  const engineSrc = script.slice(script.indexOf('const FlyBrain = (() => {'),
                                 script.indexOf('const SUBNET ='));
  const subnetAt = script.indexOf('const SUBNET =');
  const subnetSrc = script.slice(subnetAt, script.indexOf('\n', subnetAt));
  const ctx = { atob: b => Buffer.from(b, 'base64').toString('binary'), module: {}, console };
  vm.createContext(ctx);
  vm.runInContext(engineSrc + '\n' + subnetSrc + '\nthis.__net = FlyBrain.decodeNet(SUBNET);' +
                  '\nthis.__FB = FlyBrain;', ctx);
  const FB = ctx.__FB, net = ctx.__net;
  check('network decodes', net.n === 4000 && net.indices.length === 387060,
        `${net.n} neurons, ${net.indices.length} synapses`);

  const brain = new FB.Brain(net, 7);
  brain.setStim(net.groups.sugar, 100);
  brain.runSteps(2000);
  brain.spikes.fill(0);
  const t0 = Date.now();
  brain.runSteps(5000);
  const rt = 0.5 / ((Date.now() - t0) / 1000);
  const mn9Sugar = brain.spikes[net.groups.mn9[0]] / 0.5;
  check('sugar makes MN9 fire', mn9Sugar > 30, `${mn9Sugar} Hz  (realtime x${rt.toFixed(2)})`);

  const b2 = new FB.Brain(net, 7);
  b2.setStim(net.groups.sugar, 100);
  b2.setStim(net.groups.bitter, 100);
  b2.runSteps(2000);
  b2.spikes.fill(0);
  b2.runSteps(5000);
  const mn9Both = b2.spikes[net.groups.mn9[0]] / 0.5;
  check('bitter suppresses feeding', mn9Both === 0, `${mn9Both} Hz`);
  // speed is reported, not asserted: it swings with CPU thermal state
  console.log(`  info  simulation speed  x${rt.toFixed(2)} realtime` +
              (rt < 0.5 ? '  (machine is throttling)' : ''));
} catch (e) {
  check('embedded engine runs', false, e.message);
}

process.exit(ok ? 0 : 1);
