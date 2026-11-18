"""Market basket analysis: which products are bought together more often than chance would explain."""
import numpy as np
import pandas as pd
from scipy import sparse


def pairs(sales: pd.DataFrame, top_products: int = 500, min_orders_together: int | None = None, only=None) -> pd.DataFrame:
    """Every pair of products that shares enough orders.

    For each pair:
    * together: orders containing both
    * support: the share of all orders containing both
    * chance_a_then_b: of orders with A, the share that also have B (also called confidence)
    * lift: how many times more often they appear together than they would if
      buying one told you nothing about the other. 1 means no connection.

    Only the `top_products` most ordered products are considered, or the ones listed in `only`.
    Pairs need at least `min_orders_together` shared orders: by default 30, or one order in a thousand if that is more.
    """
    lines = sales.drop_duplicates(["order", "product"])
    total = lines["order"].nunique()
    if min_orders_together is None:
        min_orders_together = max(30, total // 1000)
    popular = pd.Index(only) if only is not None else lines["product"].value_counts().head(top_products).index
    lines = lines[lines["product"].isin(popular)]
    orders, products = pd.factorize(lines["order"])[0], pd.Categorical(lines["product"], categories=popular)
    grid = sparse.csr_matrix((np.ones(len(lines)), (orders, products.codes)), shape=(orders.max() + 1, len(popular)))
    both = (grid.T @ grid).toarray()
    count = both.diagonal()
    a, b = np.where(np.triu(both, 1) >= min_orders_together)
    names = lines.drop_duplicates("product").set_index("product")["name"]
    table = pd.DataFrame({
        "product_a": popular[a], "product_b": popular[b],
        "name_a": names.reindex(popular[a]).to_numpy(), "name_b": names.reindex(popular[b]).to_numpy(),
        "together": both[a, b].astype(int), "support": both[a, b] / total,
        "chance_a_then_b": both[a, b] / count[a], "chance_b_then_a": both[a, b] / count[b],
        "lift": both[a, b] * total / (count[a] * count[b]),
    })
    return table.sort_values("lift", ascending=False).reset_index(drop=True)


def baseline_lift(sales: pd.DataFrame) -> float:
    """The lift two unrelated products would show in this shop, purely because some orders are much bigger than others.

    A large order holds many products, so any two of them land together more
    often than the simple "chance" in the lift formula allows for. This works
    out the lift you would see if the same products were dealt at random into
    orders of the same sizes. A pair is only interesting well above this.
    """
    sizes = sales.drop_duplicates(["order", "product"]).groupby("order").size()
    return float(len(sizes) * (sizes * (sizes - 1)).sum() / sizes.sum() ** 2)


def rules(found: pd.DataFrame) -> pd.DataFrame:
    """Turn pairs into rules that read "customers who buy this also buy that".

    Each pair gives two rules, one in each direction. Confidence is the share
    of orders with the first product that also have the second.
    """
    forward = found.rename(columns={"name_a": "buys", "name_b": "also_buys", "chance_a_then_b": "confidence"})
    backward = found.rename(columns={"name_b": "buys", "name_a": "also_buys", "chance_b_then_a": "confidence"})
    columns = ["buys", "also_buys", "together", "support", "confidence", "lift"]
    return pd.concat([forward[columns], backward[columns]]).sort_values(["confidence", "lift"], ascending=False).reset_index(drop=True)


def families(found: pd.DataFrame, strongest: int = 150, biggest: int = 12, across: int = 4) -> pd.DataFrame:
    """Group products into families that sell together, and place them for a network chart.

    Products are joined by their `strongest` pairs. Products joined to each
    other, directly or through others, form one family. Returns one row per
    product in the `biggest` families, with its family number and an x, y
    position. Each family is laid out on its own and the families sit in a grid.
    """
    import networkx as nx
    links = found.head(strongest)
    web = nx.Graph()
    web.add_weighted_edges_from(zip(links["name_a"], links["name_b"], np.log1p(links["lift"])))
    rows = []
    for number, members in enumerate(sorted(nx.connected_components(web), key=len, reverse=True)[:biggest]):
        part = web.subgraph(members)
        place = nx.spring_layout(part, seed=7, scale=0.36, center=(number % across, -(number // across)), k=1.5 / np.sqrt(len(part)))
        rows += [dict(name=name, family=number + 1, links=part.degree(name), x=place[name][0], y=place[name][1]) for name in part]
    return pd.DataFrame(rows).sort_values(["family", "links"], ascending=[True, False]).reset_index(drop=True)
