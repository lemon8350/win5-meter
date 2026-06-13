import requests
from bs4 import BeautifulSoup
import re
import os
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

def get_win5_race_ids(date_str):
    """指定した日付のWIN5対象レースを取得する（公式WIN5ページから抽出）"""
    url = f"https://race.netkeiba.com/top/win5.html?kaisai_date={date_str}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'euc-jp'
        
        # HTML内から race_id=xxxxxxxxxxxx を抽出
        matches = re.findall(r'race_id=(\d{12})', res.text)
        
        # 順番を保持したまま重複を削除して5レース分を取得
        unique_races = []
        for rid in matches:
            if rid not in unique_races:
                unique_races.append(rid)
                
        return unique_races[:5]
    except Exception as e:
        print(f"WIN5レース取得エラー（{date_str}）: {e}")
        return []

def fetch_single_race_1st_place(race_id):
    """1レースの結果ページをスクレイピングし、1着馬の[レース番号, 人気順]を返す"""
    url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'euc-jp'
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 着順1の行を探す
        result_table = soup.find('table', class_='RaceNFriendsTable')
        if not result_table:
            return None
            
        for row in result_table.find_all('tr')[1:]: # ヘッダスキップ
            cols = row.find_all('td')
            if len(cols) > 10:
                rank = cols[0].get_text(strip=True)
                if rank == '1':
                    pop = cols[9].get_text(strip=True)
                    try:
                        return [race_id, int(pop)]
                    except ValueError:
                        return None
        return None
    except Exception as e:
        print(f"1着データ取得エラー（{race_id}）: {e}")
        return None

def fetch_1st_place_popularities(race_ids):
    """複数レースの1着人気順を並列で取得する"""
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_race = {executor.submit(fetch_single_race_1st_place, rid): rid for rid in race_ids}
        for future in as_completed(future_to_race):
            data = future.result()
            if data:
                results[data[0]] = data[1]
    
    # 元のID順にソートしてリスト化
    sorted_pops = [results[rid] for rid in race_ids if rid in results]
    return sorted_pops

def fetch_live_odds(race_id):
    """
    指定レースの馬番、枠番、馬名、騎手、最新オッズ、人気順を取得する
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. 出馬表から基本情報（枠、馬番、馬名、騎手）を取得
    shutuba_url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    try:
        res_s = requests.get(shutuba_url, headers=headers, timeout=5)
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
        res_o = requests.get(odds_url, headers=headers, timeout=5)
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
