import requests
from datetime import datetime

# Your Telegram Bot details
BOT_TOKEN="8654878137:AAEG-CQnAfukKjKz1PxiNQvRw1Am07Hf-vA"
CHAT_ID="6989302939"


# def send_telegram_alert(symbol, current_price, target_price, buy_type,
#                         entry_time=None, exit_time=None):

#     # Default entry time = current time
#     if entry_time is None:
#         entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#     # Default exit time if not provided
#     if exit_time is None:
#         exit_time = "Not Exited"

#     # Telegram message format
#     message = f"""
# 📈 *Trade Alert*

# 🔹 *Symbol:* {symbol}
# 💰 *Current Price:* {current_price}
# 🎯 *Target Price:* {target_price}
# 🛒 *Type of Buy:* {buy_type}

# ⏰ *Entry Time:* {entry_time}
# ⌛ *Exit Time:* {exit_time}
# """

#     url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

#     payload = {
#         "chat_id": CHAT_ID,
#         "text": message,
#         "parse_mode": "Markdown"
#     }

#     try:
#         response = requests.post(url, data=payload)

#         if response.status_code == 200:
#             print("Telegram alert sent successfully")
#         else:
#             print(f"Failed: {response.text}")

#     except Exception as e:
#         print(f"Error: {e}")


# # Example Usage
# send_telegram_alert(
#     symbol="BTCUSDT",
#     current_price=65000,
#     target_price=67000,
#     buy_type="Swing Buy",
#     exit_time="2026-05-15 18:30:00"
# )

def send_telegram_alert(
    symbol,
    signal,
    entry_price,
    stop_loss,
    target_price,
    logic,
    buy_type,
    entry_time=None,
    exit_time=None
):

    # Default entry time
    if entry_time is None:
        entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Default exit time
    if exit_time is None:
        exit_time = "Open Trade"

    # Telegram message
    message = f"""
📈 *Trade Alert*
🔹 *logic:* `{logic}`
🔹 *Symbol:* `{symbol}`
📊 *Signal:* *{signal}*
🛒 *Trade Type:* {buy_type}

💰 *Entry Price:* `{entry_price}`
🛑 *Stop Loss:* `{stop_loss}`
🎯 *Target:* `{target_price}`

⏰ *Entry Time:* `{entry_time}`
⌛ *Exit Time:* `{exit_time}`
"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        print("Sending telegram message ...")
        response = requests.post(url, data=payload)

        if response.status_code == 200:
            print("✅ Telegram alert sent successfully")
        else:
            print(f"❌ Failed: {response.text}")

    except Exception as e:
        print(f"❌ Error: {e}")
    
