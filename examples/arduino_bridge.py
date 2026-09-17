"""Bridge between io_bridge.py (UDP) and an Arduino (serial).

Requires: pip install pyserial

Wiring idea:
  - a potentiometer / light sensor on the Arduino controls how strongly
    the fly's sugar neurons are stimulated
  - MN9 spikes (the fly "trying to eat") drive a servo or LED

Arduino sketch protocol (newline-delimited):
  Arduino -> PC : "S:<0-1023>"   sensor reading
  PC -> Arduino : "M:<spikes>"   MN9 spikes in the last 10 ms chunk

Usage: python arduino_bridge.py COM3 [baud]
"""

import json
import socket
import sys

import serial  # pyserial

PORT = 8631
MN9 = '720575940660219265'

port = sys.argv[1] if len(sys.argv) > 1 else 'COM3'
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

ser = serial.Serial(port, baud, timeout=0.01)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('127.0.0.1', 0))
sock.settimeout(0.01)
server = ('127.0.0.1', PORT)

sock.sendto(json.dumps({'cmd': 'subscribe', 'target': 'mn9'}).encode(), server)
last_rate = -1

while True:
    line = ser.readline().decode(errors='ignore').strip()
    if line.startswith('S:'):
        rate = int(int(line[2:]) / 1023 * 200)  # sensor -> 0-200 Hz
        if abs(rate - last_rate) >= 5:
            sock.sendto(json.dumps(
                {'cmd': 'stim', 'target': 'sugar', 'rate': rate}).encode(), server)
            last_rate = rate

    try:
        data, _ = sock.recvfrom(65536)
        msg = json.loads(data.decode())
        if 'watched' in msg:
            ser.write(f"M:{msg['watched'].get(MN9, 0)}\n".encode())
    except (socket.timeout, ConnectionResetError):
        pass
