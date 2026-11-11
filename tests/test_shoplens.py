import pandas as pd
import pytest

from shoplens.market_basket import pairs
from shoplens.clean import clean
from shoplens.segmentation import group, repeat_buying, summarize
from shoplens.forward import groups_next


def rows(*lines):
    table = pd.DataFrame(lines, columns=["order", "customer", "product", "name", "quantity", "price", "when"])
    table["when"] = pd.to_datetime(table["when"], format="mixed")
    table["country"] = "UK"
    return table


def test_a_cancelled_order_leaves_no_revenue():
    raw = rows(("1", 7, "100", "Jar", 1000, 2.0, "2011-01-01 10:00"), ("C2", 7, "100", "Jar", -1000, 2.0, "2011-01-01 10:15"),
               ("3", 7, "200", "Mug", 3, 5.0, "2011-01-02"))
    sales, removed = clean(raw, r"^\D")
    assert list(sales["product"]) == ["200"] and sales["revenue"].sum() == 15
    assert removed["units returned and taken off sales"] == 1000


def test_a_part_return_comes_off_the_latest_earlier_purchase():
    raw = rows(("1", 7, "100", "Jar", 5, 2.0, "2011-01-01"), ("2", 7, "100", "Jar", 4, 2.0, "2011-02-01"),
               ("C3", 7, "100", "Jar", -6, 2.0, "2011-03-01"), ("4", 7, "100", "Jar", 2, 2.0, "2011-04-01"))
    sales, _ = clean(raw, r"^\D")
    assert dict(zip(sales["order"], sales["quantity"])) == {"1": 3, "4": 2}   # order 2 fully returned, order 1 partly, order 4 untouched


def test_fees_unknown_customers_and_free_items_are_dropped():
    raw = rows(("1", 7, "POST", "Postage", 1, 18.0, "2011-01-01"), ("1", None, "100", "Jar", 2, 2.0, "2011-01-01"),
               ("1", 7, "100", "Jar", 2, 0.0, "2011-01-01"), ("1", 7, "200", "Mug", 1, 5.0, "2011-01-01"))
    sales, _ = clean(raw, r"^\D")
    assert list(sales["product"]) == ["200"]


def test_customer_summary_only_uses_the_past():
    raw = rows(("1", 7, "100", "Jar", 1, 10.0, "2011-01-01"), ("2", 7, "100", "Jar", 1, 10.0, "2011-06-01"))
    sales, _ = clean(raw, r"^\D")
    early = summarize(sales, "2011-03-01").loc[7]
    assert early["orders"] == 1 and early["spend"] == 10 and early["days_since"] == 59


def make_shop():
    lines = []
    for c in range(200):
        orders = 1 + c % 10                                   # customers 0 to 199 place between 1 and 10 orders
        for k in range(orders):
            day = pd.Timestamp("2011-01-01") + pd.Timedelta(days=(c * 7 + k * 31) % 330)
            lines.append((f"{c}-{k}", c, "100" if k % 2 else "200", "Jar", 1, 10.0, day))
            if k % 2:
                lines.append((f"{c}-{k}", c, "300", "Lid", 1, 3.0, day))   # lids are only ever bought with jars
    return clean(rows(*lines), r"^\D")[0]


def test_groups_cover_everyone_and_best_customers_buy_most_often():
    customers = summarize(make_shop())
    customers["group"] = group(customers)
    assert customers["group"].notna().all()
    medians = customers.groupby("group")["orders"].median()
    assert medians["Best customers"] > medians["Lost"]


def test_pairs_find_products_that_go_together():
    found = pairs(make_shop(), min_orders_together=5)
    top = found.iloc[0]
    assert {top["product_a"], top["product_b"]} == {"100", "300"}
    assert top["lift"] > 1 and top["chance_b_then_a"] == pytest.approx(1.0) or top["chance_a_then_b"] == pytest.approx(1.0)


def test_repeat_buying_starts_at_everyone():
    table = repeat_buying(make_shop())
    assert (table[0] == 1).all() and (table.drop(columns=0).max().max() <= 1)


def test_forward_check_separates_what_was_known_from_what_came_next():
    table = groups_next(make_shop(), days_held_back=60)
    assert table.loc["Everyone", "customers"] >= table.drop("Everyone")["customers"].sum()      # tiny groups are left out
    assert 0 <= table["came_back"].min() and table["came_back"].max() <= 1


def test_pairs_are_measured_again_on_later_sales():
    from shoplens.forward import pairs_next
    checked = pairs_next(make_shop(), days_held_back=120, top=1)
    assert checked["lift_after"].iloc[0] > 1      # jars and lids keep selling together


def test_rules_read_both_ways_and_families_group_linked_products():
    from shoplens.market_basket import families, pairs, rules
    found = pairs(make_shop(), min_orders_together=5)
    both_ways = rules(found)
    assert len(both_ways) == 2 * len(found)
    assert both_ways["confidence"].between(0, 1).all()
    assert families(found)["family"].min() == 1


def test_profile_has_a_row_and_an_action_for_every_group():
    from shoplens.segmentation import group, profile, summarize
    sales = make_shop()
    customers = summarize(sales)
    customers["group"] = group(customers)
    table = profile(sales, customers)
    assert set(table.index) == set(customers["group"]) and table["what_to_do"].notna().all()


def test_big_spenders_are_best_customers_with_top_spend():
    from shoplens.segmentation import group, summarize
    customers = summarize(make_shop())
    names = group(customers)
    big = customers[names == "Big spenders"]
    assert len(big) > 0 and big["spend"].min() >= customers["spend"].quantile(0.95)


def test_check_repeats_at_earlier_cutoffs_only_with_enough_history():
    from shoplens.forward import over_time
    sales = make_shop()
    checks = over_time(sales, days_held_back=60)
    cutoffs = checks["cutoff"].unique()
    assert len(cutoffs) >= 2 and (pd.Series(cutoffs) - sales["when"].min()).dt.days.min() >= 60
