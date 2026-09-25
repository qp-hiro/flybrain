// An experiment that cannot be done in a living fly.
//
// Silence one neuron at a time and re-run the whole feeding circuit. Two
// questions, each impossible without a connectome:
//
//   A) sugar alone      -> which single neuron, if removed, abolishes feeding?
//                          which one is a brake (removing it feeds harder)?
//   B) sugar + bitter   -> which single neuron, if removed, makes the fly eat
//                          poison? i.e. who carries the bitter veto?
//
// Only neurons that actually fire can matter, so the screen covers exactly the
// neurons active in each condition -- that makes it exhaustive, not a sample.
//
// Usage: node screen.js [--seeds 3] [--out screen.json]

const fs = require('fs');
const path = require('path');
const FB = require('./flybrain.js');

const args = process.argv.slice(2);
const argOf = (k, d) => { const i = args.indexOf(k); return i < 0 ? d : args[i + 1]; };
const SEEDS = +argOf('--seeds', 3);
const OUT = argOf('--out', 'screen.json');

const net = FB.decodeNet(JSON.parse(
  fs.readFileSync(path.join(__dirname, 'subnet.json'), 'utf8')));
const MN9 = net.groups.mn9[0];
const SETTLE = 1500, READ = 5000;          // 150 ms settle, 500 ms measured
const ON = 150;

function run(stims, silenceIdx, seed) {
  const b = new FB.Brain(net, seed);
  for (const [grp, hz] of stims) b.setStim(net.groups[grp], hz);
  if (silenceIdx >= 0) b.silence([silenceIdx]);
  b.runSteps(SETTLE);
  b.spikes.fill(0);
  b.runSteps(READ);
  return b;
}
function mn9Of(stims, silenceIdx, seeds) {
  let sum = 0;
  for (let k = 0; k < seeds; k++) sum += run(stims, silenceIdx, 1000 + k * 977).spikes[MN9];
  return sum / seeds / (READ * 1e-4);
}
function activeIn(stims) {
  const b = run(stims, -1, 1000);
  const list = [];
  for (let i = 0; i < net.n; i++) if (b.spikes[i] > 0) list.push(i);
  return list;
}

function screen(label, stims, seeds) {
  const baseline = mn9Of(stims, -1, seeds);
  const cand = activeIn(stims);
  console.error(`[${label}] baseline MN9 ${baseline.toFixed(1)} Hz, ` +
                `${cand.length} active neurons to test`);
  const t0 = Date.now();
  const rows = [];
  cand.forEach((i, k) => {
    const hz = mn9Of(stims, i, seeds);
    rows.push({ i, hz, delta: hz - baseline });
    if ((k + 1) % 25 === 0) {
      const per = (Date.now() - t0) / (k + 1);
      console.error(`  ${k + 1}/${cand.length}  eta ${((cand.length - k - 1) * per / 1000)
        .toFixed(0)}s`);
    }
  });
  rows.sort((a, b) => a.delta - b.delta);
  return { baseline, rows };
}

const info = i => ({
  i,
  type: net.type[i] || '(未命名)',
  cls: net.cls[i] || '?',
  nt: net.nt[i] || '?',
});

console.error(`screening ${net.n.toLocaleString()} neurons, ${SEEDS} seeds each`);

const A = screen('sugar', [['sugar', ON], ['bitter', 0]], SEEDS);
const B = screen('sugar+bitter', [['sugar', ON], ['bitter', ON]], SEEDS);

const show = (title, rows, baseline, n = 12, dir = 1) => {
  console.log(`\n=== ${title} (baseline ${baseline.toFixed(1)} Hz) ===`);
  const sorted = dir > 0 ? rows.slice(-n).reverse() : rows.slice(0, n);
  console.log('   MN9 Hz   delta   cell type         class          nt');
  for (const r of sorted) {
    const m = info(r.i);
    console.log(`  ${r.hz.toFixed(1).padStart(6)}  ${(r.delta >= 0 ? '+' : '') +
      r.delta.toFixed(1).padStart(6)}   ${m.type.padEnd(16)}  ${m.cls.padEnd(13)}  ${m.nt}`);
  }
};

show('A: 沈黙させると摂食が止まるニューロン（必須）', A.rows, A.baseline, 12, -1);
show('A: 沈黙させると摂食が強まるニューロン（ブレーキ）', A.rows, A.baseline, 12, 1);
show('B: 沈黙させると毒を食べるようになるニューロン（苦味の拒否権）',
     B.rows, B.baseline, 15, 1);

fs.writeFileSync(path.join(__dirname, OUT), JSON.stringify({
  meta: { seeds: SEEDS, settle_ms: SETTLE / 10, read_ms: READ / 10, stim_hz: ON,
          n_neurons: net.n },
  sugar: { baseline: A.baseline, rows: A.rows.map(r => ({ ...r, ...info(r.i) })) },
  sugarBitter: { baseline: B.baseline, rows: B.rows.map(r => ({ ...r, ...info(r.i) })) },
}));
console.error(`\nwrote ${OUT}`);
