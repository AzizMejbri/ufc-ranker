import pandas as pd
import numpy as np
from typing import Dict

K: float = 100

# K-factor multipliers by finish type.
# Dominant finishes (KO/TKO, Submission) earn a 30% Elo bonus.
# Decisions earn a 15% reduction to reflect closer, less dominant wins.
METHOD_K_MULTIPLIER: Dict[str, float] = {
    'KO/TKO': 1.3,
    'SUB':    1.3,
    'DEC':    0.85,
    'OTHER':  1.0,  # NC, DQ, Draw – treated neutrally (most skipped anyway)
}


def categorize_method(method) -> str:
    """Classify a raw method string into one of: KO/TKO, SUB, DEC, OTHER.

    The raw CSV contains 1 200+ unique method strings due to inconsistent
    scraping.  We detect finish type by scanning for keywords (case-insensitive)
    in the following priority order:
      1. Submission  – 'sub', 'submission', 'choke', 'armbar', 'heel hook',
                       'kimura', 'guillotine', 'triangle', 'kneebar',
                       'lock', 'crank'
      2. KO / TKO   – 'ko', 'tko', 'knockout', 'technical ko',
                       'technical knockout'
      3. Decision   – 'dec', 'decision', 'unanimous', 'majority', 'split',
                       'u-dec', 'm-dec', 's-dec'
      4. OTHER      – everything else (NC, DQ, Draw, numeric artefacts, …)
    """
    if pd.isna(method):
        return 'OTHER'
    m = str(method).upper()

    SUB_KW = [
        'SUB', 'SUBMISSION', 'CHOKE', 'ARMBAR', 'HEEL HOOK',
        'KIMURA', 'GUILLOTINE', 'TRIANGLE', 'KNEEBAR', 'LOCK', 'CRANK',
    ]
    KO_KW = ['KO', 'TKO', 'KNOCKOUT', 'TECHNICAL KO', 'TECHNICAL KNOCKOUT']
    DEC_KW = ['DEC', 'DECISION', 'UNANIMOUS', 'MAJORITY', 'SPLIT',
               'U-DEC', 'M-DEC', 'S-DEC']

    is_sub = any(kw in m for kw in SUB_KW)
    is_ko  = any(kw in m for kw in KO_KW)
    is_dec = any(kw in m for kw in DEC_KW)

    # Priority: SUB first (so "Technical Submission" isn't caught by KO_KW)
    if is_sub and not is_ko:
        return 'SUB'
    if is_ko and not is_dec:
        return 'KO/TKO'
    if is_dec and not is_ko and not is_sub:
        return 'DEC'
    # Mixed signals – dominant finish takes precedence over decision label
    if is_ko:
        return 'KO/TKO'
    if is_sub:
        return 'SUB'
    return 'OTHER'

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    initial_len: int = len(df)
    df = df.drop_duplicates()
    print(f"LOG: Dropped {initial_len - len(df)} exact duplicate rows.")

    initial_len = len(df)
    df = df.dropna(subset=['opponent'])
    print(f"LOG: Dropped {initial_len - len(df)} rows missing an 'opponent'.")

    initial_len = len(df)
    df = df.dropna(subset=['result'])
    print(f"LOG: Dropped {initial_len - len(df)} rows missing an 'result'.")


    initial_len = len(df)
    df = df.dropna(subset=['date'])
    print(f"LOG: Dropped {initial_len - len(df)} rows missing an 'date'.")

    initial_len = len(df)
    # ---- FIX FOR DATE PARSING ----
    # 1. Convert to string and strip whitespace
    df['date'] = df['date'].astype(str).str.strip()
    # 2. Extract only the YYYY-MM-DD pattern (removes extra time components)
    df['date'] = df['date'].str.extract(r'(\d{4}-\d{2}-\d{2})')[0]
    # 3. Convert to datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    # 4. Drop any rows where date became NaT (just in case)
    df = df.dropna(subset=['date'])
    # -----------------------------
    print(f"LOG: Dropped {initial_len - len(df)} rows with non-normalized 'date' fields.")

    df['method'] = df['method'].fillna('Unknown')
    df['round_time'] = df['round_time'].fillna('R5')

    return df


def expected_score(rating_a: float, rating_b: float) -> float:

    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

if __name__ == '__main__':
    print("LOG: Loading the .csv file ...")
    df: pd.DataFrame = pd.read_csv('ufc_fight_history_raw.csv')

    print("LOG: Cleaning Data ...")
    df = clean_data(df)
    df = df.sort_values('date', ascending=True)
    scores: Dict[str, float] = {}
    for fight in df.itertuples():
        fighter: str = fight.fighter
        opponent: str = fight.opponent
        result: str = fight.result
        if not fighter in scores: 
            scores[fighter] = 1000.0
        if not opponent in scores:
            scores[opponent] = 1000.0

        elo_fighter = scores[fighter]
        elo_opponent = scores[opponent]
        expected_fighter = expected_score(elo_fighter, elo_opponent)
        expected_opponent = 1 - expected_fighter

        if result == 'W':
            actual_fighter, actual_opponent = 1.0, 0.0
        elif result == 'L':
            actual_fighter, actual_opponent = 0.0, 1.0
        elif result == 'D':
            actual_fighter, actual_opponent = 0.5, 0.5
        else:
            # Skip draws/NCs for simplicity
            continue
        
        # Determine K-factor multiplier from fight method
        method_category: str = categorize_method(fight.method)
        k_multiplier: float = METHOD_K_MULTIPLIER[method_category]
        effective_k: float = K * k_multiplier

        # Update ratings
        new_elo_fighter = elo_fighter + effective_k * (actual_fighter - expected_fighter)
        new_elo_opponent = elo_opponent + effective_k * (actual_opponent - expected_opponent)

        scores[fighter] = new_elo_fighter
        scores[opponent] = new_elo_opponent
        
         

    rankings = pd.DataFrame(list(scores.items()), columns=['fighter', 'elo'])
    rankings = rankings.sort_values('elo', ascending=False).reset_index(drop=True)
    rankings['rank'] = rankings.index + 1
    
    print("\n🏆 Top 10 Fighters:")
    print(rankings.head(10).to_string(index=False))
    
    # Save final rankings
    rankings.to_csv('ufc_final_elo_rankings.csv', index=False)
    print("LOG: Final rankings saved to 'ufc_final_elo_rankings.csv'")
