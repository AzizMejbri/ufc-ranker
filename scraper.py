from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Set, List, Dict, Optional
import requests
from requests.models import Response
from bs4 import BeautifulSoup
import time
import random
import pandas as pd


HEADERS =  {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def get_total_pages() -> int:
    base_url: str = 'https://ufctime.com/fighters'
    resp: Response = requests.get(base_url, headers = HEADERS, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'lxml')
        
    page_span = soup.find('span', string=lambda text: (text is not None) and ('Page' in text) and ('of' in text))
        
    if page_span:
        text = page_span.text.strip() 
        total_pages = text.split('of')[-1].strip()
        return int(total_pages)
    else:
        print('\x1b[33mWARN: Could not find page count span. Falling back to 69.\x1b[m')
        return 69
            

def fetch_fighters_urls_page(page: int = 1) -> Set[str]:
    base_url: str = 'https://ufctime.com/fighters'
    fighter_urls: Set[str]= set()
    url: str = f'{base_url}?page={page}'
    resp: Response = requests.get(url, headers = HEADERS, timeout=10)
    resp.raise_for_status()


    soup: BeautifulSoup = BeautifulSoup(resp.text, 'html.parser')
    grid = soup.find_all('div', class_= 'fighters-grid')
    if not grid:
        print('\x1b[33mWARN: No fighter grid element found\x1b[m')

    fighters_soup: BeautifulSoup = BeautifulSoup(str(grid[0]), 'html.parser')
    links = fighters_soup.find_all('a', href=True)
    for link in links:
        full_url = f'https://ufctime.com/{link.get('href')}'
        fighter_urls.add(full_url)

    page += 1

    return fighter_urls


def fetch_full_fighters_urls() -> Set[str]:
    total_pages: int = get_total_pages()
    time.sleep(1)
    fighters_urls: Set[str] = set()
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_fighters_urls_page, page) for page in range(1, total_pages+1)}
        for future in as_completed(futures):
            fighters_urls.update(future.result())
    return fighters_urls

def parse_fighter_page(fighter_url: str) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes a single fighter's page and returns a list of fight records.
    """
    fights: List[Dict[str, Optional[str]]] = []
    
    try:
        resp = requests.get(fighter_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f'\x1b[31mERROR: Failed to fetch {fighter_url}: {e}\x1b[m')
        return fights

    soup = BeautifulSoup(resp.text, 'lxml')
    
    name_tag = soup.find('h1')
    fighter_name = name_tag.text.strip() if name_tag else "Unknown"
    
    history_list = soup.find('div', class_='fighter-history__list')
    if not history_list:
        return fights
    
    fight_divs = history_list.find_all('div', class_='fighter-history__fight')
    
    for fight_div in fight_divs:
        try:
            # Result 
            result_span = fight_div.find('span', class_='fighter-history__result')
            result = result_span.text.strip() if result_span else None
            # result will be "W", "L", "D", or "NC"
            
            # Opponent 
            opponent_link = fight_div.find('a', class_='fighter-history__opponent-name')
            opponent_name = opponent_link.text.strip() if opponent_link else None
            
            # Event & Date 
            event_span = fight_div.find('span', class_='fighter-history__event')
            event_text = event_span.text.strip() if event_span else ""
            
            # Split by " · " (space, middle dot, space)
            event_name = event_text
            event_date = None
            if ' · ' in event_text:
                parts = event_text.split(' · ')
                event_name = parts[0].strip()
                event_date = parts[1].strip() if len(parts) > 1 else None
            
            # Method
            method_span = fight_div.find('span', class_='fighter-history__method-text')
            method = method_span.text.strip() if method_span else None
            
            # Round & Time 
            round_span = fight_div.find('span', class_='fighter-history__round')
            round_time = round_span.text.strip() if round_span else None
            
            fights.append({
                'fighter': fighter_name,
                'fighter_url': fighter_url,
                'result': result,  # W, L, D, NC
                'opponent': opponent_name,
                'event': event_name,
                'date': event_date,
                'method': method,
                'round_time': round_time
            })
            
        except Exception as e:
            print(f'\x1b[33mWARN: Failed to parse a fight on {fighter_url}: {e}\x1b[m')
            continue
    
    time.sleep(random.uniform(0.1, 0.3))
    return fights


def scrape_all_fighter_histories(fighter_urls: List[str], max_workers: int = 20) -> pd.DataFrame:
    """
    Takes a list of fighter URLs and scrapes all their fight histories concurrently.
    Returns a pandas DataFrame with all fights.
    """
    all_fights: List[Dict] = []
    total_fighters = len(fighter_urls)
    
    print(f"LOG: Starting to scrape {total_fighters} fighters with {max_workers} threads...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(parse_fighter_page, url): url 
            for url in fighter_urls
        }
        
        completed = 0
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            completed += 1
            
            try:
                result = future.result()
                if result:
                    all_fights.extend(result)
                    print(f'\rLOG: [{completed}/{total_fighters}] Scraped {len(result)} fights from {url.split("/")[-1]}', end='')
                else:
                    print(f'\r\x1b[33mWARN: [{completed}/{total_fighters}] No fights found for {url.split("/")[-1]}\x1b[m', end='')
            except Exception as e:
                print(f'\n\x1b[31mERROR: Failed to process {url}: {e}\x1b[m')
    
    print("\n🏁 Scraping complete!")
    return pd.DataFrame(all_fights)

if __name__ == "__main__":
    # 1. Get all fighter URLs
    print("🔍 Gathering fighter URLs...")
    urls = fetch_full_fighters_urls()
    urls_list = list(urls)
    print(f"📊 Found {len(urls_list)} fighters.")
    
    # 2. Scrape all fight histories
    df = scrape_all_fighter_histories(urls_list, max_workers=20)
    
    # 3. Save raw data to CSV
    df.to_csv('ufc_fight_history_raw.csv', index=False)
    print(f"💾 Saved {len(df)} fight records to 'ufc_fight_history_raw.csv'")
