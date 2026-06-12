import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_race_ids(date_str):
    """指定した日付のレースID一覧を取得する"""
    url = f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date_str}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'utf-8'
        matches = re.findall(r'race_id=(\d{12})', res.text)
        return sorted(list(set(matches)))
    except Exception as e:
        print(f"レース一覧取得エラー（{date_str}）: {e}")
        return []

def fetch_single_race_1st_place(race_id):
    """1レースの結果ページをスクレイピングし、1着馬の[レース番号, 人気順]を返す"""
    url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'euc-jp'
        dfs = pd.read_html(res.text)
        if not dfs:
            return None
        df = dfs[0]
        
        # MultiIndex対策
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[-1] for col in df.columns]
            
        # 1着を探す
        for _, row in df.iterrows():
            cols = df.columns
            
            def safe_get(key_candidates):
                for k in key_candidates:
                    if k in cols:
                        return str(row[k])
                return ""
                
            rank = safe_get(["着順", "着", "順位", "着 順"]).strip()
            # 「1」または「1(降)」など
            if rank.startswith("1"):
                pop_str = safe_get(["人気", "人気順", "人 気"]).strip()
                if pop_str.isdigit() or pop_str.replace('.', '', 1).isdigit():
                    return {
                        "race_id": race_id,
                        "race_num": int(race_id[-2:]),
                        "course": race_id[4:6],
                        "popularity": int(float(pop_str))
                    }
        return None
    except Exception as e:
        print(f"Exception in fetch_single_race_1st_place: {e}")
        return None

def fetch_1st_place_popularities(date_str, up_to_race=None):
    """指定日の全レースの1着馬の人気順を取得する。並列処理で高速化。"""
    race_ids = get_race_ids(date_str)
    if not race_ids:
        return []

    results = []
    
    # フィルタリング (指定レース以下のみ)
    target_race_ids = []
    for r_id in race_ids:
        r_num = int(r_id[-2:])
        if up_to_race is None or r_num <= up_to_race:
            target_race_ids.append(r_id)

    # 並列でスクレイピング
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_race = {executor.submit(fetch_single_race_1st_place, r_id): r_id for r_id in target_race_ids}
        for future in as_completed(future_to_race):
            res = future.result()
            if res:
                results.append(res)
                
    # ソートして返す
    results.sort(key=lambda x: (x["course"], x["race_num"]))
    return results
