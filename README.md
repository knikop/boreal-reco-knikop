# boreal-reco-knikop

A basket-based recommendation engine for **Boréal Marché**, a Québec online grocery store. It answers one question:

> *Given what this customer has already put in their basket, what should we suggest next — and why?*

Rules are mined offline with **Apriori** (`mlxtend`) from one year of transactions: 1,000,000 baskets and 98 products. A **Streamlit** app then serves suggestions instantly and explains each one with the rule behind it.


## Overview
The system is split in two, and the app never mines anything.

| | Offline — mining | Online — recommending |
| --- | --- | --- |
| Where | `notebooks/01_mining.ipynb` | `app/streamlit_app.py` |
| What | Loads transactions, builds the boolean table, runs Apriori, filters rules | Loads the saved rules, matches them to the basket, ranks by lift |
| Output / input | writes `models/rules.json` and `models/metadata.json` | reads `models/rules.json` and `models/metadata.json` |
| Cost | about 3 minutes for the whole notebook | instant |

```
boreal-reco-knikop/
├── README.md
├── requirements.txt
├── data/
│   ├── transactionsdata.zip     ← 8,379,837 rows (TransactionID, Date, CustomerID, Item)
│   └── products.csv             ← 98 products (Item, Item_EN, Category, Price)
├── notebooks/
│   └── 01_mining.ipynb          ← executed, all outputs visible
├── models/
│   ├── rules.json               ← 2,894 filtered rules
│   └── metadata.json            ← thresholds, mining date, counts, coverage, item frequencies
├── app/
│   └── streamlit_app.py
├── reports/
│   ├── benchmark.md             ← timing and memory measurements
│   ├── apriori_default_runs.csv
│   └── apriori_lowmem_runs.csv
└── docs/screenshots/            ← app screenshots used below
```

## How to run 

Tested with Python 3.12.16, pandas 3.1.0, numpy 2.5.4, mlxtend 0.25.0.

```bash
git clone https://github.com/knikop/boreal-reco-knikop.git
cd boreal-reco-knikop

conda create -n boreal python=3.12
conda activate boreal
pip install -r requirements.txt
```

**1. Mine the rules (optional — `models/` is already committed).** Open `notebooks/01_mining.ipynb` and run *Kernel → Restart & Run All* (about 3 minutes). The slow default-settings Apriori test is off by default (`RUN_DEFAULT_APRIORI = False` in the first cell), because it needs 8–73 GB of RAM.

**2. Start the app** from the repository root:

```bash
streamlit run app/streamlit_app.py
```

The app only reads `models/rules.json`, `models/metadata.json` and `data/products.csv`. It does not import mlxtend.


## Results


## Decisions


## Traps I hit


## Edge Cases


## Limitations

1. **41 of 98 products can never be recommended.** These are the five specialty items (about 0.08% support, below any affordable threshold), the bag (excluded on purpose) and 35 everyday staples that are bought with everything, so no rule reaches lift 1.2. This builds in popularity bias. *Fix:* item-to-item lift from the co-occurrence matrix for rare items, per-category support thresholds, and a content-based fallback within the category.
2. **No notion of time.** One rule set covers the whole year, but 47% of year-round rules don't exist in January data. *Fix:* one rule set per season, switched by date, plus monthly re-mining (18 s per run).
3. **Not personalised.** Two customers with the same basket get the same suggestions, even though `CustomerID` is in the data. *Fix:* use purchase history (customer-level collaborative filtering).
4. **Cold start.** An empty basket can only show best-sellers, which reinforces popularity.

## Ethics

### 3 ethics points

- **Law 25 (Québec):** every suggestion can be traced to a named rule with its three metrics in "Rules that fired", so the automated decision is explainable to the customer.
- **Correlation is not causation:** the data reproduces the famous "diapers and beer" story from retail analytics. Couches → Bière has confidence 36.6% and lift 2.43, so diaper buyers buy beer 2.4× more often than average. The rule proves no causal link. A hidden third factor, such as a parent doing a big weekend shop, can drive both purchases, and the rule cannot tell which way influence runs, if it runs at all. Putting beer next to diapers might change nothing.
- **Reinforcement bias:** only 57 of 98 products can ever be suggested, so the system keeps promoting what is already bought together. Recommendations then shape future data, which locks the pattern in.