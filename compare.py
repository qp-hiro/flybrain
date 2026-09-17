"""Compare our NumPy simulation against the reference Brian2 results
(results/example/sugarR_100Hz.parquet from Shiu et al.)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
T_RUN = 1.0

ours_path = sys.argv[1] if len(sys.argv) > 1 else HERE / 'results' / 'smoke_test.parquet'
ref_path = HERE / 'reference' / 'sugarR_100Hz.parquet'


def rates(df):
    n_trials = df['trial'].nunique()
    return df.groupby('flywire_id').size() / n_trials / T_RUN


ours = rates(pd.read_parquet(ours_path))
ref = rates(pd.read_parquet(ref_path))

both = pd.DataFrame({'ref_hz': ref, 'ours_hz': ours}).fillna(0.0)
active = both[(both.ref_hz > 1) | (both.ours_hz > 1)]

r = np.corrcoef(active.ref_hz, active.ours_hz)[0, 1]
print(f'neurons active (>1 Hz) in either: {len(active)}')
print(f'Pearson r of per-neuron rates:    {r:.4f}')
print(f'mean |rate diff|:                 {np.abs(active.ref_hz - active.ours_hz).mean():.2f} Hz')
print()
print('top 25 by reference rate:')
top = active.sort_values('ref_hz', ascending=False).head(25)
print(top.to_string(float_format='%.1f'))

MN9 = 720575940660219265
print(f"\nMN9  reference: {both.loc[MN9, 'ref_hz']:.1f} Hz   ours: {both.loc[MN9, 'ours_hz']:.1f} Hz")
