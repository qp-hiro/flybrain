# flybrain — ショウジョウバエ全脳をPCで動かす

**▶ ブラウザで今すぐ遊ぶ: https://qp-hiro.github.io/flybrain/**

インストール不要。ページの中でハエの脳が実際に動きます。

1. **遊ぶ** — ハエを操縦して餌を探すゲーム。食べるか吐き出すかを決めるのは脳です
2. **計算する** — 同じ回路を論理ゲートとして使い、**ハエの脳7個で半加算器**を組んで 1+1=10 を計算
3. **自由に触る** — 味の濃さを連続的に変えて応答を観察する実験台

FlyWireコネクトーム（139,255ニューロン・5,450万シナプス）に基づく、
ショウジョウバエ全脳スパイキングシミュレーションの遊び場です。

- 砂糖受容ニューロンを刺激すると、信号が脳を伝わって摂食運動ニューロン（MN9）が発火する
  ——「ハエが食べようとする」反応が計算機上で再現できます
- 苦味を同時に与えるとMN9は完全に沈黙します（実際のハエの行動と同じ）
- モデルは Shiu et al. 2024 (Nature) のLIFモデルを **NumPyのみで再実装**（Brian2不要）。
  著者公開の参照結果と発火率相関 r = 0.94 で一致を確認済み

*A pure-NumPy whole-brain LIF simulation of the FlyWire Drosophila connectome, with an
in-browser realtime feeding circuit, a 3D spike viewer, and a UDP bridge for
hardware/software integration.*

## セットアップ

```
pip install -r requirements.txt
python scripts/get_data.py        # コネクトームデータ約120MBをダウンロード
```

## 遊び方

### 1. 砂糖を味わわせる

```
python sim.py --stim sugar --rate 100 --trials 3 --name taste
```

12.7万ニューロンの全脳が1秒間動き、スパイクが `results/*.parquet` に保存されます。
`MN9 rate: 82.7 Hz` と出れば、ハエは口吻を伸ばそうとしています。
刺激を与えなければ（`--rate 0`）全脳で**0スパイク**——この脳は完全に沈黙します。

### 2. 苦味で摂食を止める

```
python sim.py --stim sugar --rate 100 --stim2 bitter --rate2 100 --trials 3 --name sugar_vs_bitter
```

MN9は **82.7 Hz → 0.0 Hz**。抑制性の回路が摂食を拒否します。

### 3. ニューロンを黙らせる（回路の外科手術）

```
python sim.py --stim sugar --rate 100 --silence type:CB0248 --trials 3 --name surgery
```

CB0248（砂糖応答で最も活発なGABA作動性ニューロン、左右2個）を黙らせると
MN9は **82.7 → 92.0 Hz**。ブレーキを外したぶん摂食駆動が強まります（脱抑制）。

### 4. ほかの感覚を試す

```
python groups.py --list class subclass          # 使える名前の一覧
python sim.py --stim type:R1-6 --rate 30 --name light          # 光（光受容細胞1,908個）
python sim.py --stim type:ORN_DA1 --rate 50 --name pheromone   # フェロモン（嗅覚122個）
python sim.py --stim class:thermosensory --rate 50 --name heat # 温度
```

光を当てると脳全体のスパイクは 12,557 → **57,243** に跳ね上がりますが、MN9は0Hzのまま。
感覚のモダリティごとに届く先が違うことが配線図だけから出てきます。

刺激対象（`--stim` / `--silence`）には組み込み名（`sugar`, `bitter`, `mn9`）、
`type:` / `class:` / `subclass:`、FlyWire IDの直接指定が使えます。
`@R` / `@L` で半球を限定できます。詳細は `groups.py` のdocstringへ。

### 5. 3Dで見る・ページを再生成する

```
python viz_export.py results/taste.parquet
python build_page.py              # -> docs/index.html（自己完結・オフライン動作）
```

`docs/index.html` をブラウザで開くだけ。mainにpushすると
https://qp-hiro.github.io/flybrain/ が自動更新されます。

### 6. 外部の機器・ソフトと繋ぐ

```
python io_bridge.py               # 脳を常駐させる (udp://127.0.0.1:8631)
python examples/feed_the_fly.py   # 別ターミナル: キー1-9で砂糖刺激、MN9メーター表示
```

UDPでJSONを投げるだけなので、Arduino（`examples/arduino_bridge.py`）、Unity、
Max/MSP、TouchDesigner等から脳を刺激したり、スパイクで機器を駆動できます。

```json
{"cmd": "stim", "target": "sugar", "rate": 120, "duration_ms": 500}
{"cmd": "stim", "target": "bitter", "rate": 100}
{"cmd": "subscribe", "target": "mn9"}
```

注意: 全脳は実時間の約1/20で進みます（`status` の `realtime_factor` で確認可）。
リアルタイム応答が要る用途では次の部分回路を使ってください。

## リアルタイム部分回路（HCI用途）

全脳は遅すぎるため、`engine.py` の `build_subnet()` で摂食に関わる2シナプス以内の
**4,000ニューロン・387,060シナプス**を切り出せます。これは実時間で動き、全脳と同じ応答を示します。

| | 全脳 127,400 | 部分回路 4,000 | ブラウザJS版 |
|---|---|---|---|
| 砂糖100Hz → MN9 | 80.6 Hz | 78 Hz | 68–112 Hz |
| 砂糖+苦味 → MN9 | 0.0 Hz | 0.0 Hz | 0.0 Hz |
| 速度 | 実時間 x0.05 | x0.8 | x1.0–1.3 |

`export_subnet.py` がこれを `subnet.json` に書き出し、`flybrain.js`（同じLIFモデルの
JavaScript移植）がブラウザ内で実行します。公開ページのインタラクティブ部分がこれです。

### 実測した回路の特性

`measure_dynamics.js` と `measure_dose.js` で測定した、ゲーム設計にも使っている値です。

| 項目 | 実測値 |
|---|---|
| 砂糖を与えてから最初のMN9スパイクまで | 25 ms |
| MN9が20Hzを超えるまで | 30 ms |
| 砂糖を止めてから20Hz以下に落ちるまで | 30 ms |
| 苦味を足してからMN9が沈黙するまで | 25 ms |
| 反応が始まる砂糖の濃さ | 30 Hz（20 Hz以下では完全に無反応） |
| 砂糖150Hzを完全に打ち消すのに必要な苦味 | 120 Hz（80 Hzでほぼ沈黙） |

## ハエの脳で計算する

砂糖を入力A、苦味を入力B、MN9を出力とみなすと、この回路は **`A AND NOT B`**（NIMPLY）
を計算しています。全脳・部分回路・ブラウザ版のすべてで真理値表が一致します。

| A 砂糖 | B 苦味 | MN9 | 出力 |
|---|---|---|---|
| 0 | 0 | 0.0 Hz | 0 |
| 1 | 0 | 116 Hz | 1 |
| 0 | 1 | 0.0 Hz | 0 |
| 1 | 1 | 0.0 Hz | 0 |

NIMPLYは定数1と組み合わせると**関数完全**——つまりこれだけであらゆる論理回路が作れます。
実際に7個つないで半加算器を組み、動作を確認しました。

```
node test_adder.js      # ハエの脳7個 = 28,000ニューロンで 1+1 = 10 (2進)
```

```
  A  B | SUM CARRY | expected | MN9 Hz (sum / carry)
  0  0 |  0    0   |   0 0    |    0 /    0   ok
  1  0 |  1    0   |   1 0    |   50 /    0   ok
  0  1 |  1    0   |   1 0    |   85 /    0   ok
  1  1 |  0    1   |   0 1    |    0 /  100   ok
```

ゲート間は出力の発火率を20Hzで0/1に整えて次の脳の味覚入力へ渡しています
（論理回路でいうバッファ相当）。それ以外はすべて生の神経活動です。

## モデル

Shiu et al. 2024 の leaky integrate-and-fire モデルそのまま:

- 静止電位 −52 mV / 閾値 −45 mV / 膜時定数 20 ms / 不応期 2.2 ms
- シナプス: 発火の1.8 ms後に指数減衰コンダクタンス（τ=5 ms）へ 0.275 mV × シナプス数を加算
  （GABA・グルタミン酸作動性は負の重み）
- 刺激: ポアソン過程（デフォルト150 Hz）で膜電位を直接押し上げる

線形ODEの厳密解で1ステップ0.1 msを更新し、遅延はリングバッファで処理します。

## 検証

```
python compare.py results/taste.parquet       # 対 Brian2参照実装
python validate_subnet.py                     # 対 部分回路
node test_js_engine.js                        # 対 ブラウザJS版
node test_page.js                             # ビルド済みページの静的検査＋実行
node test_adder.js                            # ハエの脳7個の半加算器
python test_bridge.py                         # UDPブリッジ（io_bridge.py起動中に）
```

| 比較 | 指標 | 結果 |
|---|---|---|
| NumPy版 vs Brian2参照（30試行・100Hz） | ニューロン別発火率の相関 | r = 0.94 |
| 刺激した砂糖GRN 21個 | 発火率の差 | ±2 Hz 以内 |
| 全脳 vs 部分回路 | 砂糖100Hz時のMN9 | 80.6 vs 78 Hz |

## ファイル

| ファイル | 役割 |
|---|---|
| `sim.py` | バッチシミュレーション（CLI） |
| `engine.py` | 常駐Brainクラス・部分回路抽出 |
| `groups.py` | ニューロン群の名前解決（`type:` / `class:` など） |
| `io_bridge.py` | UDP/JSONブリッジ |
| `flybrain.js` | LIFモデルのJavaScript移植（ブラウザ実行用） |
| `export_subnet.py` / `viz_export.py` / `build_page.py` | 公開ページの生成 |
| `page_template.html` | ページのHTML/CSS/JS本体（データは差し込み） |
| `measure_dynamics.js` / `measure_dose.js` | 応答遅延・用量反応の測定 |
| `test_adder.js` | ハエの脳7個で半加算器を組んで検証 |

## データと出典

| ファイル | 内容 | 出典 |
|---|---|---|
| `connectivity_630.parquet` | ニューロン間結合（1,470万エントリ） | [Shiu et al. 2024](https://github.com/philshiu/Drosophila_brain_model) |
| `2023_03_23_completeness_630_final.csv` | 全127,400ニューロンのID | 同上 |
| `neuron_annotations.tsv` | 座標・細胞タイプ・神経伝達物質 | [Schlegel et al. 2024](https://github.com/flyconnectome/flywire_annotations) |
| `reference/*.parquet` | 検証用の著者公開シミュレーション結果 | Shiu et al. 2024 |

- FlyWireコネクトーム: Dorkenwald et al. 2024 / Schlegel et al. 2024 (Nature), CC-BY 4.0
- モデル・参照結果: Shiu, Sterne et al. 2024, "A Drosophila computational brain model
  reveals sensorimotor processing" (Nature). コードはMITライセンス（`LICENSE_upstream`）
