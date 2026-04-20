import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
import json

# 從環境變數讀取金鑰 (GitHub Secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")


def send_telegram_msg(message):
    """發送 Telegram 訊息"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("✅ Telegram 訊息發送成功")
    else:
        print(f"❌ Telegram 發送失敗: {response.text}")


def get_us_market_sentiment():
    """1. 國際半導體情緒：TSM ADR 溢價與 SOX 指數"""
    try:
        tsm = yf.Ticker("TSM")
        soxx = yf.Ticker("SOXX")

        # 抓取最近交易日收盤價
        tsm_hist = tsm.history(period="2d")
        tsm_price = round(tsm_hist['Close'].iloc[-1], 2)
        tsm_prev = round(tsm_hist['Close'].iloc[-2], 2) if len(tsm_hist) >= 2 else tsm_price
        tsm_change_pct = round((tsm_price - tsm_prev) / tsm_prev * 100, 2)

        soxx_hist = soxx.history(period="2d")
        soxx_price = round(soxx_hist['Close'].iloc[-1], 2)
        soxx_prev = round(soxx_hist['Close'].iloc[-2], 2) if len(soxx_hist) >= 2 else soxx_price
        soxx_change_pct = round((soxx_price - soxx_prev) / soxx_prev * 100, 2)

        return {
            "TSM_ADR_Price": tsm_price,
            "TSM_ADR_Change": f"{tsm_change_pct:+.2f}%",
            "SOXX_Price": soxx_price,
            "SOXX_Change": f"{soxx_change_pct:+.2f}%"
        }
    except Exception as e:
        print(f"⚠️ 美股資料抓取失敗: {e}")
        return {
            "TSM_ADR_Price": "N/A",
            "TSM_ADR_Change": "N/A",
            "SOXX_Price": "N/A",
            "SOXX_Change": "N/A"
        }


def get_vix_index():
    """2. 恐慌指數 VIX"""
    try:
        vix = yf.Ticker("^VIX")
        vix_hist = vix.history(period="1d")
        vix_value = round(vix_hist['Close'].iloc[-1], 2)

        # VIX 情緒判斷
        if vix_value < 15:
            vix_signal = "😌 低恐慌（偏多頭）"
        elif vix_value < 25:
            vix_signal = "😐 正常波動"
        elif vix_value < 35:
            vix_signal = "😨 恐慌升溫（警戒）"
        else:
            vix_signal = "🚨 極度恐慌（可能反彈）"

        return {"VIX": vix_value, "VIX_Signal": vix_signal}
    except Exception as e:
        print(f"⚠️ VIX 資料抓取失敗: {e}")
        return {"VIX": "N/A", "VIX_Signal": "N/A"}


def get_twse_chips():
    """3. 籌碼面情緒：三大法人與融資比 (以 2330 台積電為例)"""
    from datetime import timedelta
    headers = {"User-Agent": "Mozilla/5.0"}

    # 往前最多查 5 個日曆日，找到有資料的最近交易日
    for days_back in range(0, 6):
        check_date = datetime.now() - timedelta(days=days_back)
        date_str = check_date.strftime("%Y%m%d")
        try:
            url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()

            if not data.get("data"):
                print(f"⚠️ {date_str} 無籌碼資料，往前找...")
                continue

            tsmc_row = None
            for row in data["data"]:
                if "2330" in row[0]:
                    tsmc_row = row
                    break

            if tsmc_row:
                foreign_net = tsmc_row[4].replace(",", "")  # 外資買賣超
                trust_net = tsmc_row[7].replace(",", "")    # 投信買賣超
                dealer_net = tsmc_row[10].replace(",", "")  # 自營商買賣超
                total_net = tsmc_row[11].replace(",", "")   # 三大法人合計
                label = check_date.strftime("%m/%d")
                print(f"✅ 找到籌碼資料：{date_str}")
                return {
                    "Target": f"2330 台積電 ({label})",
                    "Foreign_Net": f"{int(foreign_net):+,} 張",
                    "Trust_Net": f"{int(trust_net):+,} 張",
                    "Dealer_Net": f"{int(dealer_net):+,} 張",
                    "Total_Net": f"{int(total_net):+,} 張",
                }
        except Exception as e:
            print(f"⚠️ 籌碼資料抓取失敗 ({date_str}): {e}")
            continue

    # 全部失敗時回傳預設值
    return {
        "Target": "2330 台積電",
        "Foreign_Net": "N/A",
        "Trust_Net": "N/A",
        "Dealer_Net": "N/A",
        "Total_Net": "N/A",
    }


def get_etf_premium():
    """4. ETF 溢價率：元大台灣50 (0050) 折溢價"""
    try:
        url = "https://www.yuantaetfs.com/api/StkRatio"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            etf_data = resp.json()
            # 解析 0050 的折溢價資料（依實際 API 結構調整）
            for item in etf_data:
                if "0050" in str(item):
                    return {"ETF_0050_Premium": str(item)}
        return {"ETF_0050_Premium": "N/A"}
    except Exception as e:
        print(f"⚠️ ETF 資料抓取失敗: {e}")
        return {"ETF_0050_Premium": "N/A"}


def calculate_sentiment_score(us_data, vix_data, chips_data):
    """5. 綜合情緒評分 (0~100 分)"""
    score = 50  # 基準分

    # VIX 影響 (-20 ~ +20)
    try:
        vix_val = float(vix_data.get("VIX", 20))
        if vix_val < 15:
            score += 15
        elif vix_val < 20:
            score += 5
        elif vix_val > 30:
            score -= 15
        elif vix_val > 25:
            score -= 8
    except:
        pass

    # TSM ADR 漲跌影響 (-15 ~ +15)
    try:
        tsm_chg = float(us_data.get("TSM_ADR_Change", "0%").replace("%", "").replace("+", ""))
        if tsm_chg > 2:
            score += 15
        elif tsm_chg > 0:
            score += 5
        elif tsm_chg < -2:
            score -= 15
        elif tsm_chg < 0:
            score -= 5
    except:
        pass

    score = max(0, min(100, score))

    if score >= 70:
        signal = "🟢 偏多頭，情緒樂觀"
    elif score >= 50:
        signal = "🟡 中性偏多，觀望為主"
    elif score >= 30:
        signal = "🟠 中性偏空，謹慎操作"
    else:
        signal = "🔴 空頭情緒，注意風險"

    return {"Score": score, "Signal": signal}


def run_radar():
    print(f"🚀 啟動多維度情緒雷達 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 抓取各維度資料
    us_data = get_us_market_sentiment()
    vix_data = get_vix_index()
    chips_data = get_twse_chips()
    etf_data = get_etf_premium()
    sentiment = calculate_sentiment_score(us_data, vix_data, chips_data)

    # 組合 Telegram 訊息
    msg = (
        f"🚀 *多維度情緒雷達戰報*\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*28}\n\n"

        f"🌐 *美股映射*\n"
        f"• TSM ADR：${us_data['TSM_ADR_Price']}  `{us_data['TSM_ADR_Change']}`\n"
        f"• 費半SOXX：${us_data['SOXX_Price']}  `{us_data['SOXX_Change']}`\n\n"

        f"😨 *恐慌指數 VIX*\n"
        f"• VIX：{vix_data['VIX']}  →  {vix_data['VIX_Signal']}\n\n"

        f"💰 *籌碼動向 ({chips_data['Target']})*\n"
        f"• 外資：{chips_data['Foreign_Net']}\n"
        f"• 投信：{chips_data['Trust_Net']}\n"
        f"• 自營：{chips_data['Dealer_Net']}\n"
        f"• 合計：{chips_data['Total_Net']}\n\n"

        f"📊 *綜合情緒評分*\n"
        f"• 分數：{sentiment['Score']} / 100\n"
        f"• 訊號：{sentiment['Signal']}\n\n"

        f"💾 資料已備份至 GitHub Actions"
    )

    print(msg)

    # 發送 Telegram 通知
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        send_telegram_msg(msg)
    else:
        print("⚠️ 未設定 Telegram 金鑰，跳過發送")

    # 儲存 JSON 備份
    result = {
        "timestamp": datetime.now().isoformat(),
        "us_market": us_data,
        "vix": vix_data,
        "chips": chips_data,
        "etf": etf_data,
        "sentiment": sentiment
    }

    output_path = f"data/sentiment_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    print(f"✅ 資料已儲存：{output_path}")


if __name__ == "__main__":
    run_radar()
