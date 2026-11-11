"""Build the two extra demo shops in the standard column layout.

Only needed to rebuild the files in data/. Both sources are public domain (CC0).

    pip install pyreadr
    python scripts/get_data.py amazon-purchases.csv transactions.rds products.rda

Where the three files come from:
* amazon-purchases.csv: Open e-commerce 1.0, https://doi.org/10.7910/DVN/YGLYDY
* transactions.rds and products.rda: https://github.com/bradleyboehmke/completejourney (folder data/)
"""
import sys

import pandas as pd

COLUMNS = ["order", "customer", "product", "name", "quantity", "price", "when", "country"]


def amazon(path):
    """5,027 US shoppers who shared their Amazon order history. A product here is a product category."""
    table = pd.read_csv(path)
    table.columns = ["when", "price", "quantity", "country", "title", "code", "product", "customer"]
    table["when"] = pd.to_datetime(table["when"])
    # Shoppers exported their history between late 2022 and early 2023, so stop where everyone is still present.
    table = table[table["when"] <= "2022-10-31"].dropna(subset=["product"])
    table["customer"] = pd.factorize(table["customer"])[0] + 1
    table["order"] = pd.factorize(table["customer"].astype(str) + table["when"].astype(str))[0] + 1     # one order = one shopper on one day
    table["name"] = table["product"].str.replace("ABIS_", "").str.replace("_", " ").str.title()
    return table[COLUMNS]


def grocery(transactions, products):
    """2,469 households at a US grocery chain for one year. A product here is a product type, such as bananas."""
    import pyreadr
    lines = pyreadr.read_r(transactions)[None]
    kinds = list(pyreadr.read_r(products).values())[0]
    table = lines.merge(kinds[~kinds["department"].isin(["FUEL", "COUPON", "MISCELLANEOUS"])], on="product_id").dropna(subset=["product_type"])
    table = table[(table["quantity"] > 0) & (table["sales_value"] > 0)]
    return pd.DataFrame({
        "order": pd.factorize(table["basket_id"])[0] + 1, "customer": table["household_id"].astype(int),
        "product": table["product_type"], "name": table["product_type"].str.title(), "quantity": table["quantity"],
        "price": table["sales_value"] / table["quantity"], "when": table["transaction_timestamp"], "country": "US"})


if __name__ == "__main__":
    for name, table in [("amazon_shoppers", amazon(sys.argv[1])), ("grocery_chain", grocery(sys.argv[2], sys.argv[3]))]:
        for column in ("product", "name", "country"):
            table[column] = table[column].astype("category")
        table.sort_values("when").to_parquet(f"data/{name}.parquet", index=False)
        print(name, len(table), "rows")
