"""Real-time I/O bridge: run the fly brain continuously and talk to it over UDP.

The simulation advances in 10 ms chunks. Between chunks the bridge:
  - reads JSON commands from a UDP socket (stimulate neurons, subscribe to spikes)
  - pushes spike reports of watched neurons to subscribed clients

This makes the connectome a component you can wire to anything that speaks
UDP: Arduino (via a serial bridge), Unity, Max/MSP, TouchDesigner, Python...

Protocol (JSON datagrams, port 8631):
  {"cmd": "stim", "target": "sugar", "rate": 120, "duration_ms": 500}
  {"cmd": "stim", "target": [720575940660219265], "rate": 80}
  {"cmd": "stim", "target": "type:MN9", "rate": 0}          # rate 0 stops
  {"cmd": "subscribe", "target": "mn9"}                      # watch neurons
  {"cmd": "subscribe", "target": "top"}                      # top-10 firing
  {"cmd": "status"}

Report sent to subscribers after every chunk:
  {"sim_ms": 1230, "watched": {"720575940660219265": 2}, "total_spikes": 41,
   "top": [["720575940622695448", 3], ...]}

Note: the whole brain runs slower than real time (~10-30x on a laptop);
sim_ms is simulation time, not wall time.

Usage:  python io_bridge.py [--port 8631]
Demo:   python examples/feed_the_fly.py   (in another terminal)
"""

import argparse
import json
import socket
import time
from pathlib import Path

import numpy as np
import pandas as pd

from sim import (DT, DLY_STEPS, RFC_STEPS, V_0, V_RST, V_TH, W_SYN, F_POI,
                 SUGAR_GRNS, MN9, T_MBR, TAU, load_network)

HERE = Path(__file__).parent
CHUNK_STEPS = 100  # 10 ms of simulated time per chunk


class Brain:
    """Continuously running whole-brain LIF simulation with mutable stimulation."""

    def __init__(self):
        self.flyids, self.w = load_network()
        self.id2idx = {f: i for i, f in enumerate(self.flyids)}
        n = self.w.shape[0]
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

        # stimulation table: neuron index -> (per-step probability, expiry step or None)
        self.stim_p = np.zeros(n, dtype=np.float32)
        self.stim_until = np.full(n, -1, dtype=np.int64)  # -1: no expiry

    def set_stim(self, idx, rate_hz, duration_ms=None):
        idx = np.asarray(idx)
        self.stim_p[idx] = 1.0 - np.exp(-rate_hz * DT) if rate_hz > 0 else 0.0
        if duration_ms is None:
            self.stim_until[idx] = -1
        else:
            self.stim_until[idx] = self.step + int(duration_ms / 1000 / DT)

    def run_chunk(self):
        """Advance CHUNK_STEPS; return (neuron_idx, count) of spikes in the chunk."""
        counts = {}
        for _ in range(CHUNK_STEPS):
            t = self.step
            slot = t % DLY_STEPS
            self.g += self.buf[slot]
            self.buf[slot] = 0.0

            active = self.rfc <= 0
            vm = self.v[active]
            gm = self.g[active]
            self.v[active] = V_0 + (vm - V_0) * self.b + gm * self.c
            self.g[active] = gm * self.a
            self.rfc[~active] -= 1

            # expire timed stimulations
            expired = (self.stim_until == t)
            if expired.any():
                self.stim_p[expired] = 0.0
                self.stim_until[expired] = -1

            stim = np.nonzero(self.stim_p > 0)[0]
            if len(stim):
                events = self.rng.random(len(stim)) < self.stim_p[stim]
                self.v[stim[events]] += self.w_poi

            spiked = (self.v > V_TH) & (self.rfc <= 0)
            if spiked.any():
                idx = np.nonzero(spiked)[0]
                self.buf[slot] += np.asarray(self.w[idx].sum(axis=0)).ravel()
                self.v[idx] = V_RST
                self.g[idx] = 0.0
                # stimulated neurons get no refractory period (as in the paper)
                self.rfc[idx] = np.where(self.stim_p[idx] > 0, 0, RFC_STEPS)
                for i in idx:
                    counts[i] = counts.get(i, 0) + 1
            self.step += 1
        return counts


def load_typemap():
    ann = pd.read_csv(HERE / 'neuron_annotations.tsv', sep='\t',
                      usecols=['root_id', 'cell_type'])
    ann = ann.dropna(subset=['cell_type'])
    return ann.groupby('cell_type')['root_id'].apply(list).to_dict()


def resolve(target, brain, typemap):
    """Turn a protocol target into a list of neuron indices."""
    if isinstance(target, list):
        ids = target
    elif target == 'sugar':
        ids = list(SUGAR_GRNS)
    elif target == 'mn9':
        ids = [MN9]
    elif isinstance(target, str) and target.startswith('type:'):
        ids = typemap.get(target[5:], [])
    else:
        return []
    return [brain.id2idx[f] for f in ids if f in brain.id2idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8631)
    args = ap.parse_args()

    print('loading network ...', flush=True)
    brain = Brain()
    typemap = load_typemap()
    print(f'{brain.w.shape[0]:,} neurons ready', flush=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', args.port))
    sock.setblocking(False)
    print(f'listening on udp://127.0.0.1:{args.port}', flush=True)

    subscribers = {}   # addr -> set of watched neuron indices ('top' = empty set)
    t_wall = time.time()

    while True:
        # 1. handle pending commands
        while True:
            try:
                data, addr = sock.recvfrom(65536)
            except BlockingIOError:
                break
            try:
                msg = json.loads(data.decode('utf-8'))
                cmd = msg.get('cmd')
                if cmd == 'stim':
                    idx = resolve(msg.get('target'), brain, typemap)
                    brain.set_stim(idx, float(msg.get('rate', 0)), msg.get('duration_ms'))
                    sock.sendto(json.dumps({'ok': True, 'stimulating': len(idx)}).encode(), addr)
                elif cmd == 'subscribe':
                    tgt = msg.get('target', 'top')
                    subscribers[addr] = set() if tgt == 'top' else set(resolve(tgt, brain, typemap))
                    sock.sendto(json.dumps({'ok': True, 'watching': len(subscribers[addr]) or 'top'}).encode(), addr)
                elif cmd == 'status':
                    rt = brain.step * DT / max(time.time() - t_wall, 1e-9)
                    sock.sendto(json.dumps({
                        'sim_ms': brain.step * DT * 1000,
                        'realtime_factor': round(rt, 3),
                        'stimulated': int((brain.stim_p > 0).sum()),
                    }).encode(), addr)
            except (ValueError, KeyError, TypeError) as e:
                sock.sendto(json.dumps({'ok': False, 'error': str(e)}).encode(), addr)

        # 2. advance the brain
        counts = brain.run_chunk()

        # 3. report to subscribers
        if subscribers and counts is not None:
            top = sorted(counts.items(), key=lambda kv: -kv[1])[:10]
            for addr, watched in list(subscribers.items()):
                report = {
                    'sim_ms': round(brain.step * DT * 1000, 1),
                    'total_spikes': int(sum(counts.values())),
                    'watched': {str(brain.flyids[i]): counts[i] for i in watched if i in counts},
                    'top': [[str(brain.flyids[i]), c] for i, c in top],
                }
                try:
                    sock.sendto(json.dumps(report).encode(), addr)
                except OSError:
                    del subscribers[addr]


if __name__ == '__main__':
    main()
