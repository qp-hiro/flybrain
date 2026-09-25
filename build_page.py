"""Assemble the self-contained pages.

  page_template.html + viz_data.json + subnet.json + screen_page.json + flybrain.js
      -> docs/index.html
  page_robot.html    + robotnet.json + flybrain.js
      -> docs/robot.html
"""

from pathlib import Path

HERE = Path(__file__).parent
read = lambda name: (HERE / name).read_text(encoding='utf-8')

PAGES = [
    ('page_template.html', 'index.html', {
        '/*__VIZ_DATA__*/': 'viz_data.json',
        '/*__SUBNET__*/': 'subnet.json',
        '/*__SCREEN__*/': 'screen_page.json',
        '/*__FLYBRAIN_JS__*/': 'flybrain.js',
    }),
    ('page_robot.html', 'robot.html', {
        '/*__ROBOTNET__*/': 'robotnet.json',
        '/*__BODIES__*/': 'bodies.json',
        '/*__FLYBRAIN_JS__*/': 'flybrain.js',
    }),
]

for template, out, pieces in PAGES:
    page = read(template)
    for token, source in pieces.items():
        if token not in page:
            raise SystemExit(f'placeholder {token} missing from {template}')
        page = page.replace(token, read(source), 1)
    dst = HERE / 'docs' / out
    dst.parent.mkdir(exist_ok=True)
    dst.write_text(page, encoding='utf-8')
    print(f'{dst}: {dst.stat().st_size/1e6:.2f} MB')
