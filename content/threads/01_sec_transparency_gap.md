# Thread: The SEC Transparency Gap

**Hook:** The SEC built a database in 2018 that shows exactly what your mutual fund costs. Seven years later, nobody has made it usable. Until now.

---

**1/**
In 2018 the SEC modernized two filing requirements for mutual funds: Form N-CEN and Form N-PORT. The stated purpose was improving transparency around fund operations and costs.

N-CEN captures brokerage commissions, soft dollar arrangements, affiliated broker usage, and securities lending revenue. N-PORT captures complete portfolio holdings every quarter.

**2/**
These filings are machine-readable. Structured data. Submitted by every mutual fund in America, every year, and posted publicly to EDGAR.

The SEC built the infrastructure for investors to see exactly what their funds cost beyond the expense ratio. Then they stopped.

**3/**
No consumer-facing tool was built. No dashboard, no calculator, no comparison engine. The data sits in EDGAR, formatted in XML and HTML, accessible to anyone willing to navigate a 1990s-era filing search system. Which is effectively nobody.

**4/**
Meanwhile every fund comparison tool on the market — FINRA's Fund Analyzer, Morningstar, your broker's screener — still uses the expense ratio as the cost metric.

The expense ratio covers management fees, 12b-1 fees, and admin costs. It does not cover brokerage commissions, bid-ask spreads, market impact, or soft dollar arrangements. Those costs are often larger than the expense ratio itself.

**5/**
Edelen, Evans, and Kadlec (2013) found that the average active fund's annual trading costs were 1.44% — exceeding the average expense ratio of 1.21%. The costs that nobody shows you are bigger than the cost that everybody shows you.

The SEC mandated disclosure of this data. Then the industry waited for someone to use it.

**6/**
Seven years of structured, machine-readable cost data. Filed by every fund. Available to anyone.

We built the tool. Fund Autopsy pulls from N-CEN, N-PORT, and the prospectus to show what your fund actually costs. Open source. Free. Every data point traced back to its SEC filing.

github.com/tombstoneresearch/fund-autopsy

**7/**
This is the first in a series on what we're finding inside these filings. Soft dollar arrangements where your fund pays inflated commissions for research the manager should buy themselves. Affiliated broker conflicts. Portfolio manager compensation structures with zero performance incentive.

The data has been there all along. Follow along as we dig it up.

---

**Notes:**
- No feature required, pure narrative
- CTA: GitHub link + follow
- Positions Tombstone Research as the entity solving a regulatory gap
- The Edelen et al. stat is the anchor — trading costs > expense ratio lands hard
