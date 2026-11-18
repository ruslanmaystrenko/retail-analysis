"""Check the findings against what happened next.

Everything is worked out from sales before a cutoff day. Then the sales after
that day show whether the groups and the product pairs meant anything.
"""
import pandas as pd

from .market_basket import baseline_lift, pairs
from .segmentation import GROUPS, group, summarize


def split(sales: pd.DataFrame, days_held_back: int = 90, end=None):
    """Cut the sales in two: everything up to a cutoff day, and the `days_held_back` days after it, ending at `end`."""
    end = pd.Timestamp(end) if end is not None else sales["when"].max().normalize() + pd.Timedelta(days=1)
    cutoff = end - pd.Timedelta(days=days_held_back)
    return sales[sales["when"] <= cutoff], sales[(sales["when"] > cutoff) & (sales["when"] <= end)], cutoff


def groups_next(sales: pd.DataFrame, days_held_back: int = 90, end=None) -> pd.DataFrame:
    """For each group formed at the cutoff: how many came back afterward, and what they spent."""
    before, after, cutoff = split(sales, days_held_back, end)
    customers = summarize(before, cutoff)
    customers["group"] = group(customers)
    later = after.groupby("customer")["revenue"].sum()
    customers["came_back"] = customers.index.isin(later.index)
    customers["spend_after"] = later.reindex(customers.index).fillna(0)
    table = customers.groupby("group").agg(customers=("came_back", "size"), came_back=("came_back", "mean"), average_spend_after=("spend_after", "mean"))
    table.loc["Everyone"] = [len(customers), customers["came_back"].mean(), customers["spend_after"].mean()]
    table = table[table["customers"] >= 10]            # a group of a handful of customers says nothing
    return table.reindex([g for g in GROUPS + ["Everyone"] if g in table.index]).astype({"customers": int, "came_back": float, "average_spend_after": float})


def pairs_next(sales: pd.DataFrame, days_held_back: int = 90, top: int = 50, end=None) -> pd.DataFrame:
    """Take the strongest pairs found before the cutoff and measure them again afterward."""
    before, after, _ = split(sales, days_held_back, end)
    found = pairs(before).head(top)
    again = pairs(after, min_orders_together=1, only=pd.unique(found[["product_a", "product_b"]].to_numpy().ravel()))
    lift_after = {frozenset(pair): lift for pair, lift in zip(zip(again["product_a"], again["product_b"]), again["lift"])}
    found["lift_after"] = [lift_after.get(frozenset(pair), 0.0) for pair in zip(found["product_a"], found["product_b"])]   # 0 means never bought together afterward
    found["baseline_after"] = baseline_lift(after)
    return found


def still_linked(checked: pd.DataFrame) -> pd.Series:
    """True for a pair that afterward sold together at least twice as often as random baskets of the same sizes would."""
    return checked["lift_after"] > 2 * checked["baseline_after"]


def over_time(sales: pd.DataFrame, days_held_back: int = 90, windows: int = 8) -> pd.DataFrame:
    """Repeat the check at several cutoff days, stepping back `days_held_back` days each time.

    One row per cutoff and group, plus a "Pairs" row holding the share of the
    50 strongest pairs that stayed linked. A cutoff is used only if at least
    `days_held_back` days of sales come before it.
    """
    last, first, tables = sales["when"].max().normalize() + pd.Timedelta(days=1), sales["when"].min(), []
    for step in range(windows):
        end = last - pd.Timedelta(days=step * days_held_back)
        cutoff = end - pd.Timedelta(days=days_held_back)
        if (cutoff - first).days < days_held_back:
            break
        table = groups_next(sales, days_held_back, end)
        table.loc["Pairs", "came_back"] = still_linked(pairs_next(sales, days_held_back, end=end)).mean()
        tables.append(table.assign(cutoff=cutoff).rename_axis("group").reset_index())
    return pd.concat(tables).sort_values("cutoff").reset_index(drop=True)


def verdicts(check: pd.DataFrame, pairs_checked: pd.DataFrame, repeated: pd.DataFrame, sign: str = "$") -> list[dict]:
    """Four pass or fail tests on whether the segments and product pairs can be trusted.

    `check` comes from groups_next, `pairs_checked` from pairs_next and `repeated` from over_time.
    Each test has a rule written in plain words, so a reader can see what passing means.
    """
    present = [g for g in GROUPS if g in check.index]
    top, bottom, everyone = present[0], present[-1], check.loc["Everyone"]
    back, spend = check["came_back"], check["average_spend_after"]
    kept, random = still_linked(pairs_checked).mean(), pairs_checked["baseline_after"].iloc[0]
    by_cutoff = repeated[repeated["group"] != "Pairs"].pivot(index="cutoff", columns="group", values="average_spend_after")
    held = int((by_cutoff[top] > by_cutoff[bottom]).sum()) if {top, bottom} <= set(by_cutoff) else 0
    return [
        dict(test="Segments predict who comes back", rule=f"{top} must return more than the average customer, and {bottom} customers less.",
             passed=bool(back[top] >= everyone["came_back"] > back[bottom]),
             result=f"{back[top]:.0%} of {top} ordered again, against {everyone['came_back']:.0%} of all customers and {back[bottom]:.0%} of {bottom}."),
        dict(test="Segments predict who spends", rule=f"{top} must go on to spend more than the average customer, and {bottom} customers less.",
             passed=bool(spend[top] > everyone["average_spend_after"] > spend[bottom]),
             result=f"{top} spent {sign}{spend[top]:,.0f} each, against {sign}{everyone['average_spend_after']:,.0f} for all customers and {sign}{spend[bottom]:,.0f} for {bottom}."),
        dict(test="Product pairs keep selling together", rule="At least 8 in 10 of the strongest pairs must still sell together at least twice as often as random baskets would.",
             passed=bool(kept >= 0.8), result=f"{kept:.0%} of the {len(pairs_checked)} strongest pairs were still linked. Random baskets in this shop give a lift of about {random:.1f}."),
        dict(test="The result repeats at other dates", rule=f"{top} must outspend {bottom} customers at every earlier cutoff day, not only the latest.",
             passed=bool(len(by_cutoff) and held == len(by_cutoff)), result=f"It held at {held} of {len(by_cutoff)} cutoff days."),
    ]
