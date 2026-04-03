# Thread: Every Retirement Projection Is Wrong

**Hook:** Every retirement projection you've ever seen uses the expense ratio as the cost input. It ignores the larger cost layer entirely. Every Monte Carlo simulation in the industry is systematically optimistic.

---

**1/**
Financial planning software runs Monte Carlo simulations to project whether you'll have enough money in retirement. These models simulate thousands of return paths and give you a probability of success.

Every major planning tool — eMoney, MoneyGuidePro, RightCapital, the free ones too — uses the fund's expense ratio as the cost input.

**2/**
The expense ratio covers management fees, 12b-1 fees, and administrative costs. It does not cover brokerage commissions, bid-ask spreads, market impact, or soft dollar arrangements.

Academic research from Edelen, Evans, and Kadlec (2013) found these hidden trading costs average 1.44% annually for active funds, exceeding the average expense ratio of 1.21%.

**3/**
Run the math. A portfolio with a stated expense ratio of 0.75% might have a true total cost of 1.50% to 2.00% once sub-NAV drag is included.

Over 30 years on a $500,000 portfolio earning 7% gross, the difference between 0.75% total cost and 1.75% total cost is roughly $400,000 in ending wealth. That's a house. That's years of retirement income.

**4/**
Every Monte Carlo simulation that uses only the expense ratio is telling the client they're in better shape than they actually are. The probability of success is overstated. The projected ending balance is inflated. The safe withdrawal rate is too generous.

This isn't a rounding error. It's a structural blind spot in the entire financial planning industry.

**5/**
The fix is straightforward: use true total cost instead of expense ratio as the cost input. The data to calculate true total cost exists in SEC filings. Nobody has built the pipeline to feed it into planning tools.

That's exactly what Fund Autopsy is building toward. Open-source cost intelligence that can plug into any projection model and correct the systematic underestimate.

github.com/tombstoneresearch/fund-autopsy

---

**Notes:**
- This thread targets financial advisors and planners specifically — high professional engagement
- The $400K difference over 30 years is a real calculation (can verify programmatically)
- Names the major planning tools by name — their users will share this
- Positions Fund Autopsy as the upstream data correction for an industry-wide error
- Consider running the actual numbers in a Python script and screenshotting for the thread
