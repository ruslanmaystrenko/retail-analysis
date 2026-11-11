# What changed and why

The first version of this project (in `original/`) cleaned the data, clustered customers into three segments and ran association rules on baskets. It read well. Going back through it, five things did not hold.

## 1. Cancelled orders were counted as sales

The first version dropped rows with a negative quantity. That removes the cancellation and keeps the sale it cancelled.

Two orders show the damage. One customer ordered 80,995 paper craft kits and cancelled twelve minutes later. Another ordered 74,215 storage jars and cancelled the same day. Both stayed in as revenue, which made a product nobody kept the top seller and put both buyers among the top customers.

**Now:** each return is taken off that customer's most recent earlier purchase of the same product. Revenue drops by 7 percent and both orders disappear.

## 2. Postage and fees were treated as products

Rows for postage, bank charges and manual adjustments sat in the product list and showed up in baskets.

**Now:** anything whose code is not a product code is removed before analysis.

## 3. The segments had no names and no use

Clustering produced three groups described by their averages. Nobody could say what to do with group 2.

**Now:** six groups with plain names, built from two simple scores: how recently a customer bought and how often. The rules fit in ten lines and anyone can check them.

## 4. Nothing was tested

The first version described the past and stopped. There was no way to know whether the segments or the product rules meant anything going forward.

**Now:** the last 90 days are held back. Groups and pairs are built from the earlier sales and then measured on the later ones. The groups ranked who came back, and all 50 of the strongest pairs kept selling together.

## 5. It was three notebooks, with nothing to use

The work could be read and could not be run on another shop's data.

**Now:** the logic is a small tested package, and an app sits on top of it. Upload a sales file and it produces the same analysis.

## What stayed

The data, the questions, and the original notebooks and reports, which are kept as they were.
