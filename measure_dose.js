// Dose-response: at what sugar concentration does the circuit decide to eat?
// And how much bitter is needed to veto a strong sugar signal?
// Usage: node measure_dose.js

const fs = require('fs');
const path = require('path');
const FB = require('./flybrain.js');

const net = FB.decodeNet(JSON.parse(
  fs.readFileSync(path.join(__dirname, 'subnet.json'), 'utf8')));
const MN9 = net.groups.mn9[0];

function mn9(sugar, bitter, seed) {
  const b = new FB.Brain(net, seed);
  b.setStim(net.groups.sugar, sugar);
  b.setStim(net.groups.bitter, bitter);
  b.runSteps(2000);
  b.spikes.fill(0);
  b.runSteps(5000);
  return b.spikes[MN9] / 0.5;
}
const avg = (s, t) => {
  let v = 0;
  for (let k = 1; k <= 4; k++) v += mn9(s, t, k * 31);
  return v / 4;
};

console.log('sugar dose -> MN9 (no bitter)');
for (const s of [0, 10, 20, 30, 40, 50, 60, 80, 100, 150, 200]) {
  const hz = avg(s, 0);
  console.log(`  ${String(s).padStart(3)} Hz -> ${hz.toFixed(1).padStart(6)} Hz  ` +
              '#'.repeat(Math.round(hz / 4)));
}

console.log('\nbitter needed to veto sugar 150 Hz');
for (const t of [0, 10, 20, 30, 50, 80, 120]) {
  const hz = avg(150, t);
  console.log(`  bitter ${String(t).padStart(3)} Hz -> MN9 ${hz.toFixed(1).padStart(6)} Hz  ` +
              '#'.repeat(Math.round(hz / 4)));
}
