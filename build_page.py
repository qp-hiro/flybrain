"""Assemble the self-contained viewer page: viewer_template.html + viz_data.json -> docs/index.html"""

import json
from pathlib import Path

HERE = Path(__file__).parent

template = (HERE / 'viewer_template.html').read_text(encoding='utf-8')
data = json.loads((HERE / 'viz_data.json').read_text(encoding='utf-8'))
page = template.replace('/*__DATA__*/', json.dumps(data, separators=(',', ':')), 1)

dst = HERE / 'docs' / 'index.html'
dst.parent.mkdir(exist_ok=True)
dst.write_text(page, encoding='utf-8')
print(f'{dst}: {dst.stat().st_size/1e6:.1f} MB')
