# Thread: The Obfuscation Problem

**Hook:** Academic researchers proved that the funds charging you the most are also the hardest to read. The correlation is not accidental.

---

**1/**
In 2021, a team of accounting researchers published a paper called "Obfuscation in Mutual Funds" in the Journal of Accounting and Economics. Their finding: high-fee funds systematically increase the complexity of their disclosure documents.

More pages. Longer sentences. Denser language. More structural complexity in fee tables.

**2/**
This is not a formatting issue. It's a strategy. When a fund charges above-average fees, it has a financial incentive to make those fees harder to identify, compare, and act on.

The researchers found that obfuscation was associated with lower sensitivity of fund flows to fees. In plain English: when people can't easily see the cost, they don't leave.

**3/**
The SEC has tried to address this. The summary prospectus (497K) was introduced specifically to create a standardized, simplified fee table. And for most funds, it works reasonably well.

But "reasonably well" still means three different HTML table formats across major fund families, inconsistent label names for the same fee category, and footnotes that redefine the numbers in the table above them.

**4/**
We know this because we built parsers for it. Fund Autopsy processes 497K fee tables from every major fund family, and the format variation is remarkable for a document that's supposed to be standardized.

Dodge & Cox uses clean tables. Oakmark splits labels across line breaks. Fidelity uses a completely different HTML structure. The "standard" format has at least three variants we've found so far.

**5/**
The obfuscation extends beyond the prospectus. The Statement of Additional Information, where broker commissions, revenue sharing, and portfolio manager compensation are disclosed, has no standardized format at all. Section headers, table structures, and disclosure depth vary wildly across fund families.

**6/**
The response to obfuscation is automation. If a document is designed to be hard for humans to read, build a machine that reads it anyway.

That's what Fund Autopsy does. Every SEC filing a fund submits gets parsed, normalized, and presented in a consistent format. The fund's formatting choices become irrelevant.

github.com/tombstoneresearch/fund-autopsy

---

**Notes:**
- Academic citation: deHaan, Song, Xie, Zhu (2021) in Journal of Accounting and Economics
- Thread connects our parsing work to a broader systemic problem
- The "three HTML formats" detail is unique to us — nobody else has documented this
- Positions Fund Autopsy as the antidote to deliberate complexity
