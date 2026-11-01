# Detector evaluation

The data is synthetic, so the ground truth is known. The generator plants four kinds of situation and, for each,
a set of **decoys**: outlets with a weaker version of the same pattern that a sales manager would not want flagged.

| Scenario | Planted (should be flagged) | Decoy (should not) |
|---|---|---|
| Revenue decline | order rate down 50-75% over the last 60 days | down 5-20% |
| Inactive outlet | silent for 35-75 days | silent for 12-22 days |
| Stock risk | shelf empty on 9-20% of days | 3-4.5% of days |
| Cross-sell gap | does not stock the territory's most popular category | does not stock its least popular one |

## Method

- Thresholds were chosen on **seed 42** by F1, one detector at a time (sweep below).
- They are then scored, unchanged, on **four held-out seeds** (7, 101, 2024, 31337). Each seed produces different
  outlets, beats, assortments and scenarios.
- **Precision** counts every flagged outlet that was not planted as a false positive: decoys and ordinary outlets alike.
- `salesforge pipeline` regenerates these numbers into `data/seed/evaluation.json`.

## Held-out results (mean over 4 seeds)

| Detector | Precision | Recall | F1 | Decoys flagged |
|---|---:|---:|---:|---:|
| Stock Risk | 0.96 (min 0.93) | 0.91 (min 0.88) | 0.93 | 13 / 320 |
| Revenue Recovery | 0.78 (min 0.75) | 0.68 (min 0.58) | 0.72 | 9 / 320 |
| Cross-Sell | 0.74 (min 0.69) | 0.72 (min 0.63) | 0.72 | 19 / 320 |
| Inactive Outlet | 1.00 | 1.00 | 1.00 | 0 / 320 |

**Inactive Outlet** is easy by construction: in this simulation every ordinary outlet orders at least once a
fortnight, so a 30-day silence is unambiguous. Real data would be noisier.

**Revenue Recovery** is the hard one, and the reason it is a statistical test rather than a percentage rule. Its
first version compared the last 30 days with the previous 30. That flagged 557 outlets at 13% precision, because
a small outlet's monthly revenue swings by a third through chance alone. The current detector:

1. compares the last 60 days with the outlet's own six-month baseline;
2. scales that baseline by how much the median outlet moved over the same period, which removes seasonality;
3. requires the number of orders, out of the scheduled beat visits, to be unlikely at the outlet's usual rate
   (one-sided binomial test, p <= 0.01).

The recall ceiling comes from small outlets visited once a week: going from 7 orders to 3 in two months is not
distinguishable from bad luck, and the detector correctly refuses to call it.

## Threshold sweep (tuning seed)

| Detector | Setting | Precision | Recall |
|---|---|---:|---:|
| Revenue Recovery | p <= 0.001 | 0.94 | 0.61 |
| | p <= 0.005 | 0.84 | 0.67 |
| | **p <= 0.01** | **0.81** | **0.72** |
| | p <= 0.02 | 0.76 | 0.76 |
| | p <= 0.05 | 0.66 | 0.81 |
| Inactive Outlet | 21 days | 0.79 | 1.00 |
| | 25 days | 0.95 | 1.00 |
| | **30 days** | **1.00** | **1.00** |
| | 45 days | 1.00 | 0.78 |
| Stock Risk | 6% of days | 0.78 | 0.98 |
| | **8% of days** | **0.96** | **0.92** |
| | 10% of days | 0.99 | 0.85 |
| Cross-Sell | 85% of peers | 0.52 | 1.00 |
| | **90% of peers** | **0.69** | **0.74** |
| | 95% of peers | 0.93 | 0.22 |

The chosen settings sit in the middle of smooth curves, not on a cliff edge, which is why they hold up on the
held-out seeds.

## Limits

- The generator and the detectors share a view of how outlets behave. Real data would reward re-tuning, and the
  sweep above is how to do it.
- Cross-sell ground truth is "the outlet lacks a category almost all its peers stock". Whether it would actually
  sell there is unknowable from sales data; that is what the outcome tracking in the app is for.
