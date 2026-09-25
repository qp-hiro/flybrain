// What exposure would a body get purely by chance?
// Samples the same worlds sim_bodies.js used, at random positions, so the
// body scores can be read against a baseline instead of in a vacuum.
// Usage: node chance_level.js

const fs = require('fs');
const path = require('path');

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
  return patches;
}
function dwrap(a, b) { let d = a - b; if (d > .5) d -= 1; else if (d < -.5) d += 1; return d; }
function sense(patches, x, y, kind) {
  let c = 0;
  for (const p of patches) {
    if (p.kind !== kind) continue;
    const d = Math.hypot(dwrap(x, p.x), dwrap(y, p.y));
    if (d < p.r * 2.2) c = Math.max(c, Math.exp(-1.4 * (d / p.r) ** 2));
  }
  return Math.min(1, c);
}

const R = rngOf(4242);
let sugar = 0, poison = 0, n = 0;
for (let k = 0; k < 3; k++) {
  const patches = makeWorld(101 + k * 977);
  for (let i = 0; i < 200000; i++) {
    const x = R(), y = R();
    sugar += sense(patches, x, y, 'sugar');
    poison += sense(patches, x, y, 'poison');
    n++;
  }
}
const chance = { onSugar: +(sugar / n).toFixed(3), onPoison: +(poison / n).toFixed(3) };
console.log('chance level (uniformly random position in the same worlds):');
console.log(`  sugar  ${chance.onSugar}`);
console.log(`  poison ${chance.onPoison}`);

const p = path.join(__dirname, 'bodies.json');
const data = JSON.parse(fs.readFileSync(p, 'utf8'));
data.chance = chance;
fs.writeFileSync(p, JSON.stringify(data));
console.log('\nadded to bodies.json');
console.log(`\n${'body'.padEnd(22)} ${'sugar'.padStart(7)} ${'vs chance'.padStart(10)} ` +
            `${'poison'.padStart(7)} ${'vs chance'.padStart(10)}`);
for (const r of data.results) {
  console.log(`${r.name.padEnd(22)} ${r.onSugar.toFixed(3).padStart(7)} ` +
              `${(r.onSugar / chance.onSugar).toFixed(2).padStart(9)}x ` +
              `${r.onPoison.toFixed(3).padStart(7)} ` +
              `${(r.onPoison / chance.onPoison).toFixed(2).padStart(9)}x`);
}
