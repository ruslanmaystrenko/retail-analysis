"""Draw the charts used in REPORT.md.  Run from the repo root:  python scripts/report_charts.py"""
import sys
sys.path.insert(0, "src")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from shoplens.clean import SHOPS, load, open_shop
from shoplens.forward import groups_next, split
from shoplens.market_basket import families, pairs
from shoplens.segmentation import GROUPS, by_group, group, summarize

plt.style.use("dark_background")
plt.rcParams.update({"figure.facecolor": "black", "axes.facecolor": "black", "axes.edgecolor": "#3a3b3e", "axes.grid": True, "grid.color": "#1c1c1e",
                     "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 140, "savefig.bbox": "tight"})
WHITE, SILVER, GREY, JADE, RED = "#f2f2f0", "#d4d6da", "#8d8d90", "#5fd0a0", "#e0787a"
COLORS = dict(zip(GROUPS, [JADE, "#9fd9bd", WHITE, SILVER, "#c9a25a", GREY]))
PALETTE = [JADE, WHITE, "#c9a25a", "#9fd9bd", SILVER, RED, "#7fb4d8", GREY]
SHORT = dict(zip(SHOPS, ["UK gift retailer", "Amazon shoppers", "US grocery chain"]))
UK = list(SHOPS)[0]
shops = {name: open_shop(name)[0] for name in SHOPS}

# 1. What the cancelled orders did
raw = load(SHOPS[UK]["file"]).dropna(subset=["customer"])
naive = raw[(raw.quantity > 0) & (raw.price > 0)].assign(revenue=lambda t: t.quantity * t.price)
fig, axes = plt.subplots(1, 2, figsize=(13, 3.8))
for ax, table, title, color in [(axes[0], naive, "First version: cancelled orders counted", GREY), (axes[1], shops[UK], "This version: returns taken off their sales", JADE)]:
    top = table.groupby("name")["revenue"].sum().nlargest(6)[::-1]
    ax.barh([n.title()[:30] for n in top.index], top.values, color=[RED if "BIRDIE" in n or "STORAGE JAR" in n else color for n in top.index])
    ax.set_title(title, loc="left", fontsize=11); ax.xaxis.set_major_formatter(lambda v, _: f"£{v / 1000:,.0f}k"); ax.locator_params(axis="x", nbins=5); ax.grid(axis="y", visible=False)
plt.tight_layout(); fig.savefig("report/1_cancelled_orders.png"); plt.close()

# 2. Segment shares at the three shops
fig, axes = plt.subplots(3, 1, figsize=(11, 6))
for ax, (name, sales) in zip(axes, shops.items()):
    customers = summarize(sales); customers["group"] = group(customers); table = by_group(customers)
    for row, column in enumerate(["share_of_customers", "share_of_spend"]):
        left = 0
        for g in table.index:
            v = table.loc[g, column]
            ax.barh(row, v, left=left, color=COLORS[g], edgecolor="black")
            if v > 0.05:
                ax.text(left + v / 2, row, f"{v:.0%}", ha="center", va="center", color="black", fontsize=9)
            left += v
    ax.set_yticks([0, 1], ["Customers", "Spend"]); ax.set_xlim(0, 1); ax.xaxis.set_visible(False); ax.grid(False); ax.set_title(SHORT[name], loc="left", fontsize=11)
fig.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=COLORS[g]) for g in GROUPS], labels=GROUPS, frameon=False, ncol=6, loc="upper center", bbox_to_anchor=(0.5, 1.05))
plt.tight_layout(); fig.savefig("report/2_segments.png"); plt.close()

# 3. The forward check
fig, axes = plt.subplots(2, 3, figsize=(14, 6.6))
for column, (name, sales) in enumerate(shops.items()):
    table = groups_next(sales); each = table.drop("Everyone"); sign = SHOPS[name]["money"]
    axes[0, column].bar(each.index, each.came_back, color=[COLORS[g] for g in each.index]); axes[0, column].set_ylim(0, 1.05)
    axes[0, column].axhline(table.loc["Everyone", "came_back"], color=SILVER, lw=1, ls=":")
    axes[0, column].yaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); axes[0, column].set_title(f"{SHORT[name]}: ordered again", loc="left", fontsize=11)
    axes[1, column].bar(each.index, each.average_spend_after, color=[COLORS[g] for g in each.index])
    axes[1, column].yaxis.set_major_formatter(lambda v, _, sign=sign: f"{sign}{v:,.0f}"); axes[1, column].set_title("Average spend in the next 90 days", loc="left", fontsize=11)
for ax in axes.ravel():
    ax.tick_params(axis="x", rotation=30, labelsize=8); ax.grid(axis="x", visible=False)
plt.tight_layout(); fig.savefig("report/3_forward_check.png"); plt.close()

# 4. Named segments against clustering
before, after, cutoff = split(shops[UK])
then = summarize(before, cutoff); then["Named segments"] = group(then)
then["Clustering"] = KMeans(6, n_init=10, random_state=0).fit_predict(StandardScaler().fit_transform(np.log1p(then[["days_since", "orders", "spend"]])))
then["spend_after"] = after.groupby("customer")["revenue"].sum().reindex(then.index).fillna(0)
fig, axes = plt.subplots(1, 2, figsize=(13, 3.8), sharey=True)
for ax, method in zip(axes, ["Named segments", "Clustering"]):
    table = then.groupby(method).agg(spend=("spend_after", "mean"), customers=("spend_after", "size")).sort_values("spend", ascending=False)
    labels = table.index if method == "Named segments" else [f"Cluster {i + 1}" for i in range(len(table))]
    bars = ax.bar(labels, table.spend, color=[COLORS.get(i, SILVER) for i in table.index])
    ax.bar_label(bars, [f"{n:,} customers" for n in table.customers], color=GREY, fontsize=8)
    ax.set_title(f"{method}: average spend in the next 90 days", loc="left", fontsize=11); ax.tick_params(axis="x", rotation=25, labelsize=9); ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(lambda v, _: f"£{v:,.0f}")
plt.tight_layout(); fig.savefig("report/4_clustering.png"); plt.close()

# 5. Product families at the grocery chain and the gift shop
fig, axes = plt.subplots(2, 1, figsize=(13, 9))
for ax, name in zip(axes, [list(SHOPS)[2], UK]):
    found = pairs(shops[name]); spots = families(found, 100, 8).set_index("name")
    for a, b in zip(found.head(100).name_a, found.head(100).name_b):
        if a in spots.index:
            ax.plot(*zip(spots.loc[a, ["x", "y"]], spots.loc[b, ["x", "y"]]), color="#55575c", lw=1, zorder=1)
    ax.scatter(spots.x, spots.y, s=50 + 30 * spots.links, color=[PALETTE[(f - 1) % 8] for f in spots.family], zorder=2, linewidths=0)
    for number, members in spots.groupby("family"):
        ax.text((number - 1) % 4, -((number - 1) // 4) - 0.47, f"{members.index[0].title().strip()[:30]}  ({len(members)})", ha="center", fontsize=9, color=SILVER)
    ax.set_xlim(-0.5, 3.5); ax.axis("off"); ax.set_title(SHORT[name], loc="left", fontsize=12)
plt.tight_layout(); fig.savefig("report/5_families.png"); plt.close()
print("done")
