// A screen at the level a real fly experiment can actually reach.
//
// In a living fly you silence a *cell type* (a GAL4 driver line hits every
// neuron of that type), not one cell. So this screens cell types, and then
// searches greedily for the smallest set of types whose removal makes the
// fly eat poison -- a lesion the wet lab could go and try.
//
// Sensory neurons are excluded from the search: switching off the bitter
// receptors is the trivial answer (the fly simply cannot taste the poison).
// The interesting question is whether a *central* switch exists.
//
// Usage: node screen_types.js [--seeds 2] [--rounds 6]

const fs = require('fs');
const path = require('path');
const FB = require('./flybrain.js');

const args = process.argv.slice(2);
const argOf = (k, d) => { const i = args.indexOf(k); return i < 0 ? d : args[i + 1]; };
const SEEDS = +argOf('--seeds', 2);
const ROUNDS = +argOf('--rounds', 6);

const net = FB.decodeNet(JSON.parse(
  fs.readFileSync(path.join(__dirname, 'subnet.json'), 'utf8')));
const MN9 = net.groups.mn9[0];
const SETTLE = 1500, READ = 5000, ON = 150;
const EAT = 30;                        // MN9 Hz at which the proboscis extends

// group neurons by annotated cell type, skipping sensory input neurons
const byType = new Map();
for (let i = 0; i < net.n; i++) {
  const t = net.type[i];
  if (!t || net.cls[i] === 'sensory') continue;
  if (!byType.has(t)) byType.set(t, []);
  byType.get(t).push(i);
}

function mn9(stims, silenced, seeds) {
  let sum = 0;
  for (let k = 0; k < seeds; k++) {
    const b = new FB.Brain(net, 1000 + k * 977);
    for (const [g, hz] of stims) b.setStim(net.groups[g], hz);
    if (silenced.length) b.silence(silenced);
    b.runSteps(SETTLE);
    b.spikes.fill(0);
    b.runSteps(READ);
    sum += b.spikes[MN9];
  }
  return sum / seeds / (READ * 1e-4);
}
function activeTypes(silenced) {
  const b = new FB.Brain(net, 1000);
  b.setStim(net.groups.sugar, ON);
  b.setStim(net.groups.bitter, ON);
  if (silenced.length) b.silence(silenced);
  b.runSteps(SETTLE);
  b.spikes.fill(0);
  b.runSteps(READ);
  const live = new Set();
  for (const [t, idx] of byType) if (idx.some(i => b.spikes[i] > 0)) live.add(t);
  return live;
}

const POISON = [['sugar', ON], ['bitter', ON]];
console.log(`${byType.size} central cell types among ${net.n.toLocaleString()} neurons`);
console.log(`baseline (sugar+bitter): MN9 ${mn9(POISON, [], SEEDS).toFixed(1)} Hz ` +
            `-- the fly refuses\n`);

const chosen = [];       // types silenced so far
let silenced = [];
const history = [];

for (let round = 1; round <= ROUNDS; round++) {
  const live = activeTypes(silenced);
  const cands = [...byType.keys()].filter(t => !chosen.includes(t) && live.has(t));
  process.stderr.write(`round ${round}: testing ${cands.length} types ... `);
  const t0 = Date.now();

  let best = null;
  for (const t of cands) {
    const hz = mn9(POISON, silenced.concat(byType.get(t)), SEEDS);
    if (!best || hz > best.hz) best = { type: t, hz, n: byType.get(t).length };
  }
  console.error(`${((Date.now() - t0) / 1000).toFixed(0)}s`);
  if (!best) break;

  chosen.push(best.type);
  silenced = silenced.concat(byType.get(best.type));
  history.push({ round, ...best, cumulative: chosen.slice(), nSilenced: silenced.length });
  console.log(`  +${best.type.padEnd(12)} (${String(best.n).padStart(2)} neurons)  ` +
              `-> MN9 ${best.hz.toFixed(1).padStart(6)} Hz   ` +
              `[silenced ${silenced.length} neurons total]` +
              (best.hz > EAT ? '   <<< 毒を食べる' : ''));
  if (best.hz > EAT) break;
}

// does that same lesion leave normal feeding intact? a useful lesion must be
// specific: the fly should still eat plain sugar
const sugarOnly = [['sugar', ON], ['bitter', 0]];
const sugarIntact = mn9(sugarOnly, silenced, SEEDS);
const sugarBase = mn9(sugarOnly, [], SEEDS);
console.log(`\nspecificity check -- plain sugar with the same lesion:`);
console.log(`  intact brain  MN9 ${sugarBase.toFixed(1)} Hz`);
console.log(`  lesioned      MN9 ${sugarIntact.toFixed(1)} Hz`);

fs.writeFileSync(path.join(__dirname, 'screen_types.json'), JSON.stringify({
  meta: { seeds: SEEDS, eat_threshold: EAT, stim_hz: ON, n_types: byType.size },
  history,
  types: Object.fromEntries([...byType].map(([t, idx]) => [t, idx])),
  specificity: { sugar_intact: sugarBase, sugar_lesioned: sugarIntact },
}, null, 0));
console.error('\nwrote screen_types.json');
