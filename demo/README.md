# demo — SkyNet Flights

A self-contained showcase: **one dataset, two native views**, and one concrete
business question that cannot be answered from either view alone.

```
demo/
  flights.lx      the showcase program (well-commented, prints data → answer)
  flights.csv     the ticket table   → read as a Table · PRICES live here
  routes.csv      the route map      → read as a Graph  · airlines on edges
  README.md       this file
```

## Run it

From the repo root:

```bash
lynx demo/flights.lx            # once `pip install -e .`
python -m src.main demo/flights.lx    # works without installing
```

## The business problem

A customer in Paris wants to fly to New York. There is **no direct Paris→New York
flight**. We are the booking engine. Our job is to quote:

> **The cheapest Paris→New York itinerary with at most one stopover, with a total
> price and the airline of each leg.**

The answer: *Fly Paris → Berlin on EasyJet (40 €), then Berlin → New York on
Lufthansa (280 €). Total: 320 €.*

The point is that **neither source alone can produce that quote**:

- The **route map** (`routes.csv`, a Graph) is the only place that says *which
  stopover cities connect Paris to New York at all* (`from net 'paris'`, an edge
  to the hub) and *which airline operates each leg* (edge labels). But it holds
  **no prices** — a graph cannot quote anything.
- The **ticket table** (`flights.csv`, a Table) is the only place that holds
  **prices**. Every leg of every candidate itinerary must be priced by looking
  the route up in the table (`where legs 'route' = …`). But a table cannot express
  "reachable with one stopover" — that is a recursive self-join in SQL/pandas.

So the script walks the graph to find candidates and prices each candidate inside
the same loop, then keeps the cheapest — the whole booking decision in ~10 lines:

```lynx
best_route: g, legs, a, b
    best: 100000
    via: void
    loop m: from g a                       // candidates: the graph
        leg1: first (where legs 'route' = a + '-' + m) 'price'   // fares: the table
        leg2: first (where legs 'route' = m + '-' + b) 'price'
        if ((type leg1) = Number) * ((type leg2) = Number)
            cost: leg1 + leg2
            if cost < best
                best: cost
                via: m
    >>> best, via
```

## What the program prints

```
── inputs ──────────────────────────────────────────────────
┌────────────────┬───────────┬─────┬─────────┐
│ route          │ airline   │price│ dest    │
├────────────────┼───────────┼─────┼─────────┤
│'paris-london'  │'easyjet'  │  45 │'london' │
│'paris-berlin'  │'easyjet'  │  40 │'berlin' │
│'london-newyork'│'british'  │ 320 │'newyork'│
│'berlin-newyork'│'lufthansa'│ 280 │'newyork'│
│'rome-newyork'  │'ita'      │ 210 │'newyork'│
└────────────────┴───────────┴─────┴─────────┘
paris('Paris') -> london, berlin : 'easyjet'
london -> newyork : 'british'
berlin -> newyork : 'lufthansa'
rome('Fiumicino') -> newyork : 'ita'
── is there a direct paris -> newyork flight? ───────────────
void
── answer · cheapest paris → newyork itinerary ──────────────
[ 320, berlin ]
── the quote ────────────────────────────────────────────────
paris → berlin on easyjet · 40 EUR
berlin → newyork on lufthansa · 280 EUR
total: 320 EUR
the other stopover (london) would be 365 EUR
── context · one-stopover premium ────────────────────────────
cheapest newyork ticket in the market: 210 EUR
so reaching newyork from paris costs 110 EUR more than that
```

The customer-facing answer, in one sentence:

> Fly **Paris → Berlin (EasyJet, 40 €)** + **Berlin → New York (Lufthansa,
> 280 €)** = **320 €** — the cheapest of the two possible stopovers (London would
> be 365 €), and 110 € above the market's cheapest New York ticket (210 €, Rome).

## Why lynx (vs Python + pandas + networkx)

The same answer in the classic stack needs two libraries and glue to move data
between them — the graph view for routing, the table view for pricing:

```python
import pandas as pd, networkx as nx          # two worlds, already

legs = pd.read_csv("demo/flights.csv")
bench = legs.loc[legs.dest == "newyork", "price"].min()   # 210

G = nx.DiGraph()                              # rebuild the graph by hand
for line in open("demo/routes.csv").readlines()[1:]:
    k, f, t, v = line.strip().split(",")
    if k == "node": G.add_node(f, city=v)
    elif k == "edge": G.add_edge(f, t, airline=v)

best, via = 1e9, None                         # hand-rolled BFS + price lookups
for m in G["paris"]:                          # "from net 'paris'"
    p1 = legs.loc[legs.route == f"paris-{m}", "price"]
    p2 = legs.loc[legs.route == f"{m}-newyork", "price"]
    if len(p1) and len(p2) and p1.iloc[0] + p2.iloc[0] < best:
        best, via = p1.iloc[0] + p2.iloc[0], m

print(via, best, best - bench)                # berlin 320 110 — same answer
```

lynx is one language, one value model, no imports:

| step | pandas/networkx | lynx |
|---|---|---|
| ingest both views, typed | `pd.read_csv` + hand parser / `nx.*` | `read 'demo/flights.csv'`<br>`read 'demo/routes.csv'` |
| a route exists? | `G.has_edge("paris","newyork")` | `net 'paris' -> 'newyork'` |
| stopover candidates | `list(G["paris"])` | `from net 'paris'` |
| airlines on edges | `G[...][...]["airline"]` | `net 'paris' -> 'berlin'` |
| price one leg | `legs.loc[legs.route == "paris-berlin","price"]` | `first (where legs 'route' = 'paris-berlin') 'price'` |
| price a subset, min of | `legs[legs.dest=="newyork"]["price"].min()` | `min (where legs 'dest' = 'newyork') 'price'` |
| cheapest itinerary | hand-rolled BFS + bookkeeping | a 9-line lynx function |

The pitch, in one line: **the same data keeps its natural shape whether you view
it as rows or as a network — same language, same operators, no glue, and the
"query the network, price the tickets" loop reads like the decision itself.**

## Using this as a demo video

The script answers the question on screen: inputs, then `void` (no direct flight),
then the winning itinerary, the quote, and the benchmark. Record the terminal
running `lynx demo/flights.lx`, and narrate:

1. Two files, two shapes of the *same* network — `read` types both on the way in.
   The table holds prices; the graph holds structure and airline labels.
2. The graph says there is **no direct** Paris→New York edge (`void`).
3. `best_route` loops the graph for candidate stopovers and prices each leg in
   the table — the decision logic itself — and prints `[ 320, berlin ]`.
4. The quote prints the winning legs, airlines, total (320 €), and why London
   loses (365 €).
5. One table query gives the context: the cheapest New York ticket anywhere is
   210 €, so the one-stopover premium is 110 €.