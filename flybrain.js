// Leaky integrate-and-fire engine for the Drosophila feeding subnetwork.
// Faithful port of sim.py / engine.py -- same constants, same update order,
// so the browser reproduces the Python (and thus the Brian2) results.
// Runs in the browser and in Node (for the numerical regression test).

const FlyBrain = (() => {
  const DT = 1e-4;        // s, integration step
  const V_0 = -52, V_RST = -52, V_TH = -45;   // mV
  const T_MBR = 20e-3, TAU = 5e-3;            // s
  const RFC_STEPS = 22;   // 2.2 ms refractory
  const DLY_STEPS = 18;   // 1.8 ms synaptic delay
  const W_SYN = 0.275;    // mV per synapse
  const F_POI = 250;      // stimulation scaling

  const B = Math.exp(-DT / T_MBR);
  const A = Math.exp(-DT / TAU);
  const C = TAU / (TAU - T_MBR) * (Math.exp(-DT / TAU) - Math.exp(-DT / T_MBR));
  const W_POI = W_SYN * F_POI;

  function b64ToBytes(b64) {
    if (typeof Buffer !== 'undefined') return new Uint8Array(Buffer.from(b64, 'base64'));
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function decodeNet(json) {
    const bytes = k => b64ToBytes(json[k]).buffer;
    return {
      n: json.meta.n,
      indptr: new Int32Array(bytes('indptr')),
      indices: new Uint16Array(bytes('indices')),
      syn: new Int16Array(bytes('syn')),
      meta: json.meta, pos: json.pos, nt: json.nt,
      type: json.type, cls: json.cls, groups: json.groups,
    };
  }

  // xorshift128+ so tests are reproducible; seed from Math.random in the browser
  function makeRng(seed) {
    let s0 = seed >>> 0 || 1, s1 = (seed * 2654435761) >>> 0 || 2;
    return () => {
      let x = s0, y = s1;
      s0 = y;
      x ^= x << 23; x >>>= 0;
      x ^= x >>> 17;
      x ^= y ^ (y >>> 26);
      s1 = x >>> 0;
      return ((s0 + s1) >>> 0) / 4294967296;
    };
  }

  class Brain {
    constructor(net, seed) {
      this.net = net;
      const n = this.n = net.n;
      this.v = new Float32Array(n).fill(V_0);
      this.g = new Float32Array(n);
      this.rfc = new Int32Array(n);
      this.nonref = new Uint8Array(n);
      this.buf = new Float32Array(DLY_STEPS * n);
      this.stimP = new Float32Array(n);      // per-step event probability
      this.spikes = new Int32Array(n);       // spike counter, caller may reset
      this.silenced = new Uint8Array(n);     // 1 = spikes, but transmits nothing
      this.step = 0;
      this.rand = makeRng(seed === undefined ? (Math.random() * 2 ** 31) | 0 : seed);
    }

    // rate in Hz; 0 stops stimulation
    setStim(indices, rateHz) {
      const p = rateHz > 0 ? 1 - Math.exp(-rateHz * DT) : 0;
      for (const i of indices) this.stimP[i] = p;
      this._stimList = null;
    }

    // silence neurons: they still fire, but their outgoing synapses deliver
    // nothing -- the same operation as sim.py --silence
    silence(indices) {
      for (const i of indices) this.silenced[i] = 1;
    }
    clearSilence() { this.silenced.fill(0); }

    _stim() {
      if (!this._stimList) {
        const list = [];
        for (let i = 0; i < this.n; i++) if (this.stimP[i] > 0) list.push(i);
        this._stimList = new Int32Array(list);
      }
      return this._stimList;
    }

    runSteps(nSteps) {
      const { n, v, g, rfc, nonref, buf, stimP, spikes, silenced } = this;
      const { indptr, indices, syn } = this.net;
      const stim = this._stim();
      const rand = this.rand;
      let fired = 0;

      for (let s = 0; s < nSteps; s++) {
        const base = (this.step % DLY_STEPS) * n;

        for (let i = 0; i < n; i++) {
          g[i] += buf[base + i];
          buf[base + i] = 0;
          if (rfc[i] <= 0) {
            nonref[i] = 1;
            v[i] = V_0 + (v[i] - V_0) * B + g[i] * C;
            g[i] *= A;
          } else {
            nonref[i] = 0;
            rfc[i]--;
          }
        }

        for (let k = 0; k < stim.length; k++) {
          const i = stim[k];
          if (rand() < stimP[i]) v[i] += W_POI;
        }

        for (let i = 0; i < n; i++) {
          if (!nonref[i] || v[i] <= V_TH) continue;
          if (!silenced[i]) {
            for (let p = indptr[i], e = indptr[i + 1]; p < e; p++) {
              buf[base + indices[p]] += syn[p] * W_SYN;
            }
          }
          v[i] = V_RST;
          g[i] = 0;
          rfc[i] = stimP[i] > 0 ? 0 : RFC_STEPS;
          spikes[i]++;
          fired++;
        }
        this.step++;
      }
      return fired;
    }

    get simMs() { return this.step * DT * 1000; }
  }

  return { Brain, decodeNet, DT, DLY_STEPS, RFC_STEPS, V_TH, V_0, W_SYN };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = FlyBrain;
