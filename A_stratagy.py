from dataclasses import dataclass
import pandas as pd
import os
from enum import Enum
import redis
import sys
import json
from datetime import datetime, timedelta
import time

#########################Redis Connection###################
try:
    redisObject = redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True
    )

    # Test the connection
    redisObject.ping()

except redis.exceptions.RedisError as e:
    print(f"Failed to connect to Redis: {e}")
    sys.exit(1)

print("Connected to Redis successfully.")

##########################Variables########################
token_file = "NIFTY50_Tokens.csv"

levels = {}


@dataclass
class PDLevels:
    symbol: str
    trading_symbol: str
    token: str
    lot_size: int
    open: float
    close: float
    high: float
    low: float
    mid: float
    range: float

################Load Previous Day Levels########################
def load_pd_levels():
    """
    Reads token file and derives:
        PDH
        PDL
        PDMid
        Range
    """

    token_df = pd.read_csv(token_file)
    for symbol in token_df["Symbol"]:
        candle_file = os.path.join("nifty100_data", f"{symbol}.csv") 

        try:
            df = pd.read_csv(candle_file)
            last = df.iloc[-1]

            high = float(last["High"])
            low = float(last["Low"])
            open_price = float(last["Open"])
            close_price = float(last["Close"])

            # Store the levels in the global dictionary
            levels[symbol] = PDLevels(
                symbol=symbol,
                trading_symbol=token_df[token_df["Symbol"] == symbol]["TradingSymbol"].values[0],
                token=token_df[token_df["Symbol"] == symbol]["Token"].values[0],
                lot_size=token_df[token_df["Symbol"] == symbol]["LotSize"].values[0],
                open=open_price,
                close=close_price,
                high=high,
                low=low,
                mid=(high + low) / 2,
                range=round(high - low, 2)
            )

        except Exception as e:
            print(f"{symbol}: {e}")
#####################Stratagies########################

################Prepare Redis and classify state for each symbol################
# Load PD Levels and classify state for each symbol
load_pd_levels()

print("Loaded PD Levels:")
for level in levels.values():
    print(
        f"{level.trading_symbol}: "
        f"Token={level.token}, "
        f"Lot Size={level.lot_size}, "
        f"Open={level.open}, "
        f"Close={level.close}, "
        f"High={level.high}, "
        f"Low={level.low}, "
        f"Mid={level.mid}, "
        f"Range={level.range}"
    )

##########################Run in Loop#####################
INTERVAL = 5 * 60  # 5 minutes

# Run in a loop
while True:
    print("Run stratagies.....")
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute

    # Trading window: 09:15 to 15:30
    start_minutes = 9 * 60 + 15
    end_minutes = 23 * 60 + 30

    if start_minutes <= current_minutes <= end_minutes:
        loop_start = time.time()
        
        try:
            for level in levels.values():
                latest_key = f"HavyaTej:{level.token}"
                rObj = redisObject.get(latest_key)
                if rObj is None:
                    print(f"No data found in Redis for token: {level.token}")
                    continue

                rObj = json.loads(rObj)
                latest_price = rObj.get("lp")  # Assuming 'lp' is the field for open price
                day_high = rObj.get("h")
                day_low = rObj.get("l")
                day_open = rObj.get("o")

                if day_open is None:
                    print(f"No 'open price' field found in Redis data for token: {level.token}")
                    continue
                print(f"Token: {level.token}, Open Price: {day_open}")

        except subprocess.CalledProcessError as e:
            print(f"Script failed: {e}")

        elapsed = time.time() - loop_start
        wait_time = max(0, INTERVAL - elapsed)

        if wait_time > 0:
            print(f"Waiting {wait_time:.1f} seconds until next run...")
            time.sleep(wait_time)
        else:
            print("Processing took longer than 5 minutes. Starting next run immediately.")
    else:
        print("Outside trading hours. Waiting until next trading window...")
        exit()  # Exit the script if outside trading hours



# print("\nStates:")
# for symbol, s in state.items():
#     print(f"{symbol}: {s.name}")
##############################################################################