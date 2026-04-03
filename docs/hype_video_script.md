# Fund Autopsy — Reveal Video Script & Storyboard

**Duration:** ~65 seconds
**Style:** Palantir/Anduril cinematic product reveal. Dark background, typography-driven, data visualizations materializing from nothing, terminal footage, subtle particle effects. No voiceover — text and visuals only, set to atmospheric/tension-building music.
**Resolution:** 1920x1080 (landscape, optimized for X video)

---

## SHOT LIST

### ACT 1: THE LIE (0:00–0:20)

**[0:00–0:03] — COLD OPEN**
Black screen. Single line fades in, centered, white serif type on black:

> "What does your mutual fund cost you?"

Hold 2 seconds. Fade out.

**[0:03–0:07] — THE ANSWER EVERYONE GIVES**
Quick montage of numbers materializing and stacking:

```
Expense Ratio: 0.62%
```

The number glows confidently. Clean. Authoritative.
Then — small text appears beneath it, like a footnote gaining confidence:

```
...is what they tell you.
```

**[0:07–0:12] — THE CRACK**
The 0.62% number starts to fracture — hairline cracks spreading through it like glass. Behind the cracks, dim red numbers begin to glow through:

```
+ Brokerage Commissions    0.08%
+ Soft Dollar Drag         0.04%
+ Bid-Ask Spread Cost      0.06%
+ Market Impact            0.09%
```

Each line reveals in sequence (0.5s each), stacking beneath the cracking expense ratio.

**[0:12–0:16] — THE REAL NUMBER**
The cracked expense ratio shatters and falls away. The component costs consolidate upward into a new, larger number:

```
Estimated Total Cost: 0.89%
```

Pulsing glow. Hold 1 second.

Below it, a thin line of text:

```
27 basis points you were never told about.
```

**[0:16–0:20] — THE QUESTION**
Fade to black. New text:

> "Where do these costs hide?"

---

### ACT 2: THE DATA (0:20–0:42)

**[0:20–0:25] — SEC FILING RAIN**
Dark screen. Thousands of tiny XML tags and filing fragments begin falling like rain/matrix-style from the top of the screen. They're fragments of real N-CEN XML:

```xml
<brokerageCommissions>
<totalAmount>22847000</totalAmount>
<softDollarAmount>10281150</softDollarAmount>
<softDollarFlag>Y</softDollarFlag>
```

The rain condenses into a focused stream, flowing into a glowing terminal window.

**[0:25–0:32] — THE TERMINAL**
A terminal window materializes center-screen. Commands type themselves:

```bash
$ fundautopsy AGTHX --detail advisor

  Fund Autopsy — Analyzing AGTHX

  ✓ Stage 1: Fund identified — American Funds Growth Fund of America
  ✓ Stage 2: N-CEN retrieved (filed 2025-03-14)
  ✓ Stage 3: Cost computation complete
  ✓ Stage 4: No fund-of-funds structure detected

  ┌─────────────────────────────────────────┐
  │         TOTAL COST OF OWNERSHIP         │
  │                                         │
  │  Expense Ratio          62 bps  REPORTED│
  │  Brokerage Commissions   8 bps  REPORTED│
  │  Soft Dollar Drag        4 bps  REPORTED│
  │  Bid-Ask Spread       4-7 bps ESTIMATED │
  │  Market Impact        3-9 bps ESTIMATED │
  │                                         │
  │  TOTAL            81-90 bps             │
  │  Gap from stated ER: 19-28 bps          │
  └─────────────────────────────────────────┘
```

Each line types rapidly but readably. Data source tags (REPORTED/ESTIMATED) pulse with subtle color coding — green for REPORTED, amber for ESTIMATED.

**[0:32–0:38] — FUND-OF-FUNDS UNWINDING**
Terminal clears. New command:

```bash
$ fundautopsy FFFHX --detail advisor

  Fund Autopsy — Analyzing FFFHX

  ✓ Fund-of-funds detected: 18 underlying funds
  ✓ Recursive unwinding...
```

A tree diagram materializes showing FFFHX at the top, branching down to its underlying funds, each node pulsing as its cost data loads. Lines connect parent to children with allocation weights flowing along the edges.

```
  FFFHX (Fidelity Freedom 2040)
  ├── 28.4%  Fidelity Series Growth Fund
  ├── 22.1%  Fidelity Series International Growth
  ├── 18.7%  Fidelity Series Bond Fund
  ├── 12.3%  Fidelity Series Small Cap Discovery
  ├── ...14 more underlying funds
  │
  Rolled-Up Total Cost: 73-91 bps
```

**[0:38–0:42] — COMPARISON**
Split screen. Two funds side by side, costs stacking as horizontal bars racing toward the right. One fund's bars are visibly longer. Dollar impact counter at the bottom:

```
  $100,000 invested over 20 years
  Cost difference: $14,200 - $23,800
```

The number ticks up like a counter.

---

### ACT 3: THE MISSION (0:42–0:65)

**[0:42–0:47] — DATA SOURCES**
Clean infographic. Three filing types materialize as glowing document icons:

```
N-CEN          N-PORT          N-CSR
Commissions    Holdings        Expense Ratios
Soft Dollars   Asset Classes   Fee Tables
Turnover       Fund Detection
```

Thin lines connect them to a central node labeled "Fund Autopsy" — showing data flowing in from all three sources.

**[0:47–0:52] — THE GAP**
Typography sequence, each line replacing the last:

> "The SEC collects this data."
> "Fund companies file it every year."
> "Nobody aggregates it."
> "Nobody presents it."
> "Nobody makes it usable."

Pause.

> "We do."

**[0:52–0:57] — OPEN SOURCE**
GitHub-style code window materializes:

```
MIT License
github.com/tombstoneresearch/fund-autopsy

★ Open source. Free. Transparent.
★ Every data point tagged: REPORTED or ESTIMATED.
★ We show our work.
```

**[0:57–0:62] — THE BRAND**
Fade to black. The Tombstone Research logo materializes — aged, textured, the wanted poster aesthetic.

Below it:

> **TOMBSTONE RESEARCH**
> *The reckoning is in the filings.*

**[0:62–0:65] — CALL TO ACTION**
Logo holds. URL fades in below:

```
github.com/tombstoneresearch/fund-autopsy
@ejbaldwin
```

Hard cut to black.

---

## MUSIC NOTES
Atmospheric, building tension. Think: Trent Reznor/Atticus Ross score energy. Starts sparse and ominous for Act 1, builds with pulsing bass for Act 2 (the data reveal), opens into something slightly triumphant for Act 3 (the mission). No lyrics. No voiceover competing. The text IS the voice.

Royalty-free options: Epidemic Sound or Artlist, search for "cinematic technology tension" or "dark corporate reveal."

## COLOR PALETTE
- Background: Near-black (#0a0a0f)
- Primary text: Off-white (#e8e6e3)
- Accent 1: Amber/gold (#c9a84c) — for ESTIMATED tags, emphasis
- Accent 2: Green (#4ade80) — for REPORTED tags
- Accent 3: Deep red (#dc2626) — for hidden cost reveals, cracks
- Glow effects: Subtle bloom on key numbers
