---
name: company-research
description: >
  Research a company for interview or consulting preparation. Given a company name
  or links, produces a structured briefing covering: overview, funding/financials,
  founders & leadership, strategy, culture, and recent news. Use when the user
  says "research [company]", "company research", "tell me about [company]",
  "prep me on [company]", shares company links before an interview, or asks
  about a company they're considering joining or consulting for.
---

# Company Research

Research companies the user is considering for interviews or consulting engagements. Produce a structured, actionable briefing from public sources.

## Workflow

### 1. Extract Company Identity

- Parse company name from user message, links, or context
- Decode URLs (Calendly redirects, UTM-tagged links, etc.) to find the actual domain
- Identify: company name, domain, HQ location, industry vertical
- If links are provided, note what they point to (blog, about page, certification, social impact) — these hint at what the company wants candidates to know

### 2. Research (Parallel)

Spawn **3 parallel subagents** (Agent tool, general-purpose) to cover these research tracks simultaneously. Each subagent should use WebSearch and WebFetch.

#### Track A: Company Overview & Financials
Search queries (adapt to company):
- `"[company]" founded funding series crunchbase`
- `"[company]" revenue ARR valuation`
- `"[company]" SEC filing 10-K 10-Q` (public companies)
- `"[company]" IPO S-1` (if recently public or pre-IPO)
- `site:crunchbase.com "[company]"`
- `site:pitchbook.com "[company]"`
- `"[company]" layoffs OR restructuring OR hiring` (last 12 months)
- `"[company]" total funding raised`
- `"[company]" customers OR clients OR case study`

Extract:
- Founded year, HQ, employee count (LinkedIn or recent articles)
- Funding rounds (date, amount, lead investor, valuation if disclosed)
- Revenue/ARR if public or reported
- Key customers and partnerships
- Competitive landscape — who are the main competitors?

#### Track B: Leadership, Culture & People
Search queries:
- `"[company]" CEO founder linkedin`
- `"[company]" CTO "engineering blog"`
- `"[company]" glassdoor reviews`
- `"[company]" culture values "engineering culture"`
- `"[company]" diversity OR inclusion OR DEI`
- `"[company]" "great place to work" OR "best workplace"`
- `"[company]" remote OR hybrid OR "return to office"`
- `site:glassdoor.com "[company]" reviews`
- `site:linkedin.com/company "[company]"`
- `"[company]" blog engineering team`

Extract:
- Founders — name, background, previous companies, LinkedIn
- C-suite / key leaders — CTO, VP Eng, CPO
- Board members / notable investors (signal of strategic direction)
- Work model (remote/hybrid/office, locations)
- Glassdoor rating and recurring themes (positive and negative)
- Engineering culture signals (blog, open source, tech talks, stack)
- Company values (from careers/about page)

#### Track C: Strategy, News & Public Filings
Search queries:
- `"[company]" strategy direction roadmap 2025 2026`
- `"[company]" acquisition OR acquired OR merger`
- `"[company]" partnership OR integration`
- `"[company]" SEC EDGAR` (public companies)
- `"[company]" earnings call transcript`
- `"[company]" analyst report`
- `"[company]" controversy OR lawsuit OR investigation`
- `"[company]" news` (last 6 months)
- `"[company]" product launch OR announcement`

Extract:
- Recent strategic moves (acquisitions, pivots, new products)
- SEC filings summary (revenue trends, risk factors, insider transactions)
- Earnings call themes (management commentary, guidance)
- Any controversies, lawsuits, regulatory issues
- Industry analyst commentary
- Product direction and roadmap signals

### 3. Report Format

Structure the output as a briefing document:

---

## [Company Name] — Research Briefing

### At a Glance

| Field | Detail |
|-------|--------|
| **Founded** | YYYY, City, Country |
| **Founders** | Name (background) |
| **HQ** | City, Country |
| **Employees** | ~N (source) |
| **Industry** | Vertical / category |
| **Stage** | Seed / Series X / Public / Private |
| **Last Valuation** | $X (date, if known) |
| **Total Funding** | $X across N rounds |
| **Revenue/ARR** | $X (if public or reported) |
| **Work Model** | Remote / Hybrid / Office |

### Funding & Financial History

Chronological table of funding rounds:

| Date | Round | Amount | Lead Investor | Valuation | Notes |
|------|-------|--------|---------------|-----------|-------|
| YYYY-MM | Seed | $Xm | Investor | — | ... |
| YYYY-MM | Series A | $Xm | Investor | $Xm | ... |

For public companies: revenue trend, margins, cash position, recent guidance.

### Leadership & Key Figures

For each key person:

**[Name] — [Title]**
- Background: previous roles, education, notable achievements
- LinkedIn: [link if found]
- Relevant: anything that helps in an interview (published talks, blog posts, open source)

Cover: CEO/founder, CTO/VP Eng, CPO, CFO, notable board members.

### Product & Market Position

- What the company does (one paragraph, technical depth)
- Core product(s) and how they differentiate
- Key customers (logos, case studies)
- Competitive landscape — direct competitors and positioning
- Technology stack (if discoverable from job postings, engineering blog, GitHub)

### Strategy & Direction

- Recent strategic moves (acquisitions, partnerships, new products)
- Where the company is heading (analyst commentary, earnings calls, CEO interviews)
- Growth vectors — geographic expansion, new verticals, platform plays
- Risks — market headwinds, competitive threats, regulatory exposure

### Culture & Work Environment

- Glassdoor rating and key themes
- Engineering culture (blog quality, open source presence, tech talks)
- Stated values vs observed reality
- Work model details (remote policy, office locations, flexibility)
- Red flags (if any — high turnover signals, recurring complaints)

### In the News (Last 12 Months)

| Date | Headline | Source | Relevance |
|------|----------|--------|-----------|
| YYYY-MM | ... | Publication | Brief note |

### SEC / Public Filings (if applicable)

Summary of most recent 10-K/10-Q:
- Revenue and growth rate
- Risk factors worth noting
- Management discussion highlights
- Insider transactions (any large sales?)

### Interview Angles

Based on the research, suggest 3-5 informed questions the user could ask in an interview that demonstrate they've done their homework:
- Questions that reference specific company initiatives, challenges, or strategic direction
- Questions that show understanding of the competitive landscape
- Questions about engineering culture or team structure based on signals found

---

### 4. Source Links

End the report with a numbered list of all sources consulted, with URLs.

### 5. Export (Optional)

Save the briefing for future reference. Examples:
- Export to a note-taking app (Bear, Obsidian, Notion)
- Save as markdown file: `research-[company].md`
- Append to a research log

## Notes

- Prioritise recent information (last 12-18 months)
- For startups: Crunchbase, PitchBook, TechCrunch, and company blog are primary sources
- For public companies: SEC EDGAR, earnings transcripts, and analyst coverage
- Glassdoor data is directional not definitive — note sample size
- If the company is very small/stealth, say so explicitly rather than padding with speculation
- Decode Calendly/redirect URLs to get actual company links: strip `https://calendly.com/url?q=` prefix and URL-decode
- If the user provides specific links, fetch and incorporate them into the relevant sections
- Currency: report in USD primary, note local currency equivalent if relevant to the user's location

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| No funding data found | Private/bootstrapped company | Check company blog "about" page, LinkedIn company page, note "bootstrapped or undisclosed" |
| SEC filings empty | Private company | Skip section, note "private — no public filings" |
| Glassdoor has few reviews | Small company or new listing | Note sample size, check Indeed and Blind as alternatives |
| WebFetch blocked on a URL | Site blocks automated access | Use WebSearch to find cached/summarised versions of the content |
| Crunchbase paywalled | Free tier limits | Search `"[company]" crunchbase funding` — snippets often contain key data |

## Cross-References
- Feeds into job application and interview preparation workflows
- Research briefings can inform cover letters and outreach
