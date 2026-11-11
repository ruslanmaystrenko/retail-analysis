# ShopLens

Open a file of sales and get three answers: who the customers are, who is drifting away, and what sells together. Then check those answers against what happened next.

This is a rebuild of an earlier project of mine. The first version is kept in `original/`, and [REWORK.md](REWORK.md) explains what was wrong with it and what changed.

## What it found

The demo data is a year of orders from a UK online gift retailer: 4,324 customers, 18,268 orders, £8.3 million in revenue.

* **A quarter of the customers bring in two thirds of the money.** Best customers are 26 percent of the list and 68 percent of the spend.
* **654 customers are going quiet.** They ordered several times, spent £733,000 between them, and have not been back in months.
* **The strongest product pairs are sets sold as separate items.** Tea plates in three colors, herb markers, matching decorations. Someone who buys one is 40 to 60 times more likely than chance to buy the other.
* **Two cancelled orders had been bending the results.** An 80,995 unit order was placed and cancelled twelve minutes later. Counting the sale and ignoring the cancellation made it the top product in the first version.

## Did it hold up

Describing the past is easy. So the last 90 days were hidden, everything was rebuilt from the earlier sales, and the hidden days were used as the test.

| Group at the cutoff | Ordered again in the next 90 days |
| --- | --- |
| Best customers | 84% |
| Regulars | 64% |
| Going quiet | 51% |
| New | 45% |
| Occasional | 45% |
| Lost | 34% |
| Everyone | 57% |

The groups ranked customers correctly. All 50 of the strongest product pairs kept selling together.

One caution: the 90 days held back are the busiest of this shop's year, so the rates would be lower in a quiet season.

## The app

```
pip install -e .
python -m streamlit run app.py
```

On Windows, double click `ShopLens.bat`.

It opens on the demo shop. Upload your own csv or Excel file in the sidebar, match seven columns, and every tab rebuilds for your data.

* **Overview**: revenue by month, top products, what cleaning removed
* **Customers**: the six groups, every customer on one chart, repeat buying by first month
* **Going quiet**: the customers worth contacting, sorted by spend
* **Bought together**: pick a product and see what sells with it
* **Did it hold up**: the forward check, with a choice of how many days to hold back

## How it is laid out

| Path | What it holds |
| --- | --- |
| `src/shoplens/clean.py` | Loads a file and nets returns against the sales they undo |
| `src/shoplens/customers.py` | Customer groups and repeat buying |
| `src/shoplens/baskets.py` | Products bought together |
| `src/shoplens/forward.py` | The check against later sales |
| `notebooks/` | The analysis, step by step, with charts |
| `app.py` | The app |
| `tests/` | Nine tests on a small made up shop |
| `original/` | The first version, untouched |

## Data

[Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail) from the UCI Machine Learning Repository, by Daqing Chen. Licensed CC BY 4.0.
