import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
import json

TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")


def send_telegram_msg(message):
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)


def get_us_market_sentiment():
    try:
        tsm = yf.Ticker("TSM")
        soxx = yf.Ticker("SOXX")
        tsm_hist = tsm.history(period="2d")
        tsm_price = round(tsm_hist['Close'].iloc[-1], 2)
        tsm_prev = round(tsm_hist['Close'].iloc[-2], 2) if len(tsm_hist) >= 2 else tsm_price
        tsm_change_pct = round((tsm_price - tsm_prev) / tsm_prev * 100, 2)
        soxx_hist = soxx.history(period="2d")
        soxx_price = round(soxx_hist['Close'].iloc[-1], 2)
        soxx_prev = round(soxx_hist['Close'].iloc[-2], 2) if len(soxx_hist) >= 2 else soxx_price
        soxx_change_pct = round((soxx_price - soxx_prev) / soxx_prev * 100, 2)
        return {"TSM_ADR_Price": tsm_price, "TSM_ADR_Change": f"{tsm_change_pct:+.2f}%", "SOXX_Price": soxx_price, "SOXX_Change": f"{soxx_change_pct:+.2f}%"}
    except Exception as e:
        return {"TSM_ADR_Price": "N/A", "TSM_ADR_Change": "N/A", "SOXX_Price": "N/A", "SOXX_Change": "N/A"}


def get_vix_index():
    try:
        vix = yf.Ticker("^VIX")
        vix_hist = vix.history(period="1d")
        vix_value = round(vix_hist['Close'].iloc[-1], 2)
        if vix_value < 15: vix_signal = "Low Fear"
        elif vix_value < 25: vix_signal = "Normal"
        elif vix_value < 35: vix_signal = "Elevated Fear"
        else: vix_signal = "Extreme Fear"
        return {"VIX": vix_value, "VIX_Signal": vix_signal}
    except Exception:
        return {"VIX": "N/A", "VIX_Signal": "N/A"}


def get_twse_chips():
    try:
        date_str = datetime.now().strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86response=json&date={date_str}&selectType=ALLBUT0999"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        tsmc_row = None
        if data.get("data"):
            for row in data["data"]:
                if "2330" in row[0]: tsmc_row = row; break
        if tsmc_row:
            fn = int(tsmc_row[4].replace(",", ""))
            tn = int(tsmc_row[7].replace(",", ""))
            dn = int(tsmc_row[10].replace(",", ""))
            tot = int(tsmc_row[11].replace(",", ""))
            return {"Target": "2330", "Foreign_Net": f"{fn:+s}}", "Trust_Net": f"{tn:++}", "Dealer_Net": f"{dn:++}", "Total_Net": f"{tot:+s}"}
    except Exception as e: print(e)
    return {"Target": "2330", "Foreign_Net": "N/A", "Trust_Net": "N/A", "Dealer_Net": "N/A", "Total_Net": "N/A"}


def get_etf_premium():
    try:
        resp = requests.get("https://www.yuantaetfs.com/api/StkRatio", timeout=10)
        if resp.status_code == 200:
            for item in resp.json():
                if "0050" in str(item): return {"ETF_0050_Premium": str(item)}
    except: pass
    return {"ETF_0050_Premium": "N/A"}


def calculate_sentiment_score(us_data, vix_data, chips_data):
    score = 50
    try:
        v = float(vix_data.get("VIX", 20))
        if v < 15: score += 15
        elif v < 20: score += 5
        elif v > 30: score -= 15
        elif v > 25: score -= 8
    except: pass
    try:
        c = float(us_data.get("TSM_ADR_Change", "0%").replace("%", "").replace("+", ""))
        if c > 2: score += 15
        elif c > 0: score += 5
        elif c < -2: score -= 15
        elif c < 0: score -= 5
    except: pass
    score = max(0, min(100, score))
    if score >= 70: sig = "Bullish"
    elif score >= 50: sig = "Neutral-Bull"
    elif score >= 30: sig = "Neutral-Bear"
    else: sig = "Bearish"
    return {"Score": score, "Signal": sig}


def run_radar():
    print(f"Starting Sentiment Radar {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    us_data = get_us_market_sentiment()
    vix_data = get_vix_index()
    chips_data = get_twse_chips()
    etf_data = get_etf_premium()
    sentiment = calculate_sentiment_score(us_data, vix_data, chips_data)
    msg = (
        f"*Sentiment Radar Report*\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"*US Market*\n"
        f"TSM ADR: ${us_data['TSM_ADR_Price']} ({us_data['TSM_ADR_Change']})\n"
        f"SOXX: ${us_data['SOXX_Price']} ({us_data['SOXX_Change']})\n\n"
        f"*VIX*\nVIX: {vix_data['VIX']} -> {vix_data['VIX_Signal']}\n\n"
        f"*Chips 2330*\n"
        f"Foreign: {chips_data['Foreign_Net']}\n"
        f"Trust: {chips_data['Trust_Net']}\n"
        f"Dealer: {chips_data['Dealer_Net']}\n"
        f"Total: {chips_data['Total_Net']}\n\n"
        f"*Sentiment Score*\nScore: {sentiment['Score']}/100\nSignal: {sentiment['Signal']}"
    )
    print(msg)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        send_telegram_msg(msg)
    result = {
        "timestamp": datetime.now().isoformat(),
        "us_market": us_data,
        "vix": vix_data,
        "chips": chips_data,
        "etf": etf_data,
        "sentiment": sentiment
    }
    path = f"data/sentiment_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved: {path}")


if __name__ == "__main__":
    run_radar()
