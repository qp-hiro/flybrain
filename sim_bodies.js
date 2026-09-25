// Same brain, different bodies -- measured, not asserted.
//
// Runs the exact body physics of docs/robot.html headlessly for a set of body
// designs and reports how much food each one finds. Writes bodies.json, which
// the page then displays, so the table on the page is measurement.
//
// Usage: node sim_bodies.js [--seconds 40] [--worlds 2]

const fs = require('fs');
const path = require('path');
const FB = require('./flybrain.js');

const args = process.argv.slice(2);
const argOf = (k, d) => { const i = args.indexOf(k); return i < 0 ? d : +args[i + 1]; };
const SECONDS = argOf('--seconds', 40);
const WORLDS = argOf('--worlds', 2);
const DT = 1 / 30;                     // the page steps at roughly 30 fps

const net = FB.decodeNet(JSON.parse(
  fs.readFileSync(path.join(__dirname, 'robotnet.json'), 'utf8')));
const G = net.groups;

// ---- the selective motor tap, chosen the same way the page chooses it ----
function probe(grp) {
  const b = new FB.Brain(net, 7);
  b.setStim(G[grp], 150);
  b.runSteps(1500);
  b.spikes.fill(0);
  b.runSteps(3000);
  return b.spikes;
}
const sl = probe('sugarL'), sr = probe('sugarR');
let tapL = G.dnL.filter(i => sr[i] - sl[i] < -2);
let tapR = G.dnR.filter(i => sr[i] - sl[i] > 2);
if (tapL.length < 3) tapL = G.dnL.slice();
if (tapR.length < 3) tapR = G.dnR.slice();
console.log(`selective tap: ${tapL.length} left / ${tapR.length} right descending neurons ` +
            `(of ${G.dnL.length}/${G.dnR.length})`);

// ---- world ----
function rngOf(seed) {
  let s = seed >>> 0 || 1;
  return () => { s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
}
function makeWorld(seed) {
  const R = rngOf(seed);
  const patches = [];
  const mk = kind => ({ kind, x: .08 + R() * .84, y: .08 + R() * .84,
                        r: kind === 'sugar' ? .085 + R() * .04 : .075 + R() * .03, amount: 1 });
  for (let i = 0; i < 7; i++) patches.push(mk('sugar'));
  for (let i = 0; i < 4; i++) patches.push(mk('poison'));
  return { patches, robot: { x: .5, y: .5, th: R() * 6.283 }, mk, R };
}
const wrap = v => v - Math.floor(v);
function dwrap(a, b) { let d = a - b; if (d > .5) d -= 1; else if (d < -.5) d += 1; return d; }
function sense(w, x, y, kind) {
  let c = 0;
  for (const p of w.patches) {
    if (p.kind !== kind || p.amount <= 0) continue;
    const d = Math.hypot(dwrap(x, p.x), dwrap(y, p.y));
    if (d < p.r * 2.2) c = Math.max(c, p.amount * Math.exp(-1.4 * (d / p.r) ** 2));
  }
  return Math.min(1, c);
}

// ---- one run ----
function run(body, seed) {
  const w = makeWorld(seed);
  const brain = new FB.Brain(net, seed * 31 + 7);
  const noise = rngOf(seed * 7 + 3);
  let dnL = 0, dnR = 0, mn9 = 0, food = 0, poison = 0, dist = 0;
  let onSugar = 0, onPoison = 0;      // mean concentration under the robot
  const r = w.robot;
  const steps = Math.round(SECONDS / DT);

  for (let s = 0; s < steps; s++) {
    const half = body.sep / 200, cs = Math.cos(r.th), sn = Math.sin(r.th);
    const ax = wrap(r.x - sn * half), ay = wrap(r.y + cs * half);
    const bx = wrap(r.x + sn * half), by = wrap(r.y - cs * half);
    brain.setStim(G.sugarL, sense(w, ax, ay, 'sugar') * 200);
    brain.setStim(G.sugarR, sense(w, bx, by, 'sugar') * 200);
    brain.setStim(G.bitterL, sense(w, ax, ay, 'poison') * 200);
    brain.setStim(G.bitterR, sense(w, bx, by, 'poison') * 200);

    const n = Math.round(DT * 10000);
    brain.runSteps(n);
    const simSec = n * 1e-4;
    const setL = body.tap === 'all' ? G.dnL : tapL;
    const setR = body.tap === 'all' ? G.dnR : tapR;
    const sum = arr => arr.reduce((a, i) => a + brain.spikes[i], 0);
    const rawL = sum(setL) / simSec / setL.length;
    const rawR = sum(setR) / simSec / setR.length;
    const m = brain.spikes[G.mn9[0]] / simSec;
    brain.spikes.fill(0);
    dnL = dnL * .75 + rawL * .25;
    dnR = dnR * .75 + rawR * .25;
    mn9 = mn9 * .75 + m * .25;

    // the null control: wheels get drive of the same average size, but it
    // carries no information about where the food is
    let driveL = body.wiring === 'crossed' ? dnR : dnL;
    let driveR = body.wiring === 'crossed' ? dnL : dnR;
    if (body.mode === 'null') {
      const m = (dnL + dnR) / 2;
      driveL = m * (0.5 + noise()); driveR = m * (0.5 + noise());
    }
    // polarity is a property of the chassis, not the brain: does descending
    // activity speed a wheel up, or slow it down?
    const k = body.gain / 1600;
    const b0 = body.base / 900;
    const sign = body.polarity === 'inhibit' ? -1 : 1;
    const wl = Math.max(0, b0 + sign * k * driveL);
    const wr = Math.max(0, b0 + sign * k * driveR);
    const v = (wl + wr) / 2;
    r.th += ((wr - wl) / Math.max(.02, body.wheel / 100)) * DT;
    r.x = wrap(r.x + Math.cos(r.th) * v * DT);
    r.y = wrap(r.y + Math.sin(r.th) * v * DT);
    dist += v * DT;
    onSugar += sense(w, r.x, r.y, 'sugar') / steps;
    onPoison += sense(w, r.x, r.y, 'poison') / steps;

    for (const p of w.patches) {
      if (p.amount <= 0) continue;
      const d = Math.hypot(dwrap(r.x, p.x), dwrap(r.y, p.y));
      if (d > p.r * .8) continue;
      if (p.kind === 'poison') { poison += DT; continue; }
      if (mn9 > 30) {
        const take = Math.min(p.amount, DT * .6);
        p.amount -= take; food += take * 10;
        if (p.amount <= 0) Object.assign(p, w.mk('sugar'));
      }
    }
  }
  return { food, poison, dist, onSugar, onPoison };
}

const BASE = { wiring: 'crossed', sep: 18, gain: 16, base: 12, wheel: 8,
               tap: 'select', mode: 'brain', polarity: 'excite' };
const BODIES = [
  { name: '加速・交差',      note: '餌で加速、左脳→右輪',   body: { ...BASE } },
  { name: '加速・非交差',    note: '餌で加速、左脳→左輪',   body: { ...BASE, wiring: 'straight' } },
  { name: '減速・交差',      note: '餌で減速、左脳→右輪',
    body: { ...BASE, polarity: 'inhibit', base: 26, gain: 20 } },
  { name: '減速・非交差',    note: '餌で減速、左脳→左輪',
    body: { ...BASE, polarity: 'inhibit', wiring: 'straight', base: 26, gain: 20 } },
  { name: '減速・触角が広い', note: '餌で減速、間隔 28%',
    body: { ...BASE, polarity: 'inhibit', sep: 28, base: 26, gain: 20 } },
  { name: '減速・触角が近い', note: '餌で減速、間隔 2%',
    body: { ...BASE, polarity: 'inhibit', sep: 2, base: 26, gain: 20 } },
  { name: '触角が広い(加速)', note: '間隔 28%',            body: { ...BASE, sep: 28 } },
  { name: '端子は全下行N',   note: '322個を平均',          body: { ...BASE, tap: 'all' } },
  { name: '対照：操縦なし',  note: '前進のみ',             body: { ...BASE, gain: 0, base: 20 } },
  { name: '対照：脳を使わない', note: '同じ平均速度の雑音',  body: { ...BASE, mode: 'null' } },
];

console.log(`\n${SECONDS}s per run, ${WORLDS} worlds each`);
console.log('"砂糖の上" = 走行中に体が浴びた砂糖濃度の平均（走性の指標）\n');
console.log(`${'body'.padEnd(22)} ${'砂糖の上'.padStart(9)} ${'毒の上'.padStart(8)} ` +
            `${'food'.padStart(6)} ${'travel'.padStart(7)}`);
const out = [];
for (const b of BODIES) {
  const acc = { food: 0, poison: 0, dist: 0, onSugar: 0, onPoison: 0 };
  for (let k = 0; k < WORLDS; k++) {
    const r = run(b.body, 101 + k * 977);
    for (const key of Object.keys(acc)) acc[key] += r[key] / WORLDS;
  }
  console.log(`${b.name.padEnd(22)} ${acc.onSugar.toFixed(3).padStart(9)} ` +
              `${acc.onPoison.toFixed(3).padStart(8)} ${acc.food.toFixed(1).padStart(6)} ` +
              `${acc.dist.toFixed(2).padStart(7)}`);
  out.push({ name: b.name, note: b.note,
             onSugar: +acc.onSugar.toFixed(3), onPoison: +acc.onPoison.toFixed(3),
             food: +acc.food.toFixed(1), dist: +acc.dist.toFixed(2) });
}

fs.writeFileSync(path.join(__dirname, 'bodies.json'), JSON.stringify(
  { seconds: SECONDS, worlds: WORLDS, tap: { left: tapL.length, right: tapR.length },
    results: out }, null, 0));
console.log('\nwrote bodies.json');
