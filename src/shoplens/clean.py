"""Load a file of sales and clean it.

The cleaned table has one row per product line on an order, with these columns:
order, customer, product, name, quantity, price, when, country, revenue.
"""
import pandas as pd

# The names used by the public Online Retail file. Pass your own mapping for other files.
ONLINE_RETAIL = {"InvoiceNo": "order", "CustomerID": "customer", "StockCode": "product", "Description": "name",
                 "Quantity": "quantity", "UnitPrice": "price", "InvoiceDate": "when", "Country": "country"}


def load(path, columns=ONLINE_RETAIL) -> pd.DataFrame:
    """Read a parquet, csv or Excel file and rename its columns to the standard names."""
    path = str(path)
    reader = pd.read_parquet if path.endswith(".parquet") else pd.read_csv if path.endswith(".csv") else pd.read_excel
    table = reader(path).rename(columns=columns)
    table["when"] = pd.to_datetime(table["when"])
    for column in ("order", "product"):
        table[column] = table[column].astype(str)
    if "country" not in table:
        table["country"] = "Unknown"
    return table[list(dict.fromkeys(columns.values())) if set(columns.values()) <= set(table.columns) else table.columns]


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Keep real product sales to known customers, with returns taken off the sales they undo.

    Returns the cleaned sales and a count of what was removed at each step.

    The returns step is the one that matters. Dropping return rows on their
    own leaves the original sale in place, so an order that was placed and
    cancelled minutes later would still count as revenue.
    """
    removed = {"rows at the start": len(raw)}
    table = raw.dropna(subset=["customer"])
    removed["no customer on the row"] = len(raw) - len(table)
    real = table["product"].str.match(r"^\d")           # fees, postage and manual adjustments have codes that are words
    removed["fees, postage and adjustments"] = int((~real).sum())
    table = table[real & (table["price"] > 0)].copy()
    table["customer"] = table["customer"].astype(int)

    sales = table[table["quantity"] > 0].sort_values("when").copy()
    returns = table[table["quantity"] < 0]
    removed["return rows"] = len(returns)
    before = sales["quantity"].sum()
    # Take each return off that customer's most recent earlier purchases of the same product.
    by_key = {key: list(rows) for key, rows in sales.groupby(["customer", "product"]).groups.items()}
    left = sales["quantity"].to_dict()
    times = sales["when"].to_dict()
    for row in returns.itertuples():
        owed = -row.quantity
        for index in reversed(by_key.get((row.customer, row.product), [])):
            if owed == 0:
                break
            if times[index] <= row.when and left[index] > 0:
                taken = min(left[index], owed)
                left[index] -= taken
                owed -= taken
    sales["quantity"] = pd.Series(left)
    removed["units returned and taken off sales"] = int(before - sales["quantity"].sum())
    sales = sales[sales["quantity"] > 0]
    sales["revenue"] = sales["quantity"] * sales["price"]
    removed["rows at the end"] = len(sales)
    return sales.reset_index(drop=True), removed
