// Does the robot subnetwork keep the steering signal the whole brain has?
//
// Whole brain (measure_steering.py, 2 trials, 150 Hz):
//   stimulate sugar LEFT  -> lateralisation index -0.154  (output leans left)
//   stimulate sugar RIGHT -> lateralisation index +0.155  (output leans right)
//
// Usage: node test_robotnet.js

const fs = require('fs');
const path = require('path');
const FB = require('./flybrain.js');

const net = FB.decodeNet(JSON.parse(
  fs.readFileSync(path.join(__dirname, 'robotnet.json'), 'utf8')));
const G = net.groups;
console.log(`network: ${net.n.toLocaleString()} neurons, ` +
            `${net.indices.length.toLocaleString()} synapses`);
console.log(`inputs  : sugar ${G.sugarL.length}L/${G.sugarR.length}R, ` +
            `bitter ${G.bitterL.length}L/${G.bitterR.length}R`);
console.log(`outputs : descending ${G.dnL.length}L/${G.dnR.length}R\n`);

const SETTLE = 1500, READ = 5000, ON = 150;

function run(stims, seed) {
  const b = new FB.Brain(net, seed);
  for (const [g, hz] of stims) b.setStim(G[g], hz);
  b.runSteps(SETTLE);
  b.spikes.fill(0);
  const t0 = Date.now();
  b.runSteps(READ);
  const wall = (Date.now() - t0) / 1000;
  const sum = g => G[g].reduce((a, i) => a + b.spikes[i], 0) / (READ * 1e-4);
  return { l: sum('dnL'), r: sum('dnR'), rt: (READ * 1e-4) / wall };
}
const avg = stims => {
  let l = 0, r = 0, rt = 0;
  for (let k = 0; k < 3; k++) {
    const o = run(stims, 500 + k * 131);
    l += o.l / 3; r += o.r / 3; rt += o.rt / 3;
  }
  return { l, r, rt, idx: (r - l) / (r + l || 1) };
};

let ok = true;
const check = (name, pass, detail) => {
  console.log(`  ${pass ? 'PASS' : 'FAIL'}  ${name}  ${detail}`);
  ok = ok && pass;
};

console.log('descending-neuron output by stimulated side:');
const L = avg([['sugarL', ON]]);
const R = avg([['sugarR', ON]]);
const none = avg([]);
console.log(`  sugar LEFT   DN left ${L.l.toFixed(0).padStart(5)} Hz  ` +
            `right ${L.r.toFixed(0).padStart(5)} Hz   index ${L.idx >= 0 ? '+' : ''}${L.idx.toFixed(3)}`);
console.log(`  sugar RIGHT  DN left ${R.l.toFixed(0).padStart(5)} Hz  ` +
            `right ${R.r.toFixed(0).padStart(5)} Hz   index ${R.idx >= 0 ? '+' : ''}${R.idx.toFixed(3)}`);
console.log(`  no stimulus  DN left ${none.l.toFixed(0).padStart(5)} Hz  ` +
            `right ${none.r.toFixed(0).padStart(5)} Hz`);

console.log('\nchecks:');
check('left taste leans the motor output left', L.idx < 0, `index ${L.idx.toFixed(3)}`);
check('right taste leans the motor output right', R.idx > 0, `index ${R.idx.toFixed(3)}`);
check('the two sides separate', R.idx - L.idx > 0.05,
      `separation ${(R.idx - L.idx).toFixed(3)} (whole brain: 0.309)`);
check('silent without stimulation', none.l + none.r === 0,
      `${(none.l + none.r).toFixed(0)} Hz`);
console.log(`  info  simulation speed x${L.rt.toFixed(2)} realtime`);

process.exit(ok ? 0 : 1);
