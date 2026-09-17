# flybrain — ショウジョウバエ全脳をPCで動かす

**▶ ブラウザで今すぐ見る: https://qp-hiro.github.io/flybrain/**
（インストール不要。砂糖刺激に対する全脳スパイク伝播の3D再生）


FlyWireコネクトーム（139,255ニューロン・5,450万シナプス）に基づく
**ショウジョウバエ全脳スパイキングシミュレーション**の遊び場です。

- 砂糖受容ニューロンを刺激すると、信号が脳を伝わって摂食運動ニューロン（MN9）が発火する
  ——「ハエが食べようとする」反応が計算機上で再現できます
- モデルは Shiu et al. 2024 (Nature) のLIFモデルを **NumPyのみで再実装**したもの
  （Brian2不要。著者公開の参照結果と発火率相関 r > 0.95 で一致確認済み）
- ブラウザで遊べる3Dビューア、外部ハードウェア/ソフトと繋ぐUDPブリッジ付き

*A pure-NumPy whole-brain LIF simulation of the FlyWire Drosophila connectome,
with a browser-based 3D spike viewer and a UDP bridge for hardware/software integration.*

## セットアップ

```
pip install numpy pandas pyarrow scipy
python scripts/get_data.py        # コネクトームデータ約120MBをダウンロード
```

## 遊び方

### 1. 砂糖を味わわせる（バッチシミュレーション）

```
python sim.py --rate 100 --trials 5 --name my_first_taste
```

12.7万ニューロンの全脳が1秒間動き、スパイクが `results/*.parquet` に保存されます。
最後にMN9（摂食運動ニューロン）の発火率が表示されます。刺激なしでは脳は沈黙し、
砂糖ニューロンを叩くと約400個のニューロンが連鎖的に発火します。

参照実装（Brian2）との検証: `python compare.py results/my_first_taste.parquet`

### 2. 3Dビューアで眺める

シミュレーション結果を可視化データに変換してページを生成:

```
python viz_export.py results/my_first_taste.parquet
python build_page.py              # -> docs/index.html（自己完結・オフライン動作）
```

`docs/index.html` をブラウザで開くだけ。mainにpushすると
https://qp-hiro.github.io/flybrain/ が自動更新されるので、URLを共有するだけで誰でも遊べます。

### 3. 外部のモノと繋ぐ（リアルタイムI/Oブリッジ）

```
python io_bridge.py               # 脳を常駐させる (udp://127.0.0.1:8631)
python examples/feed_the_fly.py   # 別ターミナル: キー1-9で砂糖刺激、MN9メーター表示
```

UDPでJSONを投げるだけなので、Arduino（`examples/arduino_bridge.py`）、Unity、
Max/MSP、TouchDesigner等から脳を刺激したり、スパイクで機器を駆動できます。

注意: 全脳シミュレーションは実時間の数十〜数百分の1の速度で進みます
（`status` コマンドの `realtime_factor` で確認可。CPUの熱状態でも変動します）。
レポートの `sim_ms` はシミュレーション内時刻です。

プロトコル（詳細は `io_bridge.py` 冒頭のdocstring）:

```json
{"cmd": "stim", "target": "sugar", "rate": 120, "duration_ms": 500}
{"cmd": "subscribe", "target": "mn9"}
{"cmd": "stim", "target": "type:MN9", "rate": 50}
```

`target` には組み込みグループ（`sugar` / `mn9`）、flywire IDのリスト、
`type:<cell_type>`（注釈データの細胞タイプ名）が使えます。

## モデル

Shiu et al. 2024 の leaky integrate-and-fire モデルそのまま:

- 静止電位 -52 mV / 閾値 -45 mV / 膜時定数 20 ms / 不応期 2.2 ms
- シナプス: 発火の1.8 ms後に指数減衰コンダクタンス（τ=5 ms）へ 0.275 mV × シナプス数を加算
  （GABA・グルタミン酸作動性は負の重み）
- 刺激: ポアソン過程（デフォルト150 Hz）で膜電位を直接押し上げる

実装は `sim.py`（バッチ）と `io_bridge.py`（常駐・刺激可変）の2つ。
線形ODEの厳密解で1ステップ0.1 msを更新し、遅延はリングバッファで処理します。

## データと出典

| ファイル | 内容 | 出典 |
|---|---|---|
| `connectivity_630.parquet` | ニューロン間結合（1,470万エントリ） | [Shiu et al. 2024](https://github.com/philshiu/Drosophila_brain_model) |
| `2023_03_23_completeness_630_final.csv` | 全127,400ニューロンのID | 同上 |
| `neuron_annotations.tsv` | 座標・細胞タイプ・神経伝達物質 | [Schlegel et al. 2024](https://github.com/flyconnectome/flywire_annotations) |
| `reference/*.parquet` | 検証用の著者公開シミュレーション結果 | Shiu et al. 2024 |

- FlyWireコネクトームデータ: Dorkenwald et al. 2024 / Schlegel et al. 2024 (Nature), CC-BY 4.0
- モデル・参照結果: Shiu et al. 2024 "A Drosophila computational brain model reveals
  sensorimotor processing" (Nature), コードは上記リポジトリ参照
