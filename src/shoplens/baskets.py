"""Find products that are bought together more often than chance would explain."""
import numpy as np
import pandas as pd
from scipy import sparse


def pairs(sales: pd.DataFrame, top_products: int = 500, min_orders_together: int = 30) -> pd.DataFrame:
    """Every pair of products that shares at least `min_orders_together` orders.

    For each pair:
    * together: orders containing both
    * chance_a_then_b: of orders with A, the share that also have B
    * lift: how many times more often they appear together than they would if
      buying one told you nothing about the other. 1 means no connection.

    Only the `top_products` most ordered products are considered, to keep it fast.
    """
    lines = sales.drop_duplicates(["order", "product"])
    popular = lines["product"].value_counts().head(top_products).index
    lines = lines[lines["product"].isin(popular)]
    orders, products = pd.factorize(lines["order"])[0], pd.Categorical(lines["product"], categories=popular)
    grid = sparse.csr_matrix((np.ones(len(lines)), (orders, products.codes)), shape=(orders.max() + 1, len(popular)))
    both = (grid.T @ grid).toarray()
    count, total = both.diagonal(), grid.shape[0]
    a, b = np.where(np.triu(both, 1) >= min_orders_together)
    names = lines.drop_duplicates("product").set_index("product")["name"]
    table = pd.DataFrame({
        "product_a": popular[a], "product_b": popular[b],
        "name_a": names.reindex(popular[a]).to_numpy(), "name_b": names.reindex(popular[b]).to_numpy(),
        "together": both[a, b].astype(int),
        "chance_a_then_b": both[a, b] / count[a], "chance_b_then_a": both[a, b] / count[b],
        "lift": both[a, b] * total / (count[a] * count[b]),
    })
    return table.sort_values("lift", ascending=False).reset_index(drop=True)
