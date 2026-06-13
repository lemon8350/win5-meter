import requests
from bs4 import BeautifulSoup
import re
import os
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_html(url, timeout=15):
    """
    URLをフェッチする汎用ヘルパー。
    環境変数 SCRAPER_API_KEY が設定されている場合は、ScraperAPIを経由して取得する。
    """
    api_key = os.environ.get("SCRAPER_API_KEY")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    if api_key:
        # ScraperAPIを経由
        target_url = f"http://api.scraperapi.com/?api_key={api_key}&url={urllib.parse.quote(url)}"
        res = requests.get(target_url, timeout=timeout)
    else:
        # ローカルからの直接アクセス
        res = requests.get(url, headers=headers, timeout=timeout)
        
    return res

def get_race_ids(date_str):
    """指定した日付のレースID一覧を取得する"""
    url = f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date_str}"
    try:
        res = fetch_html(url)
        res.encoding = 'utf-8'
        matches = re.findall(r'race_id=(\d{12})', res.text)
        return sorted(list(set(matches)))
    except Exception as e:
        print(f"レース一覧取得エラー（{date_str}）: {e}")
        return []

def fetch_single_race_1st_place(race_id):
    """1レースの結果ページをスクレイピングし、1着馬の[レース番号, 人気順]を返す"""
    url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    try:
        res = fetch_html(url)
        res.encoding = 'euc-jp'
        
        soup = BeautifulSoup(res.text, 'html.parser')
        table = soup.find('table', class_='RaceTable01')
        if not table:
            return None
            
        rows = table.find_all('tr')[1:] # Skip header
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 10:
                rank = cols[0].get_text(strip=True)
                if rank.startswith('1'):
                    pop_str = cols[9].get_text(strip=True)
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

def fetch_live_odds(race_id):
    """
    指定レースの馬番、枠番、馬名、騎手、最新オッズ、人気順を取得する
    """
    
    # 1. 出馬表から基本情報（枠、馬番、馬名、騎手）を取得
    shutuba_url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    try:
        res_s = fetch_html(shutuba_url)
        res_s.encoding = 'euc-jp'
        soup_s = BeautifulSoup(res_s.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching shutuba for {race_id}: {e}")
        return []

    horses_info = {}
    table_s = soup_s.find('table', class_='Shutuba_Table')
    if table_s:
        for row in table_s.find_all('tr', class_='HorseList'):
            waku_td = row.find('td', class_=re.compile('Waku'))
            umaban_td = row.find('td', class_=re.compile('Umaban'))
            horse_span = row.find('span', class_='HorseName')
            jockey_td = row.find('td', class_='Jockey')
            
            if umaban_td and horse_span:
                umaban = umaban_td.get_text(strip=True)
                waku = waku_td.get_text(strip=True) if waku_td else ""
                horse_name = horse_span.get_text(strip=True)
                # 騎手名は改行などがあるため、テキストのみ抽出して整形
                jockey = jockey_td.get_text(strip=True).split(' ')[0] if jockey_td else ""
                
                horses_info[umaban] = {
                    "waku": waku,
                    "umaban": umaban,
                    "horse_name": horse_name,
                    "jockey": jockey,
                    "odds": "---",
                    "popularity": 999
                }

    # 2. オッズページから最新オッズと人気を取得
    odds_url = f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}"
    try:
        res_o = fetch_html(odds_url)
        res_o.encoding = 'euc-jp'
        soup_o = BeautifulSoup(res_o.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching odds for {race_id}: {e}")
        return list(horses_info.values())

    table_o = soup_o.find('table', class_='RaceOdds_HorseList_Table')
    if table_o:
        for row in table_o.find_all('tr'):
            tds = row.find_all('td')
            if len(tds) < 5:
                continue
            
            umaban_td = row.find('td', class_=re.compile('W31')) # 馬番のtdはW31というクラスを持つことが多い
            if not umaban_td:
                # クラス名がない場合もあるためテキストで推測
                # [枠, 馬番, 印, 選択, 馬名, オッズ]
                umaban_td = tds[1]
                
            umaban = umaban_td.get_text(strip=True)
            odds_td = row.find('td', class_='Popular')
            if odds_td and umaban in horses_info:
                odds_str = odds_td.get_text(strip=True)
                horses_info[umaban]["odds"] = odds_str
                # オッズが取得できたら人気順を一旦保持（ソート用）
                try:
                    if odds_str != '---.-' and odds_str != '':
                        horses_info[umaban]["odds_val"] = float(odds_str)
                except:
                    pass

    # リスト化
    result_list = list(horses_info.values())
    
    # オッズ値が存在するものだけソートして人気順を付与
    valid_horses = [h for h in result_list if "odds_val" in h]
    valid_horses.sort(key=lambda x: x["odds_val"])
    
    for i, h in enumerate(valid_horses):
        h["popularity"] = i + 1
        
    # オッズ値がない馬は人気999のまま
    
    # 全体を人気順 -> 馬番順でソート
    result_list.sort(key=lambda x: (x["popularity"], int(x["umaban"]) if x["umaban"].isdigit() else 999))
    
    return result_list
