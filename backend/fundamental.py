import requests
import time

# --- COINGECKO API (FREE TIER) ---
BASE_URL = "https://api.coingecko.com/api/v3"

def get_coin_id(symbol):
    symbol = symbol.replace("/USDT", "").lower()
    try:
        url = f"{BASE_URL}/search?query={symbol}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if 'coins' in data and len(data['coins']) > 0:
            for coin in data['coins']:
                if coin['symbol'].lower() == symbol:
                    return coin['id']
            return data['coins'][0]['id']
        return None
    except Exception as e:
        return None

def get_fundamental_data(symbol):
    """
    Menarik data fundamental 'Institutional Grade'.
    Gaya bahasa: Formal & Data-Driven (Tanpa Emojis).
    """
    coin_id = get_coin_id(symbol)
    if not coin_id:
        return "Data Fundamental tidak ditemukan (Simbol tidak dikenal di CoinGecko)."

    try:
        url = f"{BASE_URL}/coins/{coin_id}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=true&sparkline=false"
        resp = requests.get(url, timeout=15)
        
        if resp.status_code == 429:
            return "Rate Limit CoinGecko Tercapai. Tunggu sebentar..."
            
        data = resp.json()
        
        # 1. Identitas & Rank
        name = data.get('name', symbol)
        rank = data.get('market_cap_rank', 9999)
        if rank is None: rank = 9999
        
        # 2. Developer Data
        dev_data = data.get('developer_data', {})
        commits = dev_data.get('commit_count_4_weeks', 0)
        
        # --- LOGIKA MATURITY (FORMAL) ---
        if rank <= 100:
            if commits > 0:
                dev_status = f"ACTIVE ({commits} commits)"
            else:
                dev_status = "MATURE / STABLE (Core code established)"
        else:
            if commits > 10:
                dev_status = f"BUILDING ({commits} commits)"
            elif commits > 0:
                dev_status = f"SLOW DEVELOPMENT ({commits} commits)"
            else:
                dev_status = "INACTIVE / GHOST (High Risk)"

        # 3. Market Data & Likuiditas
        market_data = data.get('market_data', {})
        mcap = market_data.get('market_cap', {}).get('usd', 0)
        vol_24h = market_data.get('total_volume', {}).get('usd', 0)
        
        liquidity_ratio = (vol_24h / mcap) if mcap > 0 else 0
        liq_status = "LIQUID" if liquidity_ratio > 0.03 else "ILLIQUID (Hard to Exit)"
        
        # 4. Supply Info
        circ_supply = market_data.get('circulating_supply', 0)
        max_supply = market_data.get('max_supply', 0)
        supply_info = "Unlimited"
        if max_supply and max_supply > 0:
            percent_supply = (circ_supply / max_supply) * 100
            supply_info = f"{percent_supply:.1f}% Unlocked"
        
        # Output Teks Formal untuk AI
        fundamental_text = f"""
        [DATA FUNDAMENTAL {name.upper()}]:
        - Market Rank: #{rank}
        - Developer Status: {dev_status}
        - Liquidity Ratio: {liquidity_ratio:.4f} ({liq_status})
        - Supply Status: {supply_info}
        - All Time High: ${market_data.get('ath', {}).get('usd', 0)} (Drawdown: {market_data.get('ath_change_percentage', {}).get('usd', 0):.2f}%)
        """
        
        if rank > 200:
            fundamental_text += "\nWARNING: Low Cap Asset. High Volatility Risk."
            
        return fundamental_text

    except Exception as e:
        return f"Error data fundamental: {str(e)}"