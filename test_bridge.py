"""Automated smoke test for io_bridge.py: stimulate sugar, expect MN9 spikes."""

import json
import socket
import time

MN9 = '720575940660219265'
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('127.0.0.1', 0))
sock.settimeout(5.0)
server = ('127.0.0.1', 8631)

# wait until the brain answers status (it loads for ~30 s)
for _ in range(60):
    try:
        sock.sendto(json.dumps({'cmd': 'status'}).encode(), server)
        data, _ = sock.recvfrom(65536)
        print('status:', data.decode())
        break
    except (socket.timeout, ConnectionResetError):
        pass  # ConnectionResetError: Windows ICMP quirk while the bridge loads
else:
    raise SystemExit('bridge never answered')

# acks and streaming reports interleave, so don't assume reply order
sock.sendto(json.dumps({'cmd': 'subscribe', 'target': 'mn9'}).encode(), server)
sock.sendto(json.dumps({'cmd': 'stim', 'target': 'sugar', 'rate': 150}).encode(), server)

mn9_total, total, reports = 0, 0, 0
t0 = time.time()
last_ms = 0
while reports < 40 and time.time() - t0 < 120:
    try:
        msg = json.loads(sock.recvfrom(65536)[0].decode())
    except ConnectionResetError:
        continue
    if 'sim_ms' not in msg or 'watched' not in msg:
        continue
    mn9_total += msg['watched'].get(MN9, 0)
    total += msg['total_spikes']
    last_ms = msg['sim_ms']
    reports += 1

sock.sendto(json.dumps({'cmd': 'stim', 'target': 'sugar', 'rate': 0}).encode(), server)
sim_span = reports * 10 / 1000  # each report covers 10 ms
print(f'{reports} reports ({sim_span*1000:.0f} ms sim time, {time.time()-t0:.1f} s wall)')
print(f'total spikes: {total}, MN9 spikes: {mn9_total} (~{mn9_total/sim_span:.0f} Hz)')
assert mn9_total > 0, 'MN9 did not fire!'
print('PASS: the fly tried to eat')
