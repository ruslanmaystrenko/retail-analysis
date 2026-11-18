"""Turn the numbers into plain findings and next steps.

Every sentence is built from the shop's own figures, so the same code writes
a summary for any sales file. Figures are wrapped in ** ** for the app to color.
"""
import pandas as pd


def best_month(sales: pd.DataFrame) -> tuple[pd.Timestamp, float]:
    """The highest revenue month, and how many times the typical month it was. Part months at either end are left out."""
    monthly = sales.set_index("when")["revenue"].resample("MS").sum()
    if sales["when"].min().day > 3:
        monthly = monthly.iloc[1:]
    if sales["when"].max().day < 26:
        monthly = monthly.iloc[:-1]
    return monthly.idxmax(), monthly.max() / monthly.median()


def summarize_shop(sales, customers, groups, found, check, pairs_kept, sign="$") -> dict:
    """Two lists of sentences: what was found, and what to do about it.

    `groups` is the table from by_group, `found` the pairs, `check` the table
    from groups_next and `pairs_kept` the share of strong pairs still linked afterward.
    """
    money = lambda v: f"{sign}{v:,.0f}"
    share = lambda g, column: groups[column].get(g, 0)
    count = lambda g: int(groups["customers"].get(g, 0))
    top = ["Big spenders", "Best customers"]
    revenue = sales["revenue"].sum()
    products = sales.groupby("name")["revenue"].sum().sort_values(ascending=False)
    month, peak = best_month(sales)
    once = (customers["orders"] == 1).mean()
    quiet_spend = customers.loc[customers["group"] == "Going quiet", "spend"].sum()
    after = lambda g, column: check[column].get(g, float("nan"))

    learned = [
        f"**{sum(share(g, 'share_of_customers') for g in top):.0%}** of customers bring in **{sum(share(g, 'share_of_spend') for g in top):.0%}** of revenue. "
        f"The **{count('Big spenders'):,}** Big spenders alone bring in **{share('Big spenders', 'share_of_spend'):.0%}**.",
        f"**{count('Going quiet'):,}** customers who used to buy often have gone quiet. Between them they have spent **{money(quiet_spend)}**.",
        f"The best month was **{month:%B %Y}**, at **{peak:.1f} times** a typical month.",
        f"The top ten products make up **{products.head(10).sum() / revenue:.0%}** of revenue. The largest is **{products.index[0].title().strip()}** at **{products.iloc[0] / revenue:.1%}**.",
    ]
    if once >= 0.1:
        learned.insert(2, f"**{once:.0%}** of customers have ordered only once.")
    if len(found):
        first = found.iloc[0]
        learned.append(f"**{len(found):,}** pairs of products sell together more than chance. The strongest is **{first.name_a.title().strip()}** with **{first.name_b.title().strip()}**, "
                       f"bought together **{first.lift:.0f} times** more often than chance.")
    known = lambda g, column: pd.notna(after(g, column))            # a segment with too few customers has no result
    if known("Big spenders", "came_back") and known("Lost", "came_back"):
        learned.append(f"These findings held up on later sales. In the following 90 days **{after('Big spenders', 'came_back'):.0%}** of Big spenders ordered again against "
                       f"**{after('Lost', 'came_back'):.0%}** of Lost customers, and **{pairs_kept:.0%}** of the strongest product pairs kept selling together.")

    actions = []
    if known("Big spenders", "average_spend_after"):
        actions.append(f"**Look after the {count('Big spenders'):,} Big spenders personally.** Each one spends about **{money(after('Big spenders', 'average_spend_after'))}** every 90 days, "
                       f"against **{money(after('Everyone', 'average_spend_after'))}** for a typical customer.")
    if known("Going quiet", "average_spend_after"):
        actions.append(f"**Contact the {count('Going quiet'):,} Going quiet customers now, biggest spenders first.** Customers like them went on to spend about "
                       f"**{money(after('Going quiet', 'average_spend_after') * count('Going quiet'))}** in total over the next 90 days, so that is what is at stake.")
    if once >= 0.1:
        actions.append(f"**Win the second order.** Follow up with the **{int((customers['orders'] == 1).sum()):,}** customers who have bought once, within a few weeks of that first order.")
    if len(found):
        bundles = "; ".join(f"{p.name_a.title().strip()} with {p.name_b.title().strip()}" for p in found.head(3).itertuples())
        actions.append(f"**Sell what goes together as a bundle, and suggest the missing piece at checkout.** Start with: {bundles}.")
    if peak >= 1.2:
        actions.append(f"**Plan stock and staff for {month:%B}.** It ran **{peak - 1:.0%}** above a typical month.")
    actions.append(f"**Spend little on the {count('Lost'):,} Lost customers.** They are **{share('Lost', 'share_of_customers'):.0%}** of the list and **{share('Lost', 'share_of_spend'):.0%}** of revenue.")
    return {"learned": learned, "actions": actions}
