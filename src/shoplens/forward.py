"""Check the findings against what happened next.

Everything is worked out from sales before a cutoff day. Then the sales after
that day show whether the groups and the product pairs meant anything.
"""
import pandas as pd

from .market_basket import pairs
from .segmentation import GROUPS, group, summarize


def split(sales: pd.DataFrame, days_held_back: int = 90):
    cutoff = sales["when"].max().normalize() - pd.Timedelta(days=days_held_back)
    return sales[sales["when"] <= cutoff], sales[sales["when"] > cutoff], cutoff


def groups_next(sales: pd.DataFrame, days_held_back: int = 90) -> pd.DataFrame:
    """For each group formed at the cutoff: how many came back afterward, and what they spent."""
    before, after, cutoff = split(sales, days_held_back)
    customers = summarize(before, cutoff)
    customers["group"] = group(customers)
    later = after.groupby("customer")["revenue"].sum()
    customers["came_back"] = customers.index.isin(later.index)
    customers["spend_after"] = later.reindex(customers.index).fillna(0)
    table = customers.groupby("group").agg(customers=("came_back", "size"), came_back=("came_back", "mean"), average_spend_after=("spend_after", "mean"))
    table.loc["Everyone"] = [len(customers), customers["came_back"].mean(), customers["spend_after"].mean()]
    table = table[table["customers"] >= 10]            # a group of a handful of customers says nothing
    return table.reindex([g for g in GROUPS + ["Everyone"] if g in table.index]).astype({"customers": int, "came_back": float, "average_spend_after": float})


def pairs_next(sales: pd.DataFrame, days_held_back: int = 90, top: int = 50) -> pd.DataFrame:
    """Take the strongest pairs found before the cutoff and measure them again afterward."""
    before, after, _ = split(sales, days_held_back)
    found = pairs(before).head(top)
    again = pairs(after, min_orders_together=1, only=pd.unique(found[["product_a", "product_b"]].to_numpy().ravel()))
    lift_after = {frozenset(pair): lift for pair, lift in zip(zip(again["product_a"], again["product_b"]), again["lift"])}
    found["lift_after"] = [lift_after.get(frozenset(pair), 0.0) for pair in zip(found["product_a"], found["product_b"])]   # 0 means never bought together afterward
    return found
