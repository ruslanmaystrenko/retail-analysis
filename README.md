# Retail Analysis

**Customer segmentation** and **market basket analysis** for any file of sales, with a check on whether the results hold up on later sales.

It answers three questions. Who are the customers and which ones matter? Who is drifting away? What sells together?

This is a rebuild of an earlier project of mine. The first version is kept in `original/`, and [REWORK.md](REWORK.md) explains what was wrong with it and what changed. The findings are written up in [REPORT.md](REPORT.md).

## Three shops, one method

The same code runs on three very different sets of sales.

| Shop | Period | Customers | Orders | A product is |
| --- | --- | --- | --- | --- |
| UK gift retailer | 2010 to 2011 | 4,324 | 18,268 | A single item |
| Amazon shoppers | 2018 to 2022 | 5,013 | 749,808 | A category, such as pet food |
| US grocery chain | 2017 | 2,467 | 140,925 | A type, such as bananas |

## Customer segmentation

Every customer is scored on how recently and how often they buy, then placed in a named segment: Best customers, Regulars, New, Occasional, Going quiet or Lost. A seventh segment, Big spenders, holds the Best customers in the top twentieth by spend. Each segment comes with a profile and a next step.

* **Big spenders are 4 percent of customers and 44 percent of revenue at the gift shop.** At Amazon they are 18 percent of spend and at the grocery chain 16.
* **Big spenders and Best customers together are about a quarter of customers at every shop.** They bring in between half and two thirds of all spend.
* **654 gift shop customers are going quiet.** They ordered several times, spent £733,000 between them, and have not been back in months. The app lists them.
* **Clustering was tested against the named segments, and improved them.** It found a group of very large buyers the first six segments missed. That became Big spenders, and the named segments now lead on spend. Notebook 2 shows the contest.

## Market basket analysis

Every pair of products gets a support, a confidence and a lift. Pairs become rules that read "customers who buy this also buy that", and strongly linked products are grouped into families.

* **Gift shop:** sets sold as separate pieces. Nine in ten orders with the pink tea plate also have the green one.
* **Grocery chain:** cake mix and frosting, shampoo and conditioner, taco shells and taco seasoning.
* **Amazon:** the strongest links are groceries arriving in the same order. Outside food, most orders hold one or two things and there is little to pair.

## Did it hold up

Describing the past is easy. So the last 90 days of each shop were hidden, everything was rebuilt from the earlier sales, and the hidden days were the test.

| Segment at the cutoff | Gift shop | Amazon | Grocery |
| --- | --- | --- | --- |
| Big spenders | 99% | 100% | 100% |
| Best customers | 81% | 100% | 100% |
| Regulars | 64% | 99% | 99% |
| Going quiet | 51% | 89% | 96% |
| Occasional | 45% | 90% | 97% |
| New | 45% | | |
| Lost | 34% | 63% | 82% |

*Share of each segment that ordered again in the next 90 days.*

* The segments ranked customers in the same order at all three shops.
* At the gift shop the question is who comes back at all. At Amazon and the grocery chain nearly everyone does, and the segments matter for spend: a Big spender is worth thirteen to nineteen times a Lost customer.
* All 50 of the strongest product pairs kept selling together, at every shop.

**Then the check was repeated at earlier cutoff days**, 90 days apart: three for the gift shop, three for the grocery chain and eight for Amazon. The top segments kept their order at all fourteen. The gift shop's quiet summer lowered every number, and 45 of its 50 pairs held in that window.

## What cleaning found

Two cancelled orders had been bending the gift shop results. An 80,995 unit order was placed and cancelled twelve minutes later. Counting the sale and ignoring the cancellation made it the top product in the first version. Returns are now taken off the sales they undo.

## The app

```
pip install -e .
python -m streamlit run app.py
```

On Windows, double click `RetailAnalysis.bat`.

Pick one of the three shops in the sidebar (it opens on Amazon), or upload your own csv or Excel file and match seven columns. Every tab rebuilds for that data.

* **Overview**: what was learned and what to do about it, written from the data, then revenue by month, top products and who is buying
* **Customer Segmentation**: the seven segments, how each one shops and what to do about it, repeat buying
* **Going quiet**: the customers worth contacting, sorted by spend
* **Market Basket Analysis**: rules with support, confidence and lift, and the product families
* **Did it hold up**: the forward check, repeated at several cutoff days, with a choice of how many days to hold back

## How it is laid out

| Path | What it holds |
| --- | --- |
| `src/retail_analysis/clean.py` | Loads a file and takes returns off the sales they undo |
| `src/retail_analysis/segmentation.py` | Customer segmentation |
| `src/retail_analysis/market_basket.py` | Market basket analysis |
| `src/retail_analysis/forward.py` | The check against later sales |
| `notebooks/` | Five notebooks: cleaning, customer segmentation, market basket analysis, the forward check, and all three shops side by side |
| `app.py` | The app |
| `tests/` | Thirteen tests on a small made up shop |
| `scripts/get_data.py` | How the Amazon and grocery files were built |
| `REPORT.md` | The findings written up, with charts |
| `original/` | The first version, untouched |

## Data

* [Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), UCI Machine Learning Repository, by Daqing Chen. CC BY 4.0.
* [Open e-commerce 1.0](https://doi.org/10.7910/DVN/YGLYDY): Amazon purchase histories shared by 5,027 US shoppers. CC0. Cut off at October 2022, when shoppers began exporting their histories. It has no order numbers, so one shopper on one day counts as one order.
* [The Complete Journey](https://github.com/bradleyboehmke/completejourney): household shopping at a US grocery chain, from 84.51°. CC0. The chain is not named. The publisher shifted the dates, so 2017 is a label. Fuel is left out.
