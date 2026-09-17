// Can we compute with fly brains?
//
// The feeding circuit computes  MN9 = sugar AND NOT bitter  (NIMPLY).
// NIMPLY plus a constant TRUE is functionally complete, so a network of
// fly brains can evaluate any boolean function. This builds a half adder
// out of seven independent fly brains and checks its truth table.
//
//   g1 = A NIMPLY B          g2 = B NIMPLY A          g6 = 1 NIMPLY B  (NOT B)
//   g3 = 1 NIMPLY g1         g7 = A NIMPLY g6         (= A AND B = CARRY)
//   g4 = g3 NIMPLY g2        (= NOR(g1,g2))
//   g5 = 1 NIMPLY g4         (= OR(g1,g2) = XOR(A,B) = SUM)
//
// Usage: node test_adder.js

const fs = require('fs');
const path = require('path');
const FB = require('./flybrain.js');

const json = JSON.parse(fs.readFileSync(path.join(__dirname, 'subnet.json'), 'utf8'));
const net = FB.decodeNet(json);
const MN9 = net.groups.mn9[0];

const ON = 120;            // Hz delivered for a logical 1
const THRESH = 20;         // Hz above which MN9 counts as a logical 1
const SETTLE_MS = 120;     // let the circuit reach steady state
const READ_MS = 200;       // then count spikes

let seedCounter = 0;

// one fly brain evaluating  p AND NOT q
function nimply(p, q) {
  const brain = new FB.Brain(net, ++seedCounter * 7919);
  brain.setStim(net.groups.sugar, p ? ON : 0);
  brain.setStim(net.groups.bitter, q ? ON : 0);
  brain.runSteps(SETTLE_MS * 10);
  brain.spikes.fill(0);
  brain.runSteps(READ_MS * 10);
  const hz = brain.spikes[MN9] / (READ_MS / 1000);
  return { bit: hz > THRESH, hz };
}

function halfAdder(A, B) {
  const g1 = nimply(A, B);            // A AND NOT B
  const g2 = nimply(B, A);            // B AND NOT A
  const g6 = nimply(true, B);         // NOT B
  const g3 = nimply(true, g1.bit);    // NOT g1
  const g7 = nimply(A, g6.bit);       // A AND B          -> CARRY
  const g4 = nimply(g3.bit, g2.bit);  // NOR(g1, g2)
  const g5 = nimply(true, g4.bit);    // OR(g1, g2) = XOR -> SUM
  return { sum: g5, carry: g7, gates: [g1, g2, g6, g3, g7, g4, g5] };
}

console.log(`one gate = ${net.n.toLocaleString()} neurons / ` +
            `${net.indices.length.toLocaleString()} synapses`);
console.log(`half adder = 7 gates = ${(net.n * 7).toLocaleString()} neurons / ` +
            `${(net.indices.length * 7).toLocaleString()} synapses\n`);

console.log('  A  B | SUM CARRY | expected | MN9 Hz (sum / carry)');
let ok = true;
for (const [A, B] of [[0, 0], [1, 0], [0, 1], [1, 1]]) {
  const r = halfAdder(!!A, !!B);
  const sum = r.sum.bit ? 1 : 0, carry = r.carry.bit ? 1 : 0;
  const expSum = A ^ B, expCarry = A & B;
  const pass = sum === expSum && carry === expCarry;
  ok = ok && pass;
  console.log(`  ${A}  ${B} |  ${sum}    ${carry}   |   ${expSum} ${expCarry}    | ` +
              `${r.sum.hz.toFixed(0).padStart(4)} / ${r.carry.hz.toFixed(0).padStart(4)}` +
              `   ${pass ? 'ok' : 'MISMATCH'}`);
}

console.log(`\n1 + 1 = ${(() => { const r = halfAdder(true, true);
  return `${r.carry.bit ? 1 : 0}${r.sum.bit ? 1 : 0}`; })()} (binary)`);
console.log(ok ? '\nPASS: seven fly brains implement a half adder'
               : '\nFAIL: truth table mismatch');
process.exit(ok ? 0 : 1);
