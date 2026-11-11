"""ShopLens: open a file of sales and see who the customers are, who is drifting away and what sells together.

Run it with:  python -m streamlit run app.py
"""
import sys
sys.path.insert(0, "src")

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from shoplens.baskets import pairs
from shoplens.clean import ONLINE_RETAIL, clean, load
from shoplens.customers import GROUPS, by_group, group, repeat_buying, summarize
from shoplens.forward import groups_next, pairs_next

WHITE, SILVER, GREY, JADE, RED = "#f2f2f0", "#d4d6da", "#8d8d90", "#5fd0a0", "#e0787a"
COLORS = dict(zip(GROUPS, [JADE, "#9fd9bd", WHITE, SILVER, "#c9a25a", GREY]))
NEEDED = {"order": "Order number", "customer": "Customer", "product": "Product code", "name": "Product name",
          "quantity": "Quantity", "price": "Price each", "when": "Date"}

st.set_page_config("ShopLens", layout="wide")
st.markdown("<style>[data-testid='stElementToolbar']{display:none} .block-container{padding-top:3.5rem}</style>", unsafe_allow_html=True)


def chart(fig, height=380):
    fig.update_layout(template="plotly_dark", paper_bgcolor="black", plot_bgcolor="black", height=height,
                      margin=dict(l=10, r=10, t=30, b=10), legend_title_text="", font_color=SILVER)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


@st.cache_data(show_spinner="Reading and cleaning the sales")
def prepare(file, columns):
    return clean(load(file, columns) if isinstance(file, str) else read_upload(file, columns))


def read_upload(file, columns):
    table = (pd.read_csv if file.name.endswith(".csv") else pd.read_excel)(file).rename(columns=columns)
    table["when"] = pd.to_datetime(table["when"])
    table[["order", "product"]] = table[["order", "product"]].astype(str)
    return table.assign(country=table.get("country", "Unknown"))


@st.cache_data(show_spinner="Sorting customers into groups")
def describe(sales):
    customers = summarize(sales)
    customers["group"] = group(customers)
    return customers, by_group(customers), repeat_buying(sales)


find_pairs = st.cache_data(pairs, show_spinner="Finding products bought together")
check_groups = st.cache_data(groups_next, show_spinner="Checking the groups against later sales")
check_pairs = st.cache_data(pairs_next, show_spinner="Checking the pairs against later sales")

# ---- Sidebar: which sales to look at -------------------------------------------------
with st.sidebar:
    st.title("ShopLens")
    upload = st.file_uploader("Your sales file", type=["csv", "xlsx"], help="One row per product on an order. Leave empty to use the demo shop.")
    columns = ONLINE_RETAIL
    if upload:
        header = list((pd.read_csv if upload.name.endswith(".csv") else pd.read_excel)(upload, nrows=0).columns)
        upload.seek(0)
        st.caption("Match your columns")
        columns = {st.selectbox(label, header, index=min(i, len(header) - 1)): key for i, (key, label) in enumerate(NEEDED.items())}
    else:
        st.caption("Showing the demo shop: a UK online gift retailer, December 2010 to December 2011.")

sales, removed = prepare(upload or "data/online_retail.parquet", columns)
customers, groups, back = describe(sales)

# ---- Top line ------------------------------------------------------------------------
tiles = st.columns(5)
tiles[0].metric("Revenue", f"£{sales.revenue.sum():,.0f}")
tiles[1].metric("Customers", f"{len(customers):,}")
tiles[2].metric("Orders", f"{sales.order.nunique():,}")
tiles[3].metric("Best customers' share of spend", f"{groups.share_of_spend.get('Best customers', 0):.0%}")
tiles[4].metric("Going quiet", f"{int(groups.customers.get('Going quiet', 0)):,}")

overview, who, quiet, together, held = st.tabs(["Overview", "Customers", "Going quiet", "Bought together", "Did it hold up"])

with overview:
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Revenue by month")
        monthly = sales.set_index("when")["revenue"].resample("MS").sum()
        chart(go.Figure(go.Bar(x=monthly.index, y=monthly.values, marker_color=SILVER)).update_yaxes(tickprefix="£"))
    with right:
        st.subheader("Top products")
        top = sales.groupby("name")["revenue"].sum().nlargest(10)[::-1]
        chart(go.Figure(go.Bar(x=top.values, y=top.index.str.title().str[:32], orientation="h", marker_color=JADE)).update_xaxes(tickprefix="£"))
    st.subheader("What cleaning removed")
    st.caption("Returns are taken off the sales they undo, so an order placed and then cancelled does not count as revenue.")
    st.dataframe(pd.Series(removed, name="Count").map("{:,.0f}".format), width="content")

with who:
    st.subheader("Six groups, by how recently and how often they buy")
    shares = groups[["share_of_customers", "share_of_spend"]].rename(columns={"share_of_customers": "Share of customers", "share_of_spend": "Share of spend"})
    fig = go.Figure([go.Bar(name=g, y=shares.columns, x=shares.loc[g], orientation="h", marker_color=COLORS[g],
                            text=[f"{v:.0%}" for v in shares.loc[g]], textposition="inside", insidetextfont_color="black") for g in shares.index])
    chart(fig.update_layout(barmode="stack", legend_orientation="h", legend_y=1.25, legend_traceorder="normal").update_xaxes(tickformat=".0%"), 240)
    left, right = st.columns(2)
    with left:
        st.subheader("Every customer")
        fig = px.scatter(customers.reset_index(), x="days_since", y="orders", size="spend", color="group", log_y=True, size_max=40,
                         color_discrete_map=COLORS, category_orders={"group": GROUPS}, hover_data={"customer": True, "spend": ":,.0f"},
                         labels={"days_since": "Days since last order", "orders": "Orders placed"})
        chart(fig.update_traces(marker_line_width=0, opacity=0.6).update_yaxes(dtick=1), 440)
    with right:
        st.subheader("Do customers come back?")
        st.caption("Rows are the month of a customer's first order. Columns are months after it.")
        grid = back.iloc[:-1, 1:12]
        fig = px.imshow(grid.to_numpy(float), x=[str(c) for c in grid.columns], y=[str(m) for m in grid.index], zmin=0, zmax=0.5,
                        color_continuous_scale=["black", JADE], text_auto=".0%", aspect="auto")
        chart(fig.update_coloraxes(showscale=False).update_xaxes(type="category").update_yaxes(type="category"), 400)

with quiet:
    st.subheader("Customers worth contacting")
    st.caption("They ordered several times and have not been back lately. Sorted by what they have spent.")
    listed = customers[customers.group == "Going quiet"].sort_values("spend", ascending=False)
    favourite = sales[sales.customer.isin(listed.index)].groupby(["customer", "name"])["revenue"].sum().reset_index().sort_values("revenue").drop_duplicates("customer", keep="last").set_index("customer")["name"]
    shown = listed.assign(top_product=favourite.str.title(), last=listed["last"].dt.date)[["orders", "spend", "last", "days_since", "top_product"]]
    a, b, c = st.columns(3)
    a.metric("Customers", f"{len(listed):,}")
    b.metric("Their spend so far", f"£{listed.spend.sum():,.0f}")
    c.metric("Typical days since last order", f"{listed.days_since.median():.0f}")
    st.dataframe(shown.rename(columns={"orders": "Orders", "spend": "Spend", "last": "Last order", "days_since": "Days since", "top_product": "Bought most"}),
                 width="stretch", height=520, column_config={"Spend": st.column_config.NumberColumn(format="£%.0f")})

with together:
    found = find_pairs(sales)
    names = sorted(set(found.name_a.dropna()) | set(found.name_b.dropna()))
    picked = st.selectbox("Pick a product to see what sells with it", ["All products"] + names, format_func=str.title)
    shown = found if picked == "All products" else found[(found.name_a == picked) | (found.name_b == picked)]
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Strongest pairs")
        table = shown.head(25).assign(Pair=lambda t: t.name_a.str.title().str.strip() + "  +  " + t.name_b.str.title().str.strip())
        st.dataframe(table[["Pair", "together", "chance_a_then_b", "lift"]].rename(columns={"together": "Orders with both", "chance_a_then_b": "Chance", "lift": "Lift"}),
                     hide_index=True, width="stretch", height=460,
                     column_config={"Pair": st.column_config.TextColumn(width="large"),
                                    "Chance": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1, help="Of orders with the first product, the share that also have the second"),
                                    "Lift": st.column_config.NumberColumn(format="%.0fx", help="How many times more often than chance")})
    with right:
        st.subheader("All pairs")
        st.caption("Up and to the right is best: bought together often, and far more than chance.")
        fig = go.Figure(go.Scattergl(x=found.together, y=found.lift, mode="markers", marker=dict(color=GREY, size=4, opacity=0.35), hoverinfo="skip"))
        fig.add_scattergl(x=shown.head(25).together, y=shown.head(25).lift, mode="markers", marker=dict(color=JADE, size=8),
                          text=shown.head(25).name_a.str.title() + " + " + shown.head(25).name_b.str.title(), hoverinfo="text")
        chart(fig.update_xaxes(type="log", dtick=1, title="Orders with both").update_yaxes(type="log", dtick=1, title="Times more than chance").update_layout(showlegend=False), 440)

with held:
    days = st.select_slider("Days held back", [30, 60, 90, 120], 90)
    st.caption(f"Everything is rebuilt from sales before the last {days} days. Those {days} days then show whether it meant anything.")
    table = check_groups(sales, days)
    each = table.drop("Everyone")
    left, right = st.columns(2)
    with left:
        st.subheader("Share who ordered again")
        fig = go.Figure(go.Bar(x=each.index, y=each.came_back, marker_color=[COLORS[g] for g in each.index], text=[f"{v:.0%}" for v in each.came_back]))
        chart(fig.add_hline(y=table.loc["Everyone", "came_back"], line_dash="dot", line_color=SILVER, annotation_text="Everyone").update_yaxes(tickformat=".0%"))
    with right:
        st.subheader("Average spend afterward")
        chart(go.Figure(go.Bar(x=each.index, y=each.average_spend_after, marker_color=[COLORS[g] for g in each.index])).update_yaxes(tickprefix="£"))
    checked = check_pairs(sales, days)
    kept = int((checked.lift_after > 1).sum())
    st.subheader(f"{kept} of the {len(checked)} strongest pairs kept selling together")
    fig = go.Figure(go.Scatter(x=checked.lift, y=checked.lift_after.clip(lower=0.5), mode="markers", marker=dict(color=JADE, size=8),
                               text=checked.name_a.str.title() + " + " + checked.name_b.str.title(), hoverinfo="text"))
    chart(fig.add_hline(y=1, line_dash="dot", line_color=SILVER).update_xaxes(type="log", dtick=1, title="Times more than chance, before").update_yaxes(type="log", dtick=1, title="After"), 360)
