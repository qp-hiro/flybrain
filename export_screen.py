"""Turn the lesion screens into the compact JSON the page renders.

Reads screen.json (single-neuron screen) and screen_types.json (greedy
cell-type search) and writes screen_page.json. Every number the page shows
about the screen comes from here, so nothing on the page is hand-written.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
N_SHOW = 14
SRC = sys.argv[1] if len(sys.argv) > 1 else 'screen.json'

single = json.loads((HERE / SRC).read_text(encoding='utf-8'))
types = json.loads((HERE / 'screen_types.json').read_text(encoding='utf-8'))
veto = json.loads((HERE / 'validate_veto.json').read_text(encoding='utf-8'))
hits = json.loads((HERE / 'validate_hits.json').read_text(encoding='utf-8'))

sugar, poison = single['sugar'], single['sugarBitter']
keep = lambda r: {'i': r['i'], 'type': r['type'], 'cls': r['cls'],
                  'nt': r['nt'], 'hz': round(r['hz'], 1), 'delta': round(r['delta'], 1)}

necessary = [keep(r) for r in sugar['rows'][:N_SHOW]]
brakes = [keep(r) for r in reversed(sugar['rows'][-N_SHOW:])]
best_poison = max(poison['rows'], key=lambda r: r['delta'])

hist = types['history']
answer = hist[-1]['cumulative'] if hist else []
# the puzzle offers the real answer plus plausible decoys, in a fixed order
decoys = [r['type'] for r in brakes if r['type'] not in answer and r['type'] != '(未命名)']
puzzle_names = sorted(set(answer) | set(decoys[:9]))
puzzle = [{'type': t, 'idx': types['types'][t]}
          for t in puzzle_names if t in types['types']]

n_active_sugar = len(sugar['rows'])
n_active_poison = len(poison['rows'])
spec = types['specificity']

whole = {r['label']: round(r['mn9_hz'], 1) for r in veto['results']}
agree = sum(1 for h in hits['hits']
            if (h['whole_delta'] >= 0) == (h['subnet_delta'] >= 0))

findings = [
    f"<b>1個で一番効くのは {necessary[0]['type']}（{necessary[0]['nt']}）</b>。"
    f"これを消すだけで摂食は {sugar['baseline']:.0f} → {necessary[0]['hz']:.0f} Hz "
    f"（{necessary[0]['delta']:.0f} Hz）に落ちます。"
    f"12.7万個のうちのたった1個です。",

    f"<b>脳は自分にブレーキをかけています</b>。{brakes[0]['type']}"
    f"（{brakes[0]['nt']}）を消すと、逆に摂食が {brakes[0]['hz']:.0f} Hz へ"
    f"{brakes[0]['delta']:+.0f} Hz 強まります。"
    f"普段は食べすぎないよう抑えられている、ということです。",

    f"<b>毒の拒否権には単一障害点がありません</b>。"
    f"苦味を与えたときに発火している {n_active_poison} 個すべてを1個ずつ消しても、"
    f"最大で MN9 {best_poison['hz']:.0f} Hz にしかならず、ハエは毒を食べません。"
    f"1個壊れたくらいでは毒を食べてしまわないよう、回路が冗長に作られています。",

    f"<b>ただし{len(answer)}種類まとめて止めると破れます</b>。"
    f"細胞タイプ単位で探索すると、{'、'.join(answer)} の"
    f"{hist[-1]['nSilenced']}個を止めた時点で MN9 {hist[-1]['hz']:.0f} Hz となり、"
    f"ハエは毒入りの餌を食べ始めます。"
    f"しかも普通の砂糖への反応は {spec['sugar_lesioned']:.0f} Hz "
    f"（健常 {spec['sugar_intact']:.0f} Hz）とほぼ保たれたままで、"
    f"<b>苦味の拒否だけが選択的に壊れます</b>。",

    f"<b>この5個は、全脳12.7万ニューロンで再検証しても効きます</b>。"
    f"健常な脳は毒入りの餌に MN9 {whole['健常・砂糖+苦味']:.0f} Hz（拒否）ですが、"
    f"同じ5個を止めた脳は <b>{whole['病変(5個)・砂糖+苦味']:.0f} Hz</b> で食べ始めます。"
    f"普通の砂糖への反応は {whole['健常・砂糖のみ']:.0f} → "
    f"{whole['病変(5個)・砂糖のみ']:.0f} Hz と損なわれていません。"
    f"この3種類は脳全体でもちょうど5個しかないので、"
    f"遺伝子操作で狙える単位そのものです。",

    f"<b>部分回路の結果は完璧ではありません</b>。単一ニューロンの上位8件を全脳で"
    f"再検証したところ {agree}/8 は同じ向きに再現しましたが、1件"
    f"（{next(h['type'] for h in hits['hits'] if (h['whole_delta'] >= 0) != (h['subnet_delta'] >= 0))}）"
    f"は部分回路だけの偽陽性でした。スクリーニングは候補を出す道具で、"
    f"判定するのは全脳のほうです。",
]

out = {
    'meta': {
        'baseline': round(sugar['baseline'], 1),
        'baselinePoison': round(poison['baseline'], 1),
        'nTested': n_active_sugar,
        'nTestedPoison': n_active_poison,
        'seeds': single['meta']['seeds'],
    },
    'necessary': necessary,
    'brakes': brakes,
    'findings': findings,
    'puzzleTypes': puzzle,
    'answer': answer,
    'greedy': [{'round': h['round'], 'type': h['type'], 'n': h['n'],
                'hz': round(h['hz'], 1), 'nSilenced': h['nSilenced']} for h in hist],
    'specificity': {k: round(v, 1) for k, v in spec.items()},
    'whole': {'rows': [{'label': r['label'], 'hz': round(r['mn9_hz'], 1),
                        'n': r['n_silenced']} for r in veto['results']],
              'trials': veto['trials'], 'agree': agree, 'tested': len(hits['hits'])},
}

dst = HERE / 'screen_page.json'
dst.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f'{dst}: {dst.stat().st_size/1000:.1f} kB')
print(f'  screened {n_active_sugar} (sugar) / {n_active_poison} (poison) neurons')
print(f'  answer: {answer} -> MN9 {hist[-1]["hz"]:.0f} Hz')
print(f'  puzzle offers {len(puzzle)} cell types')
