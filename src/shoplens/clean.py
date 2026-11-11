"""Load a file of sales and clean it.

The cleaned table has one row per product line on an order, with these columns:
order, customer, product, name, quantity, price, when, country, revenue.
"""
import pandas as pd

# The names used by the public Online Retail file. Pass your own mapping for other files.
ONLINE_RETAIL = {"InvoiceNo": "order", "CustomerID": "customer", "StockCode": "product", "Description": "name",
                 "Quantity": "quantity", "UnitPrice": "price", "InvoiceDate": "when", "Country": "country"}


# The demo shops that ship in data/. `money` is the currency sign and `not_products` matches codes to leave out.
SHOPS = {
    "UK gift retailer, 2010 to 2011": dict(file="data/online_retail.parquet", money="£", not_products=r"^\D",
        about="A UK online gift shop selling mostly to other businesses. Each product is a single item."),
    "Amazon shoppers, 2018 to 2022": dict(file="data/amazon_shoppers.parquet", money="$", not_products=None,
        about="5,013 US shoppers who shared their Amazon order history. A product here is a category, such as pet food."),
    "US grocery chain, one year": dict(file="data/grocery_chain.parquet", money="$", not_products=None,
        about="2,467 households at a US grocery chain. A product here is a type, such as bananas. The publisher shifted the dates to 2017."),
}


def load(path, columns=ONLINE_RETAIL) -> pd.DataFrame:
    """Read a parquet, csv or Excel file and rename its columns to the standard names."""
    path = str(path)
    reader = pd.read_parquet if path.endswith(".parquet") else pd.read_csv if path.endswith(".csv") else pd.read_excel
    table = reader(path).rename(columns=columns)
    table["when"] = pd.to_datetime(table["when"])
    for column in ("order", "product", "name"):
        table[column] = table[column].astype(str).where(table[column].notna())
    return table.assign(country=table.get("country", "Unknown"))


def clean(raw: pd.DataFrame, not_products: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Keep real product sales to known customers, with returns taken off the sales they undo.

    Returns the cleaned sales and a count of what was removed at each step.
    `not_products` is a pattern for codes that are fees or adjustments, not products.

    The returns step is the one that matters. Dropping return rows on their
    own leaves the original sale in place, so an order that was placed and
    cancelled minutes later would still count as revenue.
    """
    removed = {"rows at the start": len(raw)}
    table = raw.dropna(subset=["customer"])
    removed["no customer on the row"] = len(raw) - len(table)
    real = ~table["product"].str.contains(not_products) if not_products else pd.Series(True, index=table.index)
    removed["fees, postage and adjustments"] = int((~real).sum())
    table = table[real & (table["price"] > 0)].copy()
    if pd.api.types.is_float_dtype(table["customer"]):
        table["customer"] = table["customer"].astype(int)

    sales = table[table["quantity"] > 0].sort_values("when").copy()
    returns = table[table["quantity"] < 0]
    removed["return rows"] = len(returns)
    before = sales["quantity"].sum()
    # Take each return off that customer's most recent earlier purchases of the same product.
    returned = sales[sales["customer"].isin(returns["customer"]) & sales["product"].isin(returns["product"])]
    by_key = {key: list(rows) for key, rows in returned.groupby(["customer", "product"]).groups.items()}
    left = returned["quantity"].to_dict()
    times = returned["when"].to_dict()
    for row in returns.itertuples():
        owed = -row.quantity
        for index in reversed(by_key.get((row.customer, row.product), [])):
            if owed == 0:
                break
            if times[index] <= row.when and left[index] > 0:
                taken = min(left[index], owed)
                left[index] -= taken
                owed -= taken
    if left:
        sales.loc[list(left), "quantity"] = list(left.values())
    removed["units returned and taken off sales"] = int(before - sales["quantity"].sum())
    sales = sales[sales["quantity"] > 0]
    sales["revenue"] = sales["quantity"] * sales["price"]
    removed["rows at the end"] = len(sales)
    return sales.reset_index(drop=True), removed


def open_shop(name: str):
    """Load and clean one of the demo shops."""
    shop = SHOPS[name]
    return clean(load(shop["file"]), shop["not_products"])
