# Benchmark — Apriori on 1,000,000 baskets

All measurements come from `notebooks/01_mining.ipynb`, run on my machine.

| | |
| --- | --- |
| Machine | _CPU model · 16GB RAM · Windows 10 version 22H2_ |
| Environment | conda env `Boreal-New` · Python 3.12.16 · pandas 3.1.0 · numpy 2.5.4 · mlxtend 0.25.0 |
| Data | 8,379,837 rows · 1,000,000 baskets · 98 products · 8.38 items per basket |


## 1. Long → wide format

Apriori needs a boolean baskets × products table (1,000,000 × 98).

| Method | Time | Memory |
| --- | --- | --- |
| `pd.crosstab(...).astype(bool)` | 63.4 s | builds an int64 count table first (8 bytes per cell) |
| `pd.factorize` + NumPy bool array | **1.04 s** | **106 MB** (98 MB of bool data + 8 MB int64 TransactionID index) |

The fast method is about 61× quicker. It turns basket IDs and item names into integer codes and writes `True` straight into a 1-byte boolean array by position, so there is no grouping, sorting or int64 intermediate table.

## 2. Apriori with default settings (`low_memory=False`)

| min_support | Itemsets | Rules | Time | Peak memory | Outcome |
| --- | --- | --- | --- | --- | --- |
| 0.05 | 191 | — | 64.4 s | not measured | OK |
| 0.02 | 658 | — | 210.3 s | ~8 GB (heavy swapping) | OK on the second attempt, MemoryError on the first |
| 0.01 | — | — | 132.7 s | needed 14.2 GiB | **MemoryError** |
| 0.005 | — | — | 161.7 s | needed 72.6 GiB | **MemoryError** |

Exact error messages:

```
min_support=0.02 (first attempt): MemoryError: Unable to allocate 7.97 GiB for an array with shape (4278, 2, 1000000) and data type bool
min_support=0.01:                 MemoryError: Unable to allocate 14.2 GiB for an array with shape (5099, 3, 1000000) and data type bool
min_support=0.005:                MemoryError: Unable to allocate 72.6 GiB for an array with shape (25975, 3, 1000000) and data type bool
```

At 0.02 the outcome depended on how much RAM happened to be free. The first attempt failed with the 7.97 GiB error. A later run succeeded, but only after Windows swapped memory to disk for 3.5 minutes and froze the PC. The full default-settings test took about 10 minutes. It is switched off in the notebook (`RUN_DEFAULT_APRIORI = False`), which displays these recorded results instead.

### Why it fails

With `low_memory=False`, mlxtend checks every candidate itemset against every basket in one vectorised step. To do that it builds a single boolean array of shape **(candidate itemsets × items per candidate × baskets)**, and the array's size is the product of those three numbers.

- At 0.01: 5,099 candidates × 3 items × 1,000,000 baskets = 15.3 billion booleans = **14.2 GiB**.
- At 0.005: 25,975 × 3 × 1,000,000 = 77.9 billion booleans = **72.6 GiB**.

Two things make this grow so fast as min_support drops:

1. **The number of candidates grows combinatorially.** More items pass the threshold, and every pair or triple of frequent items becomes a candidate: 4,278 → 5,099 → 25,975.
2. **Every candidate is multiplied by 1,000,000 baskets.** Even a modest candidate count turns into billions of cells.

Sac réutilisable makes it worse. At 90% support it is frequent enough to combine with almost every other frequent item, so it adds candidates at every level ({X, bag}, {X, Y, bag} …).

### The fix

`low_memory=True` makes mlxtend count candidates in small batches instead of materialising the full array, so memory stays flat no matter how many candidates there are. On this data it is also much faster: 18.3 s instead of a MemoryError at 0.01, because the default version spends most of its time allocating and swapping.

## 3. Apriori with `low_memory=True` (min_confidence = 0.1)

| min_support | Itemsets | Rules | Time | Peak memory | Longest itemset | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| 0.05 | 191 | 306 | 3.5 s | 0.16 GB | 4 | OK |
| 0.02 | 658 | 3,468 | 7.7 s | 0.18 GB | 5 | OK |
| 0.01 | 2,267 | 13,731 | 18.3 s | 0.18 GB | 7 | OK — **chosen** |
| 0.005 | 7,106 | 41,952 | 38.5 s | 0.18 GB | 7 | OK |

Peak memory is measured with `tracemalloc` during the `apriori` + `association_rules` calls. The 106 MB basket table is not included. Each time support halves, rules multiply by about 3–4× and time roughly doubles.

## 4. Chosen thresholds and final rule set

| Setting | Value | Why |
| --- | --- | --- |
| min_support | 0.01 | 13,731 rules in 18 s with itemsets up to 7 items. 0.005 triples the rules without making any new product recommendable. |
| min_confidence | 0.1 | Floor to drop rules that almost never fire. |
| min_lift | 1.2 | lift > 1 still kept 586 of the 1,017 "X → Sac réutilisable" rules (lift 0.992–1.009). lift > 1.2 removes all of them. |
| Consequent size | 1 item | One rule = one suggested product. |
| **Rules saved** | **2,894** | `models/rules.json`, 0.43 MB |

## 5. Coverage

| Filter | Products that can be recommended |
| --- | --- |
| lift > 1 | 74 / 98 |
| lift > 1.2 (final) | **57 / 98** |

The 41 products that can never be recommended fall into three groups:

- **Below min_support (5):** Caviar, Foie gras, Safran, Huile de truffe, Vinaigre balsamique vieilli. Each is in about 0.08% of baskets, so they appear in no rule.
- **Excluded on purpose (1):** Sac réutilisable. Its rules have lift ≈ 1.00, so the lift filter removes them.
- **Bought with everything (35):** staples such as Lait 2%, Fromage cheddar, Papier hygiénique, Savon à vaisselle and Céréales. They are common, but no basket makes them more likely, so no rule reaches lift 1.2.

The 74 → 57 drop also shows that lift > 1 inflated coverage with noise rules.

## 6. Limitations

1. **41 of 98 products can never be recommended**, including the high-value specialty items. Fix: compute item-to-item lift directly from the co-occurrence matrix for rare items, or use per-category support thresholds, plus a content-based fallback within the category.
2. **No notion of time or season.** 6,394 of the 13,731 year-round rules (47%) don't exist in January data, and 21,458 rules exist only in summer. Fix: one rule set per season (or month), switched by date, and monthly re-mining. At 18 s per run, re-mining costs almost nothing.
