import time
from scraper import fetch_1st_place_popularities

# 簡易キャッシュ: { "YYYYMMDD_upToRace": { "sum": X, "count": Y, "timestamp": 12345 } }
CACHE = {}
CACHE_TTL_SEC = 300  # 5分間キャッシュする

def get_popularity_sum(date_str, up_to_race=None):
    """
    指定日の(up_to_raceまでの)1着馬人気順の和を計算する
    キャッシュがあればキャッシュを返す
    """
    cache_key = f"{date_str}_{up_to_race}"
    now = time.time()
    
    # キャッシュチェック
    if cache_key in CACHE:
        cached_data = CACHE[cache_key]
        if now - cached_data["timestamp"] < CACHE_TTL_SEC:
            return cached_data
            
    # キャッシュ切れまたは新規ならスクレイピング
    results = fetch_1st_place_popularities(date_str, up_to_race)
    
    total_pop = sum(r["popularity"] for r in results)
    
    data = {
        "sum": total_pop,
        "count": len(results),
        "timestamp": now,
        "details": results
    }
    
    # 土曜日のデータなどでレース数が多い（完了している）場合はキャッシュ時間を延ばす工夫も可能
    CACHE[cache_key] = data
    return data
