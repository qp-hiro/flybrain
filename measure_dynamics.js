// Measure the two things a game built on this circuit needs to know:
//   1. the truth table of taste -> MN9 (what the circuit computes)
//   2. the step response: how long after a taste change does MN9 react
//
// Usage: node measure_dynamics.js

const fs = require('fs');
const path = require('path');
const FB = require('./flybrain.js');

const json = JSON.parse(fs.readFileSync(path.join(__dirname, 'subnet.json'), 'utf8'));
const net = FB.decodeNet(json);
const MN9 = net.groups.mn9[0];

function rate(sugar, bitter, seed, settleMs = 300, measureMs = 700) {
  const b = new FB.Brain(net, seed);
  b.setStim(net.groups.sugar, sugar);
  b.setStim(net.groups.bitter, bitter);
  b.runSteps(settleMs * 10);
  b.spikes.fill(0);
  b.runSteps(measureMs * 10);
  return b.spikes[MN9] / (measureMs / 1000);
}

console.log('=== truth table: MN9 output for each taste combination ===');
console.log('   sugar   bitter |  MN9 (Hz, mean of 5 seeds)   digital');
for (const [s, t] of [[0, 0], [120, 0], [0, 120], [120, 120]]) {
  let sum = 0;
  for (let k = 1; k <= 5; k++) sum += rate(s, t, k);
  const hz = sum / 5;
  console.log(`   ${String(s).padStart(5)}   ${String(t).padStart(6)} | ` +
              `${hz.toFixed(1).padStart(8)}                ${hz > 20 ? '1' : '0'}`);
}

console.log('\n=== step response: sugar switched on at t=0 ===');
// bin MN9 spikes in 5 ms windows after switching sugar on
const BIN = 5, NBINS = 40, acc = new Float64Array(NBINS);
const TRIALS = 12;
for (let k = 1; k <= TRIALS; k++) {
  const b = new FB.Brain(net, 100 + k);
  b.runSteps(1000);                       // 100 ms of silence
  b.setStim(net.groups.sugar, 120);
  for (let i = 0; i < NBINS; i++) {
    b.spikes.fill(0);
    b.runSteps(BIN * 10);
    acc[i] += b.spikes[MN9];
  }
}
let onset = -1, first = -1;
for (let i = 0; i < NBINS; i++) {
  const hz = acc[i] / TRIALS / (BIN / 1000);
  if (first < 0 && hz > 0) first = i * BIN;
  if (onset < 0 && hz > 20) onset = i * BIN;
}
const bars = [];
for (let i = 0; i < 16; i++) {
  const hz = acc[i] / TRIALS / (BIN / 1000);
  bars.push(`  ${String(i*BIN).padStart(3)}-${String(i*BIN+BIN).padStart(3)} ms ` +
            `${hz.toFixed(0).padStart(4)} Hz ${'#'.repeat(Math.round(hz / 4))}`);
}
console.log(bars.join('\n'));
console.log(`\n  first MN9 spike:        ${first} ms after sugar onset`);
console.log(`  crosses 20 Hz:          ${onset} ms`);

console.log('\n=== release: sugar switched off after a steady 120 Hz ===');
const accOff = new Float64Array(NBINS);
for (let k = 1; k <= TRIALS; k++) {
  const b = new FB.Brain(net, 200 + k);
  b.setStim(net.groups.sugar, 120);
  b.runSteps(3000);
  b.setStim(net.groups.sugar, 0);
  for (let i = 0; i < NBINS; i++) {
    b.spikes.fill(0);
    b.runSteps(BIN * 10);
    accOff[i] += b.spikes[MN9];
  }
}
let off = -1;
for (let i = 0; i < NBINS; i++) {
  const hz = accOff[i] / TRIALS / (BIN / 1000);
  if (off < 0 && hz < 20) off = i * BIN;
}
console.log(`  drops below 20 Hz:      ${off} ms after sugar is removed`);

console.log('\n=== bitter veto speed: bitter added on top of steady sugar ===');
const accVeto = new Float64Array(NBINS);
for (let k = 1; k <= TRIALS; k++) {
  const b = new FB.Brain(net, 300 + k);
  b.setStim(net.groups.sugar, 120);
  b.runSteps(3000);
  b.setStim(net.groups.bitter, 120);
  for (let i = 0; i < NBINS; i++) {
    b.spikes.fill(0);
    b.runSteps(BIN * 10);
    accVeto[i] += b.spikes[MN9];
  }
}
let veto = -1;
for (let i = 0; i < NBINS; i++) {
  const hz = accVeto[i] / TRIALS / (BIN / 1000);
  if (veto < 0 && hz < 20) veto = i * BIN;
}
console.log(`  MN9 silenced within:    ${veto} ms after bitter arrives`);
