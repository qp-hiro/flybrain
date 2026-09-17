"""Whole-brain leaky integrate-and-fire simulation of the Drosophila connectome.

Pure NumPy/SciPy reimplementation of the Brian2 model from
Shiu et al. 2024 (https://github.com/philshiu/Drosophila_brain_model).
Model constants follow `model.py` of that repository exactly:

    dv/dt = (v_0 - v + g) / t_mbr   (unless refractory)
    dg/dt = -g / tau                (unless refractory)
    spike:  v > v_th  ->  v = v_rst, g = 0, refractory 2.2 ms
    synapse: g += w after 1.8 ms delay,  w = 0.275 mV x (signed synapse count)
    stimulation: Poisson events add w_syn * 250 directly to v, no refractory

Usage:
    python sim.py --rate 100 --trials 30 --name sugarR_100Hz_numpy
    python sim.py --stim sugar --stim2 bitter --rate2 100 --name sugar_vs_bitter
    python sim.py --silence type:MN9 --name no_mn9
"""

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from groups import MN9, SUGAR_GRNS, resolve

HERE = Path(__file__).parent

# model constants (identical to Shiu et al. default_params)
DT = 0.1e-3        # integration step [s] (Brian2 default)
T_RUN = 1.0        # trial duration [s]
V_0 = -52.0        # resting potential [mV]
V_RST = -52.0      # reset potential [mV]
V_TH = -45.0       # spike threshold [mV]
T_MBR = 20e-3      # membrane time constant [s]
TAU = 5e-3         # synaptic time constant [s]
T_RFC = 2.2e-3     # refractory period [s]
T_DLY = 1.8e-3     # synaptic delay [s]
W_SYN = 0.275      # weight per synapse [mV]
F_POI = 250        # scaling factor for Poisson events

RFC_STEPS = int(round(T_RFC / DT))   # 22
DLY_STEPS = int(round(T_DLY / DT))   # 18
N_STEPS = int(round(T_RUN / DT))     # 10000

def load_network():
    """Return (flywire ids as index array, CSR weight matrix [mV])."""
    comp = pd.read_csv(HERE / '2023_03_23_completeness_630_final.csv', index_col=0)
    flyids = comp.index.to_numpy(dtype=np.int64)
    n = len(flyids)

    con = pd.read_parquet(HERE / 'connectivity_630.parquet')
    w = sparse.csr_matrix(
        (con['Excitatory x Connectivity'].to_numpy(dtype=np.float32) * W_SYN,
         (con['Presynaptic_Index'].to_numpy(), con['Postsynaptic_Index'].to_numpy())),
        shape=(n, n),
    )
    return flyids, w


def silence(w, idx):
    """Zero every outgoing synapse of the given neurons (in place)."""
    for i in idx:
        w.data[w.indptr[i]:w.indptr[i + 1]] = 0.0


def run_trial(w, stim, rng):
    """Simulate one 1-second trial.

    stim: list of (neuron index array, stimulation rate in Hz) pairs.
    Returns (spike_step, spike_neuron) arrays.
    """
    n = w.shape[0]
    v = np.full(n, V_0, dtype=np.float32)
    g = np.zeros(n, dtype=np.float32)
    rfc = np.zeros(n, dtype=np.int32)          # remaining refractory steps
    buf = np.zeros((DLY_STEPS, n), dtype=np.float32)  # delayed g increments

    # exact one-step solution of the linear ODE system
    b = np.float32(np.exp(-DT / T_MBR))
    a = np.float32(np.exp(-DT / TAU))
    c = np.float32(TAU / (TAU - T_MBR) * (np.exp(-DT / TAU) - np.exp(-DT / T_MBR)))

    w_poi = np.float32(W_SYN * F_POI)
    if stim:
        stim_idx = np.concatenate([idx for idx, _ in stim])
        stim_p = np.concatenate([np.full(len(idx), 1.0 - np.exp(-r * DT))
                                 for idx, r in stim])
    else:
        stim_idx = np.zeros(0, dtype=int)
        stim_p = np.zeros(0)
    is_exc = np.zeros(n, dtype=bool)
    is_exc[stim_idx] = True

    spk_t, spk_i = [], []

    for t in range(N_STEPS):
        # synaptic events scheduled T_DLY ago arrive now
        slot = t % DLY_STEPS
        g += buf[slot]
        buf[slot] = 0.0

        # integrate non-refractory neurons (exact update)
        active = rfc <= 0
        vm = v[active]
        gm = g[active]
        v[active] = V_0 + (vm - V_0) * b + gm * c
        g[active] = gm * a
        rfc[~active] -= 1

        # Poisson stimulation adds directly to v (stimulated cells never refractory)
        events = rng.random(len(stim_idx)) < stim_p
        if events.any():
            v[stim_idx[events]] += w_poi

        # threshold, propagate, reset
        spiked = (v > V_TH) & (rfc <= 0)
        if spiked.any():
            idx = np.nonzero(spiked)[0]
            spk_t.append(np.full(len(idx), t, dtype=np.int32))
            spk_i.append(idx.astype(np.int32))
            # slot was consumed this step, so writing here arrives DLY_STEPS later
            buf[slot] += np.asarray(w[idx].sum(axis=0)).ravel()
            v[idx] = V_RST
            g[idx] = 0.0
            rfc[idx] = np.where(is_exc[idx], 0, RFC_STEPS)

    if spk_t:
        return np.concatenate(spk_t), np.concatenate(spk_i)
    return np.array([], dtype=np.int32), np.array([], dtype=np.int32)


def main():
    ap = argparse.ArgumentParser(
        description='Whole-brain Drosophila LIF simulation. '
                    'Group specs (--stim/--silence) are documented in groups.py.')
    ap.add_argument('--stim', default='sugar', help='neuron group to stimulate')
    ap.add_argument('--rate', type=float, default=150.0, help='stimulation rate [Hz]')
    ap.add_argument('--stim2', help='second group to stimulate, e.g. bitter')
    ap.add_argument('--rate2', type=float, default=150.0, help='rate for --stim2 [Hz]')
    ap.add_argument('--silence', help='neuron group to silence (outgoing synapses zeroed)')
    ap.add_argument('--trials', type=int, default=30)
    ap.add_argument('--name', default='sugarR_numpy')
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()

    print('loading network ...', flush=True)
    flyids, w = load_network()
    id2idx = {f: i for i, f in enumerate(flyids)}
    print(f'{w.shape[0]:,} neurons, {w.nnz:,} connections', flush=True)

    def to_idx(spec):
        return np.array([id2idx[f] for f in resolve(spec) if f in id2idx], dtype=int)

    stim = [(to_idx(args.stim), args.rate)]
    if args.stim2:
        stim.append((to_idx(args.stim2), args.rate2))
    for spec, (idx, rate) in zip([args.stim, args.stim2], stim):
        print(f'stimulating {len(idx):,} neurons at {rate:g} Hz  [{spec}]', flush=True)

    if args.silence:
        sil = to_idx(args.silence)
        silence(w, sil)
        print(f'silencing   {len(sil):,} neurons        [{args.silence}]', flush=True)

    rows = []
    for trial in range(args.trials):
        rng = np.random.default_rng(args.seed + trial)
        t0 = time.time()
        st, si = run_trial(w, stim, rng)
        rows.append(pd.DataFrame({
            't': st.astype(np.float64) * DT,
            'trial': trial,
            'flywire_id': flyids[si],
            'exp_name': args.name,
        }))
        print(f'trial {trial + 1}/{args.trials}: {len(st):,} spikes '
              f'({time.time() - t0:.1f} s)', flush=True)

    df = pd.concat(rows, ignore_index=True)
    out = HERE / 'results'
    out.mkdir(exist_ok=True)
    path = out / f'{args.name}.parquet'
    df.to_parquet(path)
    print(f'saved {len(df):,} spikes -> {path}', flush=True)

    # quick readout: does the feeding motor neuron fire?
    mn9 = df[df.flywire_id == MN9]
    print(f'MN9 rate: {len(mn9) / args.trials / T_RUN:.1f} Hz', flush=True)


if __name__ == '__main__':
    main()
