import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]      # works whatever folder you launch from

@st.cache_data
def load():
    rules = json.loads((ROOT / 'models/rules.json').read_text(encoding='utf-8'))
    for r in rules:
        r['antecedents'] = frozenset(r['antecedents'])
    meta = json.loads((ROOT / 'models/metadata.json').read_text(encoding='utf-8'))
    products = pd.read_csv(ROOT / 'data/products.csv').set_index('Item')
    return rules, meta, products


# Recommendation engine section
def recommend(basket, rules, k=5):
    basket = set(basket)
    best = {}
    for r in rules:
        if r['antecedents'] <= basket and r['consequent'] not in basket:   # subset match; never re-suggest
            c = r['consequent']
            if c not in best or r['lift'] > best[c]['lift']:            # two rules, same item: keep higher lift
                best[c] = r
    return sorted(best.values(), key=lambda r: r['lift'], reverse=True)[:k]


def strength(lift):
    if lift >= 6:   return 'very strong'
    if lift >= 3:   return 'strong'
    if lift >= 1.5: return 'moderate'
    return 'weak'


def popular(basket, meta, k=5, exclude=('Sac réutilisable',)):
    s = pd.Series(meta['item_support']).sort_values(ascending=False)
    return [i for i in s.index if i not in basket and i not in exclude][:k]


# Check if page opens and if caption shows rule count
rules, meta, products = load()
st.set_page_config(page_title='Boréal Marché', layout='wide')
st.title('Boréal Marché — recommendations')
st.caption(f"{meta['n_rules']} rules mined on {meta['mined_on']} · min_support {meta['min_support']} · coverage {meta['coverage']}/98")


# State of the basket
if 'basket' not in st.session_state:
    st.session_state.basket = []
cat_col, basket_col, reco_col = st.columns([1.2, 1, 1.4])


# Catalogue section
with cat_col:
    st.header('1 · Catalogue')
    cat = st.selectbox('Category', ['All'] + sorted(products.Category.unique()))
    q = st.text_input('Search')
    view = products if cat == 'All' else products[products.Category == cat]
    if q:
        view = view[view.index.str.contains(q, case=False) | view.Item_EN.str.contains(q, case=False)]
    for item, p in view.iterrows():
        a, b = st.columns([3, 1])
        a.write(f'**{item}** · {p.Category} · {p.Price:.2f} $')
        if b.button('Add', key=f'add_{item}', disabled=item in st.session_state.basket):
            st.session_state.basket.append(item)
            st.rerun()


# basket section
with basket_col:
    st.header('2 · Basket')
    if not st.session_state.basket:
        st.write('Your basket is empty.')
    for item in st.session_state.basket:
        p = products.loc[item]
        a, b = st.columns([3, 1])
        a.write(f'{item} · {p.Category} · {p.Price:.2f} $')
        if b.button('Remove', key=f'rm_{item}'):
            st.session_state.basket.remove(item)
            st.rerun()
    total = products.loc[st.session_state.basket, 'Price'].sum() if st.session_state.basket else 0
    st.metric('Total', f'{total:.2f} $')
    if st.button('Clear basket'):
        st.session_state.basket = []
        st.rerun()


# Recommendations and edge cases
with reco_col:
    st.header('3 · Recommendations')
    basket = st.session_state.basket
    ms = meta['min_support']

    for item in basket:                                   # edge case: very rare product
        sup = meta['item_support'][item]
        if sup < ms:
            st.info(f'**{item}** appears in only {sup:.2%} of baskets, below the {ms:.0%} mining '
                    f'threshold, so it is in no rule and cannot trigger or receive suggestions.')

    recs = recommend(basket, rules)
    if not basket:                                        # edge case: empty basket
        st.warning('Your basket is empty, so no rule can fire. Showing popular products instead.')
    elif not recs:                                        # edge case: no rule fires
        st.warning('No rule matches this basket. Showing popular products instead.')

    # Recommendation cards
    if recs:
        for r in recs:
            c = r['consequent']; p = products.loc[c]
            X = ', '.join(sorted(r['antecedents']))
            with st.container(border=True):
                st.subheader(f'{c} · {p.Price:.2f} $')
                st.caption(f"{p.Category} · {strength(r['lift'])}")
                st.write(f"Because your basket contains {X}, customers who buy that also buy {c} "
                         f"{r['confidence']:.0%} of the time — that is {r['lift']:.1f}× more often than average.")
                m1, m2, m3 = st.columns(3)
                m1.metric('Support', f"{r['support']:.2%}")
                m2.metric('Confidence', f"{r['confidence']:.0%}")
                m3.metric('Lift', f"{r['lift']:.2f}")
    
    # Rules that "fired" and fallback list
    if recs:
        for r in recs:
            c = r['consequent']; p = products.loc[c]
            X = ', '.join(sorted(r['antecedents']))
            with st.container(border=True):
                st.subheader(f'{c} · {p.Price:.2f} $')
                st.caption(f"{p.Category} · {strength(r['lift'])}")
                st.write(f"Because your basket contains {X}, customers who buy that also buy {c} "
                         f"{r['confidence']:.0%} of the time — that is {r['lift']:.1f}× more often than average.")
                m1, m2, m3 = st.columns(3)
                m1.metric('Support', f"{r['support']:.2%}")
                m2.metric('Confidence', f"{r['confidence']:.0%}")
                m3.metric('Lift', f"{r['lift']:.2f}")

    # Recommendation Explanation
    X = ', '.join(sorted(r['antecedents']))
    st.write(f"Because your basket contains {X}, customers who buy that also buy {c} "
         f"{r['confidence']:.0%} of the time — that is {r['lift']:.1f}× more often than average.")