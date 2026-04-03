# E.J. Baldwin — Persona Package

## The Name
**E.J. Baldwin** — Named after Elias Jackson "Lucky" Baldwin (1828–1909), the 19th century speculator who made fortunes in mining stocks, real estate, and railroads. Baldwin's edge was never luck. It was information asymmetry — he did the work to see what things actually cost while everyone else traded on surface numbers. That's what Tombstone Research does with mutual fund costs.

## The Brand
**Tombstone Research** — Double meaning. In finance, a tombstone is the advertisement announcing a securities underwriting deal. In the American West, it's the town where the reckoning happened. Tombstone Research is where the fund industry's hidden costs get a proper burial notice.

**Tagline:** *The reckoning is in the filings.*

---

## X Account: @ejbaldwin

### Bio (160 chars)
```
Mutual fund costs are a lie of omission. I read the filings nobody reads. Open source. Anonymous.
Tombstone Research | github.com/tombstoneresearch
```

### Alt Bio (shorter, punchier)
```
Reading the SEC filings your fund company hopes you won't.
@tombaborneresearch | Open source fund cost analysis
```

### Pinned Tweet (Draft — Launch Day)
```
Your mutual fund's expense ratio is not what it costs you.

Soft dollar arrangements. Brokerage commissions. Bid-ask spreads. Market impact drag.

This data is in SEC filings. Nobody aggregates it. Nobody presents it.

Until now.

Introducing Fund Autopsy — open source, free, transparent.

github.com/tombstoneresearch/fund-autopsy

🧵 Thread below on what we found.
```

### Thread #1 — Soft Dollars (Launch Thread)
```
1/ The mutual fund industry has a cost transparency problem.

Every cost calculator stops at the expense ratio. But the expense ratio is just the cover charge. The real tab is running behind the scenes in SEC filings nobody reads.

Let me show you what I mean.

2/ SEC Form N-CEN requires every mutual fund to report:
- Total brokerage commissions paid (Item C.6.a)
- Commissions paid to brokers providing research services (Item C.6.b)

That second line is the soft dollar number. It's the portion of YOUR trading costs that subsidize research for the adviser.

3/ Why does this matter?

Because the adviser could pay for that research out of its own management fee. Instead, it routes trades through brokers who bundle research into the commission. The fund — meaning you — pays a higher commission than necessary so the adviser gets "free" research.

4/ This is legal. It's been legal since Section 28(e) of the Securities Exchange Act of 1934 created the safe harbor.

But legal doesn't mean free. It means the cost is hidden in your pre-gross returns. You still subtract the expense ratio on top of that.

5/ Nobody aggregates this data. The SEC collects it. It sits in XML files on EDGAR. The information is technically public.

Fund Autopsy reads those filings, computes soft dollar commissions as a percentage of net assets, and shows you the gap between what your fund says it costs and what it actually costs.

6/ We're open-sourcing everything.

The parser. The cost model. The methodology. The data.

If you want to know what your fund actually costs, or if you want to build on this:

github.com/tombstoneresearch/fund-autopsy

This is thread 1 of 8. Next: securities lending revenue splits.
```

---

## GitHub: tombstoneresearch

### Org Bio
```
Open-source tools for mutual fund cost transparency. We read the filings nobody reads.
```

### Org README (profile README)
```markdown
## Tombstone Research

Open-source financial analysis tools built on public SEC data.

**Active Projects:**
- [Fund Autopsy](https://github.com/tombstoneresearch/fund-autopsy) — Mutual fund total cost of ownership analyzer

**What We Do:**
We parse SEC filings (N-CEN, N-PORT, N-CSR) that the fund industry files but hopes you'll never read, and turn them into tools that answer questions the industry doesn't want asked.

**Philosophy:**
- Open source. Always.
- Data comes from public filings. Always cited.
- Estimates are labeled as estimates. Reported data is labeled as reported.
- We show our work.

*The reckoning is in the filings.*
```

---

## Gmail
**Recommended:** tombstoneresearch@gmail.com
**Fallback:** tombstone.research@gmail.com or ejbaldwin.research@gmail.com

Used for: GitHub account, X account, any future platform signups. Not for public display.

---

## Avatar Concept

### Direction: Old West Wanted Poster Aesthetic
A weathered, sepia-toned composition evoking a 19th century handbill or wanted poster. The central element is typographic rather than a face — keeping the anonymous researcher mystique.

**Elements:**
- Aged paper texture, torn edges, slight foxing/staining
- Bold serif typeface: "TOMBSTONE RESEARCH" across the top in woodblock style
- Center: A stylized magnifying glass over a financial document or ticker tape
- Or: A skull with a monocle examining a ledger (playful but not cartoonish)
- Bottom: "EST. 2026" in small type
- Color palette: Sepia, aged cream, dark brown, with one accent color (gold or deep red)

**What it should NOT be:**
- A real face or photo
- Cartoonish or meme-style
- Overly corporate/clean — it should feel like it was printed in a frontier town
- Anything that looks AI-generated in the obvious Midjourney house style

### Alt Direction: Typographic Monogram
Clean, modern approach. "TR" monogram in a strong geometric typeface, set inside a hexagonal or circular frame. Think: what if a quant fund had an anonymous research arm. Works better at small sizes (X profile pic). Less personality than the wanted poster direction but more versatile.

---

## Content Calendar — N-CEN Data Series

| Week | Thread Topic | Hook | N-CEN Fields |
|------|-------------|------|-------------|
| Launch | Soft dollars + Fund Autopsy release | "Your fund's expense ratio is not what it costs you" | C.6.a, C.6.b, C.6.c |
| +1 | Securities lending revenue splits | "Your index fund lends your shares. Here's how much you get back" | Sec lending gross income, agent fees, net income |
| +2 | Affiliated broker self-dealing | "Which fund families pay the most commissions to themselves?" | Affiliated broker-dealer commissions |
| +3 | Principal transactions | "When your fund buys securities from its own adviser" | Principal transaction counterparties, amounts |
| +4 | Credit line stress signals | "These funds needed emergency cash last year" | Lines of credit, max outstanding, facility size |
| +5 | Derivatives mismatch | "Your 'conservative' fund's derivatives footprint" | Derivatives types, purposes |
| +6 | Service provider concentration | "The hidden single points of failure in the fund industry" | Custodians, admins, auditors, transfer agents |
| +7 | Governance scoring | "Does your fund's board actually work for you?" | Director counts, independence status |

After the initial 8-thread series, transition to recurring analysis: quarterly updates when new N-CEN/N-PORT filings drop, spotlighting specific fund families, responding to industry news with data.
