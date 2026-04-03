# Fund Autopsy Release Roadmap — N-CEN Data Series

Each release is a standalone feature module in Fund Autopsy + a companion X content piece from E.J. Baldwin. Every release follows the same pattern: build the tool, run it against real data, publish the findings.

---

## Release 1: Soft Dollar Transparency (LAUNCH)

### Tool: `fundautopsy analyze <TICKER>`
The flagship. Total cost of ownership with soft dollar isolation.

### What It Ships
- N-CEN parser extracting C.6.a, C.6.b, C.6.c
- N-PORT parser for holdings and asset class mix
- Bid-ask spread and market impact estimation
- Fund-of-funds recursive unwinding
- CLI with all three output tiers
- Comparison mode for 2-5 tickers

### Data Story
Run Fund Autopsy against the 50 largest actively managed mutual funds by AUM. Rank them by the gap between stated expense ratio and estimated total cost. Identify which fund families have the highest soft dollar intensity (C.6.b / C.6.a). Name names.

### X Thread
"Your mutual fund's expense ratio is not what it costs you." Walk through a specific fund with real numbers. Show the gap. Link to the tool.

### New Files
All core modules already scaffolded. Implementation priority: `data/ncen.py`, `data/nport.py`, `data/edgar.py`, `core/fund.py`, `core/costs.py`.

---

## Release 2: Securities Lending Revenue Split

### Tool: `fundautopsy lending <TICKER>`
New CLI command analyzing securities lending economics.

### What It Ships
- N-CEN securities lending fields: gross income, agent fees, net income, lending agent identity, affiliation status
- Lending efficiency ratio: net income / gross income (what % does the fund keep?)
- Affiliated lending agent flag and conflict-of-interest indicator
- Comparison across funds: who keeps more, who gives more away?

### Data Story
Pull securities lending data for every index fund with > $10B AUM. Rank by lending efficiency. Identify which fund families use affiliated lending agents and whether affiliated agents take a larger cut than independent agents. The hypothesis: affiliated lending agents keep a disproportionate share because the arrangement benefits the fund family, not the shareholders.

Highlight the dollar amounts. If an index fund with $100B AUM earns $50M in gross lending income but only passes through $30M to the fund, that's $20M/year extracted from shareholders through a related-party arrangement.

### X Thread
"Your index fund lends your shares to short sellers. Here's what happens to the money."

Show real numbers: Fund X earned $Y in gross lending income. The lending agent (which happens to be owned by the same parent company) kept Z%. You got the rest. Compare two similar funds — one with an independent agent, one affiliated — and show the efficiency gap.

### New Files
```
fundautopsy/
├── data/
│   └── securities_lending.py    # N-CEN lending field parser
├── core/
│   └── lending.py               # Lending economics computation
├── views/
│   └── lending.py               # Output formatter
└── cli.py                       # Add `lending` command
```

### N-CEN Fields
- Securities lending engagement flag (yes/no)
- Gross securities lending income ($)
- Fees/compensation paid to lending agent ($)
- Net securities lending income ($)
- Lending agent name
- Lending agent affiliation status (affiliated/independent)
- Collateral manager identity
- Average value of portfolio securities on loan

### Key Metrics to Compute
- **Lending efficiency ratio**: Net income / Gross income (higher is better for shareholders)
- **Lending intensity**: Average value on loan / Total net assets (what % of the portfolio is out on loan?)
- **Agent fee rate**: Agent fees / Gross income (the agent's take)
- **Income yield**: Net lending income / Total net assets (bps earned for shareholders)
- **Affiliation premium**: Difference in agent fee rate between affiliated and independent agent arrangements

---

## Release 3: Affiliated Broker Self-Dealing

### Tool: `fundautopsy brokers <TICKER>`
Analyze brokerage commission routing and affiliated broker concentration.

### What It Ships
- N-CEN affiliated broker-dealer disclosure: names, commission amounts
- Non-affiliated broker disclosure: names, gross commissions
- Affiliated broker concentration ratio: affiliated commissions / total commissions
- Fund family ranking by self-dealing intensity
- Time series: is affiliated routing increasing or decreasing?

### Data Story
Pull affiliated broker data for every fund family. Rank by what % of total commissions flow to their own brokerage arms. Identify the worst offenders. Then cross-reference with soft dollar data from Release 1 — are the families with the highest affiliated broker concentration also the ones with the most aggressive soft dollar programs? Double-dipping: routing trades through your own broker AND getting research kickbacks.

### X Thread
"Which fund families pay the most commissions to themselves?"

Publish the ranked list. Show which families route 30%+ of trade volume through their own brokerage desks. Ask the question: if you're paying commissions to an entity your fund manager owns, who is that arrangement designed to benefit?

### New Files
```
fundautopsy/
├── data/
│   └── brokers.py               # Affiliated + non-affiliated broker parser
├── core/
│   └── broker_analysis.py       # Concentration ratios, rankings
├── views/
│   └── brokers.py               # Output formatter
└── cli.py                       # Add `brokers` command
```

### N-CEN Fields
- Affiliated broker-dealer names
- Commission amounts per affiliated broker ($)
- Non-affiliated broker names (top 10 by commission volume)
- Gross commissions per non-affiliated broker ($)
- Total brokerage commissions (already captured in Release 1)

### Key Metrics
- **Affiliated concentration ratio**: Affiliated commissions / Total commissions
- **Affiliated broker count**: How many of the fund family's own entities receive commissions
- **Top broker dominance**: % of commissions going to the single largest broker
- **Cross-reference score**: Affiliated concentration x Soft dollar intensity (identifies double-dipping)

---

## Release 4: Principal Transactions

### Tool: `fundautopsy principals <TICKER>`
Analyze cross-trades and principal transactions with affiliated entities.

### What It Ships
- N-CEN principal transaction disclosure: counterparties, purchase/sale amounts
- Principal transaction volume as % of net assets
- Affiliated counterparty identification
- Fund family ranking by principal transaction intensity

### Data Story
Principal transactions are trades where the fund buys or sells securities directly with its adviser or an affiliated entity, rather than going through the open market. Both sides of the trade are controlled by related parties. These require board approval under Section 17(a) of the Investment Company Act, but the data in N-CEN shows some fund families do billions in principal transactions annually.

The question: are these trades done at fair market value? The data can't answer that directly, but it can show which families do the most of them, and it can prompt the question of why a fund needs to trade with its own adviser instead of the open market.

### X Thread
"These funds bought $X billion in securities directly from their own advisers last year. Here's why you should care."

Walk through what a principal transaction is, why it creates conflict of interest, and show the data on which fund families do the most of them.

### New Files
```
fundautopsy/
├── data/
│   └── principal_transactions.py  # N-CEN principal tx parser
├── core/
│   └── principal_analysis.py      # Volume metrics, rankings
├── views/
│   └── principals.py              # Output formatter
└── cli.py                         # Add `principals` command
```

### N-CEN Fields
- Principal transaction flag (yes/no)
- Counterparty names
- Purchase amounts per counterparty ($)
- Sale amounts per counterparty ($)
- Counterparty affiliation status

### Key Metrics
- **Principal transaction intensity**: Total principal tx volume / Total net assets
- **Buy/sell asymmetry**: Are funds net buyers or net sellers in principal trades? (Direction matters — is the adviser dumping inventory into the fund?)
- **Counterparty concentration**: % of principal volume with a single counterparty
- **Cross-reference**: Principal transaction intensity x Affiliated broker concentration (identifies families with multiple self-dealing channels)

---

## Release 5: Credit Line Stress Signals

### Tool: `fundautopsy credit <TICKER>`
Screen for funds showing signs of liquidity stress through credit facility utilization.

### What It Ships
- N-CEN credit facility data: existence, size, shared flag, lending institutions, max outstanding
- Credit utilization ratio: max outstanding / facility size
- Shared facility flag and sibling fund identification
- Industry screen: which funds drew hardest on their credit lines?

### Data Story
A mutual fund that taps its credit line is borrowing cash to meet redemptions. This isn't inherently alarming — credit facilities exist for this purpose — but high utilization is a signal worth watching. It means the fund didn't have enough cash or liquid assets on hand to meet shareholder withdrawals.

The shared facility angle is even more interesting. Many fund families maintain a single credit facility shared across all their funds. If one fund in the family has a liquidity crisis, it draws down capacity that every sibling fund was counting on. This is systemic risk within a fund family that nobody is screening for.

### X Thread
"These mutual funds maxed out their credit lines last year. Here's what that tells you about what happened behind the scenes."

Show the data. Which funds had the highest utilization? Were there periods where shared facilities were under stress from multiple funds drawing simultaneously?

### New Files
```
fundautopsy/
├── data/
│   └── credit_facilities.py      # N-CEN credit line parser
├── core/
│   └── credit_analysis.py        # Utilization metrics, stress scoring
├── views/
│   └── credit.py                 # Output formatter
└── cli.py                        # Add `credit` command
```

### N-CEN Fields
- Has line of credit (yes/no)
- Credit facility size ($)
- Shared facility flag (yes/no)
- Lending institution names
- Maximum amount outstanding during period ($)
- Shared facility participant fund names

### Key Metrics
- **Credit utilization ratio**: Max outstanding / Facility size
- **Utilization frequency**: How often was the line drawn? (may require time series across filings)
- **Shared facility stress score**: Number of funds sharing the facility x Average utilization
- **Cash buffer adequacy**: Compare credit utilization against N-PORT cash and liquid asset positions

---

## Release 6: Derivatives Mismatch Detector

### Tool: `fundautopsy derivatives <TICKER>`
Flag funds where derivatives usage seems inconsistent with stated investment objectives.

### What It Ships
- N-CEN derivatives disclosure: types used (futures, options, swaps, forwards), purposes
- Derivatives complexity score based on type diversity
- Cross-reference with fund category and stated objective
- Mismatch alerts: conservative/income funds with complex derivatives footprints

### Data Story
A "conservative balanced" fund that trades interest rate swaps, equity index options, and currency forwards is running a more complex strategy than its marketing suggests. The derivatives themselves aren't necessarily bad, but the gap between what's marketed to retail investors ("conservative income") and what's actually happening in the portfolio (multi-instrument derivatives trading) is worth flagging.

The N-CEN data tells you WHAT derivatives a fund uses and WHY (hedging, income generation, speculation). Cross-referencing this with the fund's Morningstar category and prospectus language can identify mismatches.

### X Thread
"Your 'conservative' bond fund traded derivatives last year. Here's what they were doing and whether you should care."

Pick 3-5 funds with seemingly conservative mandates and show their derivatives footprints. Explain what each derivative type does. Let the reader decide whether that matches what they thought they were buying.

### New Files
```
fundautopsy/
├── data/
│   └── derivatives.py            # N-CEN derivatives disclosure parser
├── core/
│   └── derivatives_analysis.py   # Complexity scoring, mismatch detection
├── views/
│   └── derivatives.py            # Output formatter
└── cli.py                        # Add `derivatives` command
```

### N-CEN Fields
- Derivatives types used (futures, options, swaps, forwards, other)
- Purpose of derivatives usage (hedging, income generation, leverage, speculation)
- Notional amounts (if reported)

### Key Metrics
- **Derivatives complexity score**: Number of distinct derivative types x Purpose diversity
- **Category mismatch flag**: Complexity score relative to fund category (a large-cap blend fund with 1 type is normal; a short-term bond fund with 4 types deserves scrutiny)
- **Purpose alignment**: Do stated purposes match fund category? (A bond fund using equity derivatives for "income generation" is doing something unusual)

---

## Release 7: Service Provider Dependency Graph

### Tool: `fundautopsy providers [--industry]`
Map the fund industry's service provider network and identify concentration risk.

### What It Ships
- N-CEN service provider data: administrators, custodians, transfer agents, pricing services, auditors, sub-advisers
- Provider concentration metrics: which providers have the most fund family clients?
- AUM exposure by provider: which custodian holds the most assets?
- Dependency graph: interactive visualization of provider relationships
- Single-point-of-failure identification

### Data Story
The mutual fund industry looks diverse from the front — thousands of funds, hundreds of fund families. But the back office is concentrated. A handful of custodians hold custody of trillions. A few transfer agents process the majority of shareholder transactions. A small number of pricing services value the most difficult-to-price securities.

If one of these critical providers has a major operational failure, the blast radius crosses fund family boundaries. This is systemic risk that nobody is visualizing because the data is fund-by-fund in N-CEN, not aggregated across the industry.

### X Thread
"One company holds custody of $X trillion in mutual fund assets. Here's the map of who depends on whom in the fund industry's back office."

Publish the dependency graph. Show the concentration numbers. Ask the question: what happens when a single critical provider has a bad day?

### New Files
```
fundautopsy/
├── data/
│   └── service_providers.py      # N-CEN provider parser
├── core/
│   └── provider_analysis.py      # Concentration metrics, graph building
├── views/
│   └── providers.py              # Output formatter + graph renderer
└── cli.py                        # Add `providers` command
```

### N-CEN Fields
- Investment advisers (name, SEC file number, CRD, LEI)
- Sub-advisers (name, file number, affiliation status)
- Administrators (name, LEI)
- Custodians (name, custody type)
- Transfer agents (name, SEC file number)
- Principal underwriters/distributors (name, affiliation status)
- Public accountants/auditors (name, PCAOB number)
- Pricing services (name)
- Shareholder servicing agents (name)

### Key Metrics
- **Provider market share**: Number of fund families using each provider; AUM served
- **Custodial concentration**: Top 5 custodians' share of total industry AUM
- **Audit concentration**: Top 5 auditors' share of fund family clients
- **Affiliation density**: % of a fund family's providers that are affiliated entities
- **Dependency depth**: Average number of unique providers per fund family (fewer = more concentrated risk)

---

## Release 8: Governance Quality Index

### Tool: `fundautopsy governance <TICKER or FAMILY>`
Score fund board governance quality and correlate with cost metrics.

### What It Ships
- N-CEN board data: director counts, independent member counts, chair independence
- Governance quality score per fund family
- Correlation analysis: governance score vs. fee levels, soft dollar intensity, affiliated broker usage
- Industry ranking

### Data Story
Academic research suggests that independent fund boards negotiate better fee deals for shareholders. The N-CEN data lets you test this at industry scale. Build a simple governance score (independent board majority + independent chair + reasonable board size) and cross-tabulate it against every other metric from Releases 1-7.

Do fund families with more independent governance charge lower fees? Have lower soft dollar intensity? Route less volume through affiliated brokers? The data exists to answer these questions definitively.

### X Thread
"Does your mutual fund's board actually work for you? We scored every fund family's governance using public SEC data and then cross-referenced it with what they charge."

Publish the governance rankings. Show the correlation (or lack thereof) with cost metrics. Let the data tell the story.

### New Files
```
fundautopsy/
├── data/
│   └── governance.py             # N-CEN board data parser
├── core/
│   └── governance_analysis.py    # Scoring, correlation analysis
├── views/
│   └── governance.py             # Output formatter
└── cli.py                        # Add `governance` command
```

### N-CEN Fields
- Number of directors/trustees
- Number of independent directors/trustees
- Whether the board chair is an interested person
- Director CRD numbers (for cross-referencing with FINRA BrokerCheck)

### Key Metrics
- **Independence ratio**: Independent directors / Total directors
- **Chair independence flag**: Binary (independent chair = 1, interested chair = 0)
- **Governance score**: Weighted composite of independence ratio + chair flag + board size reasonableness
- **Cost-governance correlation**: Regression of governance score against expense ratio, soft dollar intensity, affiliated broker concentration, lending efficiency

---

## Release Cadence

| Release | Target | Dependencies |
|---------|--------|-------------|
| 1. Soft Dollars (Launch) | ASAP | Core pipeline must work |
| 2. Securities Lending | Launch + 1 week | N-CEN parser from R1 |
| 3. Affiliated Brokers | Launch + 2 weeks | N-CEN parser from R1 |
| 4. Principal Transactions | Launch + 3 weeks | N-CEN parser from R1 |
| 5. Credit Line Stress | Launch + 4 weeks | N-CEN parser from R1 |
| 6. Derivatives Mismatch | Launch + 5 weeks | N-CEN parser + supplementary data |
| 7. Service Providers | Launch + 6 weeks | N-CEN parser, may need graph lib |
| 8. Governance Index | Launch + 7 weeks | All prior releases (cross-correlation) |

Each release is designed to be independent but additive. You can ship Release 3 without Release 2 if priorities shift. Release 8 is the capstone that ties everything together.

The content cadence matches: one X thread per week, each using real data from the corresponding release. By week 8, E.J. Baldwin has published a comprehensive data-driven critique of mutual fund cost transparency using nothing but public SEC filings.
