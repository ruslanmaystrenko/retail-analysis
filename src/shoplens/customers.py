"""Describe each customer by three things, then sort them into named groups.

The three things, as of a chosen day:
* days_since: days since their last order
* orders: how many separate orders they have placed
* spend: how much they have spent in total
"""
import pandas as pd

GROUPS = ["Best customers", "Regulars", "New", "Occasional", "Going quiet", "Lost"]


def summarize(sales: pd.DataFrame, as_of=None) -> pd.DataFrame:
    """One row per customer, using only sales up to `as_of`."""
    as_of = pd.Timestamp(as_of) if as_of is not None else sales["when"].max()
    past = sales[sales["when"] <= as_of]
    table = past.groupby("customer").agg(last=("when", "max"), first=("when", "min"), orders=("order", "nunique"), spend=("revenue", "sum"))
    table["days_since"] = (as_of - table["last"]).dt.days
    return table


def group(customers: pd.DataFrame) -> pd.Series:
    """Give each customer a group name.

    Customers are scored from 1 to 5 on how recently they bought and on how
    often they have bought, each score being a fifth of all customers. The
    names follow from the two scores:

    * Best customers: bought recently and often
    * Regulars: bought fairly recently and fairly often
    * New: one order, placed recently
    * Going quiet: used to buy often, has not been back lately
    * Lost: few orders, long ago
    * Occasional: everyone else
    """
    recent = pd.qcut(-customers["days_since"].rank(method="first"), 5, labels=False) + 1    # 5 is the most recent fifth
    often = pd.qcut(customers["orders"].rank(method="first"), 5, labels=False) + 1          # 5 is the most frequent fifth
    name = pd.Series("Occasional", index=customers.index)
    name[(recent <= 2) & (often <= 2)] = "Lost"
    name[(recent <= 2) & (often >= 3)] = "Going quiet"
    name[(recent >= 4) & (customers["orders"] == 1)] = "New"
    name[(recent >= 3) & (often >= 3)] = "Regulars"
    name[(recent >= 4) & (often >= 4)] = "Best customers"
    return name.rename("group")


def by_group(customers: pd.DataFrame) -> pd.DataFrame:
    """Size and value of each group."""
    table = customers.groupby("group").agg(customers=("spend", "size"), spend=("spend", "sum"), typical_orders=("orders", "median"), typical_days_since=("days_since", "median"))
    table["share_of_customers"] = table["customers"] / table["customers"].sum()
    table["share_of_spend"] = table["spend"] / table["spend"].sum()
    return table.reindex([g for g in GROUPS if g in table.index])


def repeat_buying(sales: pd.DataFrame) -> pd.DataFrame:
    """Of the customers who first bought in each month, the share who ordered again in each later month.

    Rows are first months. Columns are months since then. Column 0 is always 1.
    """
    month = sales["when"].dt.to_period("M")
    first = month.groupby(sales["customer"]).transform("min")
    age = (month - first).apply(lambda gap: gap.n)
    active = sales.assign(first=first, age=age).groupby(["first", "age"])["customer"].nunique().unstack()
    return active.div(active[0], axis=0)
