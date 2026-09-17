"""Feed the fly: interactive demo client for io_bridge.py (stdlib only).

Start the brain first:   python io_bridge.py
Then in another shell:   python examples/feed_the_fly.py

Keys 1-9 stimulate the sugar-sensing neurons at 20-180 Hz, 0 stops.
The meter shows the firing rate of MN9, the proboscis motor neuron --
when it climbs, the fly is trying to eat.
"""

import json
import socket
import sys
import time

PORT = 8631
MN9 = '720575940660219265'

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('127.0.0.1', 0))
sock.settimeout(0.05)
server = ('127.0.0.1', PORT)


def send(msg):
    sock.sendto(json.dumps(msg).encode(), server)


send({'cmd': 'subscribe', 'target': 'mn9'})

if sys.platform == 'win32':
    import msvcrt

    def key_pressed():
        return msvcrt.getwch() if msvcrt.kbhit() else None
else:
    def key_pressed():
        return None  # on unix, pipe keys in or edit as needed

print(__doc__)
window = []          # (wall_time, mn9_spikes) for a sliding rate estimate
sim_ms_prev = None
rate_cmd = 0

while True:
    k = key_pressed()
    if k == 'q':
        send({'cmd': 'stim', 'target': 'sugar', 'rate': 0})
        break
    if k and k.isdigit():
        rate_cmd = int(k) * 20
        send({'cmd': 'stim', 'target': 'sugar', 'rate': rate_cmd})

    try:
        data, _ = sock.recvfrom(65536)
    except socket.timeout:
        continue
    msg = json.loads(data.decode())
    if 'sim_ms' not in msg or 'watched' not in msg:
        continue

    mn9 = msg['watched'].get(MN9, 0)
    sim_ms = msg['sim_ms']
    if sim_ms_prev is not None and sim_ms > sim_ms_prev:
        window.append((sim_ms, mn9))
        window = [(t, c) for t, c in window if sim_ms - t <= 200]  # 200 ms window
        span = max(sim_ms - window[0][0], 1e-9) / 1000
        rate = sum(c for _, c in window) / span
        bar = '#' * min(int(rate / 2), 60)
        print(f'\rsugar {rate_cmd:3d} Hz | MN9 {rate:6.1f} Hz |{bar:<60}|', end='', flush=True)
    sim_ms_prev = sim_ms
