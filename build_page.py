"""Assemble the self-contained page.

page_template.html + viz_data.json + subnet.json + flybrain.js -> docs/index.html
"""

import json
from pathlib import Path

HERE = Path(__file__).parent

template = (HERE / 'page_template.html').read_text(encoding='utf-8')
pieces = {
    '/*__VIZ_DATA__*/': (HERE / 'viz_data.json').read_text(encoding='utf-8'),
    '/*__SUBNET__*/': (HERE / 'subnet.json').read_text(encoding='utf-8'),
    '/*__SCREEN__*/': (HERE / 'screen_page.json').read_text(encoding='utf-8'),
    '/*__FLYBRAIN_JS__*/': (HERE / 'flybrain.js').read_text(encoding='utf-8'),
}
for token, content in pieces.items():
    if token not in template:
        raise SystemExit(f'placeholder {token} missing from page_template.html')
    template = template.replace(token, content, 1)

dst = HERE / 'docs' / 'index.html'
dst.parent.mkdir(exist_ok=True)
dst.write_text(template, encoding='utf-8')
print(f'{dst}: {dst.stat().st_size/1e6:.2f} MB')
