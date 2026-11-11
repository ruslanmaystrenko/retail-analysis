# ShopLens

**Customer segmentation** and **market basket analysis** for any file of sales, with a check on whether the results hold up on later sales.

It answers three questions. Who are the customers and which ones matter? Who is drifting away? What sells together?

This is a rebuild of an earlier project of mine. The first version is kept in `original/`, and [REWORK.md](REWORK.md) explains what was wrong with it and what changed. The findings are written up in [REPORT.md](REPORT.md).

## Three shops, one method

The same code runs on three very different sets of sales.

| Shop | Period | Customers | Orders | A product is |
| --- | --- | --- | --- | --- |
| UK gift retailer | 2010 to 2011 | 4,324 | 18,268 | A single item |
| Amazon shoppers | 2018 to 2022 | 5,013 | 749,808 | A category, such as pet food |
| US grocery chain | One year | 2,467 | 140,925 | A type, such as bananas |

## Customer segmentation

Every customer is scored on how recently and how often they buy, then placed in one of six named segments: Best customers, Regulars, New, Occasional, Going quiet and Lost. Each segment comes with a profile and a next step.

* **About a quarter of customers are Best customers at every shop.** They bring in 68 percent of spend at the gift shop, 55 percent at Amazon and 48 percent at the grocery chain.
* **654 gift shop customers are going quiet.** They ordered several times, spent £733,000 between them, and have not been back in months. The app lists them.
* **Clustering was tested against the named segments.** It sorted customers slightly better, because it found a small group of very large buyers. The named segments are kept because anyone can read the rules behind them. Notebook 2 shows the contest.

## Market basket analysis

Every pair of products gets a support, a confidence and a lift. Pairs become rules that read "customers who buy this also buy that", and strongly linked products are grouped into families.

* **Gift shop:** sets sold as separate pieces. Nine in ten orders with the pink tea plate also have the green one.
* **Grocery chain:** cake mix and frosting, shampoo and conditioner, taco shells and taco seasoning.
* **Amazon:** the strongest links are groceries arriving in the same order. Outside food, most orders hold one or two things and there is little to pair.

## Did it hold up

Describing the past is easy. So the last 90 days of each shop were hidden, everything was rebuilt from the earlier sales, and the hidden days were the test.

| Segment at the cutoff | Gift shop | Amazon | Grocery |
| --- | --- | --- | --- |
| Best customers | 84% | 100% | 100% |
| Regulars | 64% | 99% | 99% |
| Going quiet | 51% | 90% | 96% |
| Occasional | 45% | 90% | 96% |
| New | 45% | | |
| Lost | 34% | 63% | 82% |

*Share of each segment that ordered again in the next 90 days.*

* The segments ranked customers in the same order at all three shops.
* At the gift shop the question is who comes back at all. At Amazon and the grocery chain nearly everyone does, and the segments matter for how much they spend.
* All 50 of the strongest product pairs kept selling together, at every shop.

## What cleaning found

Two cancelled orders had been bending the gift shop results. An 80,995 unit order was placed and cancelled twelve minutes later. Counting the sale and ignoring the cancellation made it the top product in the first version. Returns are now taken off the sales they undo.

## The app

```
pip install -e .
python -m streamlit run app.py
```

On Windows, double click `ShopLens.bat`.

Pick one of the three shops in the sidebar, or upload your own csv or Excel file and match seven columns. Every tab rebuilds for that data.

* **Overview**: revenue by month, top products, what cleaning removed
* **Customer Segmentation**: the six segments, how each one shops and what to do about it, repeat buying
* **Going quiet**: the customers worth contacting, sorted by spend
* **Market Basket Analysis**: rules with support, confidence and lift, and the product families
* **Did it hold up**: the forward check, with a choice of how many days to hold back

## How it is laid out

| Path | What it holds |
| --- | --- |
| `src/shoplens/clean.py` | Loads a file and takes returns off the sales they undo |
| `src/shoplens/segmentation.py` | Customer segmentation |
| `src/shoplens/market_basket.py` | Market basket analysis |
| `src/shoplens/forward.py` | The check against later sales |
| `notebooks/` | Five notebooks: cleaning, customer segmentation, market basket analysis, the forward check, and all three shops side by side |
| `app.py` | The app |
| `tests/` | Eleven tests on a small made up shop |
| `scripts/get_data.py` | How the Amazon and grocery files were built |
| `REPORT.md` | The findings written up, with charts |
| `original/` | The first version, untouched |

## Data

* [Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), UCI Machine Learning Repository, by Daqing Chen. CC BY 4.0.
* [Open e-commerce 1.0](https://doi.org/10.7910/DVN/YGLYDY): Amazon purchase histories shared by 5,027 US shoppers. CC0. Cut off at October 2022, when shoppers began exporting their histories. It has no order numbers, so one shopper on one day counts as one order.
* [The Complete Journey](https://github.com/bradleyboehmke/completejourney): household shopping at a US grocery chain, from 84.51°. CC0. The publisher shifted the dates to 2017. Fuel is left out.
