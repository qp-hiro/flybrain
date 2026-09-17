"""Simulation engine: the continuously-running Brain, and subnetwork extraction.

The whole brain (127k neurons) runs at roughly 1/20 of real time on a laptop,
which is too slow to feel interactive. For HCI use, `build_subnet` carves out
the part of the brain that the stimulated pathway actually reaches -- typically
a few thousand neurons -- which runs faster than real time.
"""

import numpy as np
from scipy import sparse

from sim import (DT, DLY_STEPS, RFC_STEPS, V_0, V_RST, V_TH, W_SYN, F_POI,
                 T_MBR, TAU, load_network)


def build_subnet(flyids, w, seed_ids, hops=2, min_syn=3, max_neurons=6000):
    """Carve out the k-hop downstream neighbourhood of `seed_ids`.

    Follows outgoing connections of at least `min_syn` synapses. Returns
    (sub_flyids, sub_w) -- a self-contained network that keeps every synapse
    among the selected neurons, including feedback and inhibition.
    """
    id2idx = {f: i for i, f in enumerate(flyids)}
    frontier = {id2idx[f] for f in seed_ids if f in id2idx}
    keep = set(frontier)
    min_w = min_syn * W_SYN

    for _ in range(hops):
        nxt = set()
        for i in frontier:
            lo, hi = w.indptr[i], w.indptr[i + 1]
            strong = np.abs(w.data[lo:hi]) >= min_w
            nxt.update(w.indices[lo:hi][strong].tolist())
        frontier = nxt - keep
        keep |= frontier
        if len(keep) > max_neurons:
            break

    idx = np.array(sorted(keep))
    if len(idx) > max_neurons:
        # keep the seeds plus the most strongly driven targets
        seed_set = {id2idx[f] for f in seed_ids if f in id2idx}
        drive = np.asarray(np.abs(w[:, idx]).sum(axis=0)).ravel()
        order = np.argsort(-drive)
        chosen = list(seed_set)
        for j in order:
            if idx[j] not in seed_set:
                chosen.append(idx[j])
            if len(chosen) >= max_neurons:
                break
        idx = np.array(sorted(chosen))

    return flyids[idx], sparse.csr_matrix(w[idx][:, idx])


class Brain:
    """Continuously running LIF network with mutable stimulation."""

    def __init__(self, flyids=None, w=None):
        if flyids is None:
            flyids, w = load_network()
        self.flyids = flyids
        self.w = w
        self.id2idx = {f: i for i, f in enumerate(flyids)}
        n = w.shape[0]

        self.v = np.full(n, V_0, dtype=np.float32)
        self.g = np.zeros(n, dtype=np.float32)
        self.rfc = np.zeros(n, dtype=np.int32)
        self.buf = np.zeros((DLY_STEPS, n), dtype=np.float32)
        self.step = 0
        self.rng = np.random.default_rng()

        self.b = np.float32(np.exp(-DT / T_MBR))
        self.a = np.float32(np.exp(-DT / TAU))
        self.c = np.float32(TAU / (TAU - T_MBR) * (np.exp(-DT / TAU) - np.exp(-DT / T_MBR)))
        self.w_poi = np.float32(W_SYN * F_POI)

        self.stim_p = np.zeros(n, dtype=np.float32)
        self.stim_until = np.full(n, -1, dtype=np.int64)

        # raw CSR arrays: gathering spiking rows directly is far cheaper than
        # slicing the sparse matrix every step
        self._indptr = w.indptr
        self._indices = w.indices
        self._data = w.data.astype(np.float32)
        self._scratch = np.empty(n, dtype=np.float32)

    def set_stim(self, idx, rate_hz, duration_ms=None):
        idx = np.asarray(idx, dtype=int)
        if not len(idx):
            return
        self.stim_p[idx] = 1.0 - np.exp(-rate_hz * DT) if rate_hz > 0 else 0.0
        self.stim_until[idx] = (-1 if duration_ms is None
                                else self.step + int(duration_ms / 1000 / DT))

    def run_steps(self, n_steps):
        """Advance n_steps; return {neuron index: spike count}."""
        counts = {}
        v, g, rfc, buf = self.v, self.g, self.rfc, self.buf
        indptr, indices, data = self._indptr, self._indices, self._data
        n = len(v)
        stim = np.nonzero(self.stim_p > 0)[0]
        stim_p = self.stim_p[stim]

        for _ in range(n_steps):
            t = self.step
            slot = t % DLY_STEPS
            g += buf[slot]
            buf[slot] = 0.0

            # integrate everyone, then hold the refractory ones fixed
            nonref = rfc <= 0
            upd = V_0 + (v - V_0) * self.b + g * self.c
            np.copyto(v, upd, where=nonref)
            np.multiply(g, self.a, out=self._scratch)
            np.copyto(g, self._scratch, where=nonref)
            np.subtract(rfc, ~nonref, out=rfc, casting='unsafe')

            if (self.stim_until == t).any():
                expired = self.stim_until == t
                self.stim_p[expired] = 0.0
                self.stim_until[expired] = -1
                stim = np.nonzero(self.stim_p > 0)[0]
                stim_p = self.stim_p[stim]

            if len(stim):
                fired = stim[self.rng.random(len(stim)) < stim_p]
                v[fired] += self.w_poi

            spiked = (v > V_TH) & nonref
            if spiked.any():
                idx = np.nonzero(spiked)[0]
                # gather the outgoing rows of all spiking neurons at once
                lo, hi = indptr[idx], indptr[idx + 1]
                lens = hi - lo
                total = int(lens.sum())
                if total:
                    starts = np.repeat(lo, lens)
                    offs = np.arange(total) - np.repeat(np.cumsum(lens) - lens, lens)
                    sel = starts + offs
                    buf[slot] += np.bincount(indices[sel], weights=data[sel],
                                             minlength=n).astype(np.float32)
                v[idx] = V_RST
                g[idx] = 0.0
                rfc[idx] = np.where(self.stim_p[idx] > 0, 0, RFC_STEPS)
                for i in idx:
                    counts[i] = counts.get(i, 0) + 1
            self.step += 1
        return counts

    @property
    def sim_ms(self):
        return self.step * DT * 1000
