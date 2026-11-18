"""Retail Analysis: customer segmentation and market basket analysis for any file of sales.

Run it with:  python -m streamlit run app.py
"""
import sys
sys.path.insert(0, "src")

import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from retail_analysis.clean import SHOPS, clean, load
from retail_analysis.forward import groups_next, over_time, pairs_next, still_linked, verdicts
from retail_analysis.market_basket import baseline_lift, families, pairs, rules
from retail_analysis.summary import best_month, summarize_shop
from retail_analysis.segmentation import GROUPS, by_group, group, profile, repeat_buying, scores, summarize

WHITE, SILVER, GREY, JADE, GOLD, CORAL = "#f2f2f0", "#d4d6da", "#8d8d90", "#5fd0a0", "#e3b341", "#ff7b72"
COLORS = dict(zip(GROUPS, ["#7fb4d8", JADE, "#9fd9bd", WHITE, SILVER, "#c9a25a", GREY]))
PALETTE = [JADE, WHITE, "#c9a25a", "#9fd9bd", SILVER, "#e0787a", "#7fb4d8", GREY]
NEEDED = {"order": "Order number", "customer": "Customer", "product": "Product code", "name": "Product name",
          "quantity": "Quantity", "price": "Price each", "when": "Date"}

st.set_page_config("Retail Analysis", layout="wide")
st.markdown("<style>[data-testid='stElementToolbar']{display:none} .block-container{padding-top:3.5rem}</style>", unsafe_allow_html=True)


def chart(fig, height=380):
    fig.update_layout(template="plotly_dark", paper_bgcolor="black", plot_bgcolor="black", height=height,
                      margin=dict(l=10, r=10, t=30, b=10), legend_title_text="", font_color=SILVER)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


@st.cache_data(show_spinner="Reading and cleaning the sales")
def prepare(file, columns, not_products):
    if isinstance(file, str):
        return clean(load(file), not_products)
    table = (pd.read_csv if file.name.endswith(".csv") else pd.read_excel)(file).rename(columns=columns)
    table["when"] = pd.to_datetime(table["when"])
    table[["order", "product", "name"]] = table[["order", "product", "name"]].astype(str)
    return clean(table.assign(country="Unknown"))


@st.cache_data(show_spinner="Segmenting customers")
def segment(sales):
    customers = summarize(sales)
    customers["group"] = group(customers)
    return customers, by_group(customers), profile(sales, customers), repeat_buying(sales)


find_pairs = st.cache_data(pairs, show_spinner="Running the market basket analysis")
check_groups = st.cache_data(groups_next, show_spinner="Checking the segments against later sales")
check_pairs = st.cache_data(pairs_next, show_spinner="Checking the pairs against later sales")
check_over_time = st.cache_data(over_time, show_spinner="Repeating the check at earlier cutoff days")

# ---- Sidebar: which sales to look at -------------------------------------------------
with st.sidebar:
    st.title("Retail Analysis")
    st.caption("Customer segmentation and market basket analysis")
    picked_shop = st.selectbox("Demo shop", sorted(SHOPS, key=lambda name: ["Amazon", "US", "UK"].index(name.split()[0])))
    upload = st.file_uploader("Or your own sales file", type=["csv", "xlsx"], help="One row per product on an order.")
    if upload:
        header = list((pd.read_csv if upload.name.endswith(".csv") else pd.read_excel)(upload, nrows=0).columns)
        upload.seek(0)
        st.caption("Match your columns")
        columns = {st.selectbox(label, header, index=min(i, len(header) - 1)): key for i, (key, label) in enumerate(NEEDED.items())}
        sign = st.text_input("Currency sign", "$")
        sales, removed = prepare(upload, columns, None)
    else:
        shop = SHOPS[picked_shop]
        st.caption(shop["about"])
        sign = shop["money"]
        sales, removed = prepare(shop["file"], None, shop["not_products"])

customers, groups, shopping, back = segment(sales)
found = find_pairs(sales)

# ---- Top line ------------------------------------------------------------------------
tiles = st.columns(5)
tiles[0].metric("Revenue", f"{sign}{sales.revenue.sum():,.0f}")
tiles[1].metric("Customers", f"{len(customers):,}")
tiles[2].metric("Orders", f"{sales.order.nunique():,}")
tiles[3].metric("Big spenders' share of spend", f"{groups.share_of_spend.get('Big spenders', 0):.0%}")
tiles[4].metric("Product pairs found", f"{len(found):,}")

overview, segments, quiet, basket, held = st.tabs(["Overview", "Customer Segmentation", "Going quiet", "Market Basket Analysis", "Testing the findings"])

def colored(sentence, color):
    """Color the figures in a sentence. Bold phrases without a digit stay plain bold."""
    paint = lambda m: f"<b style='color:{color}'>{m.group(1)}</b>" if any(ch.isdigit() for ch in m.group(1)) else f"<b>{m.group(1)}</b>"
    return re.sub(r"\*\*(.+?)\*\*", paint, sentence)


with overview:
    words = summarize_shop(sales, customers, groups, found, check_groups(sales, 90), still_linked(check_pairs(sales, 90)).mean(), sign)
    left, right = st.columns(2)
    with left:
        st.subheader("What we learned")
        st.markdown("".join(f"<p>{colored(line, JADE)}</p>" for line in words["learned"]), unsafe_allow_html=True)
    with right:
        st.subheader("What to do about it")
        st.markdown("".join(f"<p>{number}. {colored(line, GOLD)}</p>" for number, line in enumerate(words["actions"], 1)), unsafe_allow_html=True)
    st.divider()

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Revenue by month")
        monthly = sales.set_index("when")["revenue"].resample("MS").sum()
        best, _ = best_month(sales)
        fig = go.Figure(go.Bar(x=monthly.index, y=monthly.values, marker_color=[GOLD if month == best else SILVER for month in monthly.index], hovertemplate=sign + "%{y:,.0f}<extra></extra>"))
        fig.add_hline(y=monthly.median(), line_dash="dot", line_color=GREY, annotation_text="Typical month", annotation_font_color=SILVER, annotation_position="top left")
        fig.add_annotation(x=best, y=monthly[best], text=f"Best month: {best:%b %Y}<br>{sign}{monthly[best]:,.0f}", font_color=GOLD, showarrow=False, yshift=22)
        chart(fig.update_yaxes(tickprefix=sign))
    with right:
        st.subheader("Top products")
        st.caption("Revenue, and each product's share of all revenue.")
        top = sales.groupby("name")["revenue"].sum().nlargest(10)[::-1]
        fig = go.Figure(go.Bar(x=top.values, y=top.index.str.title().str[:32], orientation="h", text=[f"{sign}{v:,.0f}  ·  {v / sales.revenue.sum():.1%}" for v in top.values],
                               textposition="outside", textfont_color=SILVER, cliponaxis=False, marker_color=[JADE] * 9 + [GOLD], hovertemplate=sign + "%{x:,.0f}<extra></extra>"))
        chart(fig.update_xaxes(tickprefix=sign, range=[0, top.max() * 1.7]), 360)

    left, right = st.columns([3, 2])
    with left:
        first = sales.groupby("customer")["when"].transform("min").dt.to_period("M")
        month = sales["when"].dt.to_period("M")
        if sales.loc[month == first, "revenue"].sum() >= 0.05 * sales["revenue"].sum():
            st.subheader("New and returning customers")
            st.caption("Each month's revenue, split by whether the customer's first order was that month.")
            split = sales.groupby([month.dt.to_timestamp(), (month == first).map({True: "New", False: "Returning"})])["revenue"].sum().unstack(fill_value=0)
            fig = go.Figure([go.Bar(x=split.index, y=split[name], name=name, marker_color=color, hovertemplate=sign + "%{y:,.0f}") for name, color in [("Returning", SILVER), ("New", JADE)]])
            chart(fig.update_layout(barmode="stack", legend_orientation="h", legend_y=1.12).update_yaxes(tickprefix=sign), 340)
        else:   # the same customers throughout, so show how many of them buy each month
            st.subheader("Customers buying each month")
            st.caption("How many different customers placed at least one order.")
            active = sales.groupby(month.dt.to_timestamp())["customer"].nunique()
            fig = go.Figure(go.Bar(x=active.index, y=active.values, marker_color=[GOLD if m == active.idxmax() else SILVER for m in active.index], hovertemplate="%{y:,} customers<extra></extra>"))
            chart(fig, 340)
    with right:
        st.subheader("Revenue by day of the week")
        weekdays = sales.groupby(sales["when"].dt.day_name())["revenue"].sum().reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]).fillna(0)
        fig = go.Figure(go.Bar(x=weekdays.index.str[:3], y=weekdays.values, marker_color=[GOLD if day == weekdays.idxmax() else SILVER for day in weekdays.index],
                               text=[f"{v / weekdays.sum():.0%}" for v in weekdays.values], textposition="outside", hovertemplate=sign + "%{y:,.0f}<extra></extra>"))
        chart(fig.update_yaxes(tickprefix=sign), 340)

    with st.expander("What cleaning removed"):
        st.caption("Returns are taken off the sales they undo, so an order placed and then cancelled does not count as revenue.")
        st.dataframe(pd.Series(removed, name="Count").map("{:,.0f}".format), width="content")

with segments:
    st.subheader("Seven segments, by how recently, how often and how much customers buy")
    shares = groups[["share_of_customers", "share_of_spend"]].rename(columns={"share_of_customers": "Share of customers", "share_of_spend": "Share of spend"})
    fig = go.Figure([go.Bar(name=g, y=shares.columns, x=shares.loc[g], orientation="h", marker_color=COLORS[g],
                            text=[f"{v:.0%}" for v in shares.loc[g]], textposition="inside", insidetextfont_color="black") for g in shares.index])
    chart(fig.update_layout(barmode="stack", legend_orientation="h", legend_y=1.25, legend_traceorder="normal").update_xaxes(tickformat=".0%"), 240)

    st.subheader("How each segment shops, and what to do about it")
    table = shopping.join(groups[["customers"]])[["customers", "average_order", "products_per_order", "orders_per_customer", "what_to_do", "leans_toward"]]
    st.dataframe(table.rename(columns={"customers": "Customers", "average_order": "Average order", "products_per_order": "Products per order",
                                       "orders_per_customer": "Orders each", "leans_toward": "Leans toward", "what_to_do": "What to do"}).rename_axis("Segment"),
                 width="stretch", column_config={"Average order": st.column_config.NumberColumn(format=f"{sign}%.0f"), "Products per order": st.column_config.NumberColumn(format="%.1f"),
                                                 "Orders each": st.column_config.NumberColumn(format="%.1f")})
    left, right = st.columns(2)
    with left:
        st.subheader("How the segments are drawn")
        st.caption("Every customer is scored 1 to 5 on recency and on frequency. The number is the customers in each square. Big spenders are the Best customers in the top twentieth by spend.")
        recent, often = scores(customers)
        count = pd.crosstab(recent, often)
        owner = customers["group"].replace("Big spenders", "Best customers").groupby([recent, often]).agg(lambda g: g.mode()[0]).unstack()
        fig = go.Figure(go.Heatmap(z=owner.map(GROUPS[1:].index).to_numpy(), x=count.columns, y=count.index, text=count.to_numpy(), texttemplate="%{text:,}",
                                   textfont_color="black", colorscale=[[i / 5, COLORS[g]] for i, g in enumerate(GROUPS[1:])], zmin=0, zmax=5, showscale=False,
                                   xgap=3, ygap=3, customdata=owner.to_numpy(), hovertemplate="%{customdata}<extra></extra>"))
        chart(fig.update_xaxes(title="How often they buy (5 is most often)", dtick=1).update_yaxes(title="How recently (5 is most recent)", dtick=1), 400)
    with right:
        st.subheader("Do customers come back?")
        st.caption("Rows are the month of a customer's first order. Columns are months after it.")
        grid = back.iloc[:-1, 1:12].head(12)
        fig = px.imshow(grid.to_numpy(float), x=[str(c) for c in grid.columns], y=[str(m) for m in grid.index], zmin=0, zmax=max(0.5, float(grid.max().max())),
                        color_continuous_scale=["black", JADE], text_auto=".0%", aspect="auto")
        chart(fig.update_coloraxes(showscale=False).update_xaxes(type="category").update_yaxes(type="category"), 400)
    st.subheader("Every customer")
    fig = px.scatter(customers.reset_index(), x="days_since", y="orders", size="spend", color="group", log_y=True, size_max=40,
                     color_discrete_map=COLORS, category_orders={"group": GROUPS}, hover_data={"customer": True, "spend": ":,.0f"},
                     labels={"days_since": "Days since last order", "orders": "Orders placed"})
    chart(fig.update_traces(marker_line_width=0, opacity=0.6).update_yaxes(dtick=1), 440)

with quiet:
    st.subheader("Customers worth contacting")
    st.caption("They ordered several times and have not been back lately. Sorted by what they have spent.")
    listed = customers[customers.group == "Going quiet"].sort_values("spend", ascending=False)
    favourite = sales[sales.customer.isin(listed.index)].groupby(["customer", "name"])["revenue"].sum().reset_index().sort_values("revenue").drop_duplicates("customer", keep="last").set_index("customer")["name"]
    shown = listed.assign(top_product=favourite.str.title(), last=listed["last"].dt.date)[["orders", "spend", "last", "days_since", "top_product"]]
    a, b, c = st.columns(3)
    a.metric("Customers", f"{len(listed):,}")
    b.metric("Their spend so far", f"{sign}{listed.spend.sum():,.0f}")
    c.metric("Typical days since last order", f"{listed.days_since.median():.0f}")
    st.dataframe(shown.rename(columns={"orders": "Orders", "spend": "Spend", "last": "Last order", "days_since": "Days since", "top_product": "Bought most"}),
                 width="stretch", height=520, column_config={"Spend": st.column_config.NumberColumn(format=f"{sign}%.0f")})

with basket:
    st.caption("Support is the share of all orders with both products. Confidence is the share of orders with the first that also have the second. "
               "Lift is how many times more often than chance they sell together. "
               f"Big orders push every lift up a little: two unrelated products in this shop would show a lift of about {baseline_lift(sales):.1f}, so look for pairs far above that.")
    names = sorted(set(found.name_a.dropna()) | set(found.name_b.dropna()))
    picked = st.selectbox("Pick a product to see what sells with it", ["All products"] + names, format_func=str.title)
    listed = rules(found).sort_values("lift", ascending=False)
    listed = listed if picked == "All products" else listed[listed.buys == picked]
    st.subheader("Rules: customers who buy this also buy that")
    table = listed.head(50).assign(buys=lambda t: t.buys.str.title().str.strip(), also_buys=lambda t: t.also_buys.str.title().str.strip())
    st.dataframe(table.rename(columns={"buys": "Buys", "also_buys": "Also buys", "together": "Orders with both", "support": "Support", "confidence": "Confidence", "lift": "Lift"}),
                 hide_index=True, width="stretch", height=390,
                 column_config={"Support": st.column_config.NumberColumn(format="percent"), "Confidence": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
                                "Lift": st.column_config.NumberColumn(format="%.0fx")})
    left, right = st.columns([2, 3])
    with left:
        st.subheader("Every pair")
        st.caption("Up and to the right is best: bought together often, and far more than chance.")
        near = found if picked == "All products" else found[(found.name_a == picked) | (found.name_b == picked)]
        fig = go.Figure(go.Scattergl(x=found.together, y=found.lift, mode="markers", marker=dict(color=GREY, size=4, opacity=0.35), hoverinfo="skip"))
        fig.add_scattergl(x=near.head(25).together, y=near.head(25).lift, mode="markers", marker=dict(color=JADE, size=8),
                          text=near.head(25).name_a.str.title() + " + " + near.head(25).name_b.str.title(), hoverinfo="text")
        chart(fig.update_xaxes(type="log", dtick=1, title="Orders with both").update_yaxes(type="log", dtick=1, title="Lift").update_layout(showlegend=False), 560)
    with right:
        st.subheader("Product families")
        st.caption("Products joined by their strongest pairs fall into families that sell together. Each one is a ready made bundle. Hover for names.")
        spots = families(found, strongest=min(150, len(found))).set_index("name")
        fig = go.Figure()
        for a, b in zip(found.head(150).name_a, found.head(150).name_b):
            if a in spots.index:
                fig.add_scatter(x=[spots.x[a], spots.x[b]], y=[spots.y[a], spots.y[b]], mode="lines", line=dict(color="#55575c", width=1), hoverinfo="skip")
        fig.add_scatter(x=spots.x, y=spots.y, mode="markers", text=spots.index.str.title(), hoverinfo="text",
                        marker=dict(size=10 + 3 * spots.links, color=[PALETTE[(f - 1) % 8] for f in spots.family], line_width=0))
        for number, members in spots.groupby("family"):
            fig.add_annotation(x=(number - 1) % 4, y=-((number - 1) // 4) - 0.47, text=f"{members.index[0].title().strip()[:24]} ({len(members)})", showarrow=False, font_color=SILVER, font_size=11)
        chart(fig.update_layout(showlegend=False).update_xaxes(visible=False, range=[-0.5, 3.5]).update_yaxes(visible=False), 560)

with held:
    st.subheader("Can the segments and product pairs be trusted?")
    st.markdown("The other tabs describe the past. This tab checks whether those descriptions predict what happens next, which is the only reason to act on them.")
    days = st.select_slider("Days hidden for the test", [30, 60, 90, 120], 90)
    st.markdown(f"**How the test works.** Pretend today is {days} days before the data ends. The segments and product pairs are built using only the sales up to that day. "
                f"The {days} days that were hidden then show what those customers and products really did. "
                "If Big spenders came back and spent far more than Lost customers, the segments were telling the truth.")
    st.caption("A longer window gives customers more time to return, so every bar rises. The order of the bars is what matters.")
    table = check_groups(sales, days)
    each = table.drop("Everyone")
    checked = check_pairs(sales, days)
    checks = check_over_time(sales, days)

    tests = verdicts(table, checked, checks, sign)
    passed = sum(t["passed"] for t in tests)
    color = JADE if passed == len(tests) else GOLD if passed >= len(tests) / 2 else CORAL
    answer = "Yes, on this data." if passed == len(tests) else "Partly. Read the failed tests before relying on them." if passed >= len(tests) / 2 else "No, not on this data."
    st.markdown(f"<p style='font-size:22px'><b style='color:{color}'>{passed} of {len(tests)} tests passed.</b> {answer}</p>", unsafe_allow_html=True)
    cards = "".join(
        f"<div style='border:1px solid #232527;border-left:3px solid {JADE if t['passed'] else CORAL};border-radius:8px;padding:12px 14px'>"
        f"<b style='color:{JADE if t['passed'] else CORAL}'>{'PASSED' if t['passed'] else 'FAILED'}</b> &nbsp; <b>{t['test']}</b>"
        f"<div style='color:{GREY};font-size:13px;margin-top:4px'>To pass: {t['rule']}</div><div style='margin-top:4px'>{t['result']}</div></div>" for t in tests)
    st.markdown(f"<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:10px;margin-bottom:18px'>{cards}</div>", unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Customer segments: share who ordered again")
        fig = go.Figure(go.Bar(x=each.index, y=each.came_back, marker_color=[COLORS[g] for g in each.index], text=[f"{v:.0%}" for v in each.came_back]))
        chart(fig.add_hline(y=table.loc["Everyone", "came_back"], line_dash="dot", line_color=SILVER, annotation_text="Everyone").update_yaxes(tickformat=".0%"))
    with right:
        st.subheader("Customer segments: average spend afterward")
        chart(go.Figure(go.Bar(x=each.index, y=each.average_spend_after, marker_color=[COLORS[g] for g in each.index])).update_yaxes(tickprefix=sign))
    kept, bar = int(still_linked(checked).sum()), 2 * checked.baseline_after.iloc[0]
    st.subheader(f"Market basket: {kept} of the {len(checked)} strongest pairs kept selling together")
    fig = go.Figure(go.Scatter(x=checked.lift, y=checked.lift_after.clip(lower=0.5), mode="markers", marker=dict(color=JADE, size=8),
                               text=checked.name_a.str.title() + " + " + checked.name_b.str.title(), hoverinfo="text"))
    st.caption(f"Each dot is a pair. To count as still linked, a pair must sit above the dotted line: twice the lift that random baskets give in this shop, which is about {bar / 2:.1f}.")
    chart(fig.add_hline(y=bar, line_dash="dot", line_color=SILVER).update_xaxes(type="log", dtick=1, title="Lift before").update_yaxes(type="log", dtick=1, title="Lift after"), 360)

    st.subheader("The same check at earlier cutoff days")
    st.caption(f"One window could be luck. The check is repeated at cutoff days {days} days apart, as far back as the sales allow. Each dot is a separate check.")
    left, right = st.columns(2)
    for place, column, title, axis in [(left, "came_back", "Share who ordered again", dict(tickformat=".0%")), (right, "average_spend_after", "Average spend afterward", dict(type="log", tickprefix=sign, dtick=1))]:
        table = checks.pivot(index="cutoff", columns="group", values=column)
        fig = go.Figure([go.Scatter(x=table.index, y=table[g], name=g, mode="lines+markers", line_color=COLORS[g]) for g in GROUPS if g in table])
        with place:
            st.markdown(f"**{title}**")
            chart(fig.update_yaxes(**axis).update_xaxes(title="Cutoff day").update_layout(showlegend=column == "average_spend_after"), 360)
    linked = checks[checks.group == "Pairs"]
    st.caption(f"Strongest pairs still linked afterward: between {linked.came_back.min():.0%} and {linked.came_back.max():.0%} across {len(linked)} cutoff days.")
