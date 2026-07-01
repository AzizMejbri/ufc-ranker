# UFC Elo Rating System

Computes Elo ratings for UFC fighters by scraping fight history from [ufctime.com](https://ufctime.com/fighters) and running a chronological Elo simulation.

## Data Pipeline

### 1. Scraping (`scraper.py`)

| Step | Detail |
|---|---|
| **Page discovery** | Fetches `https://ufctime.com/fighters`, parses the `"Page X of Y"` span to determine total pages (falls back to 69). |
| **URL collection** | Iterates all pages concurrently via `ThreadPoolExecutor(max_workers=20)`, extracting fighter profile links from `div.fighters-grid` and prefixing `https://ufctime.com/`. |
| **Fight history** | Each fighter page is scraped concurrently (20 threads) with a `random.uniform(0.1, 0.3)s` delay between requests. Parses `div.fighter-history__fight` blocks for result, opponent, event, date, method, and round/time. |
| **Output** | `ufc_fight_history_raw.csv` — schema: `fighter`, `fighter_url`, `result`, `opponent`, `event`, `date`, `method`, `round_time` |

### 2. Ranking (`ranker.py`)

#### Data Cleaning
- Drops exact duplicate rows
- Removes rows missing `opponent`, `result`, or `date`
- Extracts `YYYY-MM-DD` pattern from date strings (handles extra time components)
- Fills missing `method` / `round_time` with defaults

#### Elo Algorithm

Each fighter starts at **1000 Elo**. For every bout (processed chronologically by date):

```
expected_fighter = 1 / (1 + 10^((elo_opponent - elo_fighter) / 400))
expected_opponent = 1 - expected_fighter
```

Result → score mapping:

| Result | Fighter | Opponent |
|--------|---------|----------|
| W | 1.0 | 0.0 |
| L | 0.0 | 1.0 |
| D | 0.5 | 0.5 |
| NC | skipped | skipped |

Update rule:

```
new_elo_fighter = elo_fighter + K * (actual_fighter - expected_fighter)
```

Where **K = 100** (≈3× traditional chess Elo, making ratings more reactive to recent results).

#### Output
`ufc_final_elo_rankings.csv` — schema: `fighter`, `elo`, `rank`

### Top 5 (current)

| Rank | Fighter | Elo |
|------|---------|------|
| 1 | Islam Makhachev | 2182.45 |
| 2 | Jon Jones | 2122.87 |
| 3 | Georges St-Pierre | 2109.48 |
| 4 | Khabib Nurmagomedov | 2022.90 |
| 5 | Ilia Topuria | 1993.92 |

## Requirements

- Python 3.14+
- `requests`, `beautifulsoup4`, `pandas`, `numpy`, `lxml`

```bash
pip install requests beautifulsoup4 pandas numpy lxml
```

## Usage

```bash
# Step 1: scrape fight data
python scraper.py

# Step 2: compute Elo rankings
python ranker.py
```

## Notes

- Includes fighters' entire career history (not just UFC bouts), so regional/feeder organization fights affect ratings.
- `numpy` is imported but unused in `ranker.py` — a legacy dependency.
- CSV files are gitignored; regenerate them by running the scripts.
