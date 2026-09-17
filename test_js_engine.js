// Regression test: does the browser engine reproduce the Python results?
//
// Reference (engine.py on the same 4,000-neuron subnetwork, 100 Hz):
//     sugar          -> MN9  78 Hz
//     sugar + bitter -> MN9   0 Hz
// Whole brain (sim.py, 30 trials): MN9 80.6 Hz / 0.0 Hz
//
// Usage: node test_js_engine.js

const fs = require('fs');
const path = require('path');
const FB = require('./flybrain.js');

const json = JSON.parse(fs.readFileSync(path.join(__dirname, 'subnet.json'), 'utf8'));
const net = FB.decodeNet(json);
console.log(`network: ${net.n.toLocaleString()} neurons, ` +
            `${net.indices.length.toLocaleString()} synapses`);

function run(label, stims, seed) {
  const brain = new FB.Brain(net, seed);
  for (const [group, hz] of Object.entries(stims)) brain.setStim(net.groups[group], hz);
  brain.runSteps(2000);                       // 200 ms settle
  brain.spikes.fill(0);
  const t0 = Date.now();
  const fired = brain.runSteps(5000);         // 500 ms measured
  const wall = (Date.now() - t0) / 1000;
  const mn9 = brain.spikes[net.groups.mn9[0]] / 0.5;
  console.log(`  ${label.padEnd(14)} MN9 ${mn9.toFixed(1).padStart(6)} Hz   ` +
              `total ${(fired / 0.5).toFixed(0).padStart(6)} spk/s   ` +
              `realtime x${(0.5 / wall).toFixed(2)}`);
  return mn9;
}

console.log('\nseed 1:');
const sugar1 = run('sugar', { sugar: 100 }, 1);
const both1 = run('sugar+bitter', { sugar: 100, bitter: 100 }, 1);
console.log('seed 2:');
const sugar2 = run('sugar', { sugar: 100 }, 2);
const both2 = run('sugar+bitter', { sugar: 100, bitter: 100 }, 2);

const sugarAvg = (sugar1 + sugar2) / 2;
let ok = true;
console.log('\nchecks:');
const check = (name, pass, detail) => {
  console.log(`  ${pass ? 'PASS' : 'FAIL'}  ${name}  ${detail}`);
  ok = ok && pass;
};
check('sugar drives MN9 near the Python result (78 Hz +/- 25%)',
      sugarAvg > 58 && sugarAvg < 98, `got ${sugarAvg.toFixed(1)} Hz`);
check('bitter fully suppresses feeding', both1 === 0 && both2 === 0,
      `got ${both1} / ${both2} Hz`);

process.exit(ok ? 0 : 1);
