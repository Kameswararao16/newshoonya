import os
import sys
import json
import yaml
import redis
import queue
import threading
import time
import pandas as pd
from pathlib import Path
import shutil

from datetime import datetime, time as dt_time

from api_helper import NorenApiPy


# ============================================================
# CONFIGURATION
# ============================================================

LIVE_DATA_FOLDER = "live_data"
LIVE_DATA_FOLDER_ARCHIVE = "live_data_archive"

# Market data running window
MARKET_START = dt_time(9, 14, 0)
MARKET_END = dt_time(15, 14, 0)

os.makedirs(LIVE_DATA_FOLDER, exist_ok=True)
os.makedirs(LIVE_DATA_FOLDER_ARCHIVE, exist_ok=True)
###############################################################
# Back-up
folder = Path(LIVE_DATA_FOLDER)
archive_folder = Path(LIVE_DATA_FOLDER_ARCHIVE)

# Move existing files/folders to archive if they exist
if folder.exists():
    # Create timestamped archive folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = archive_folder / f"live_data_{timestamp}"
    archive.mkdir(parents=True, exist_ok=True)

    # Move all files/folders into archive
    for item in folder.iterdir():
        shutil.move(str(item), str(archive / item.name))

    print(f"Archived live_data to: {archive}")

else:
    folder.mkdir(parents=True)
    print("Created nifty100_data_today folder.")

time.sleep(10)  # Wait for 10 seconds to ensure the folder is created

# ============================================================
# REDIS
# ============================================================

redisObject = redis.Redis(
    host="localhost",
    port=6379,
    db=0
)


# ============================================================
# QUEUE
# ============================================================

# Unbounded queue.
# We do not intentionally drop WebSocket feeds.
data_queue = queue.Queue()


# ============================================================
# IN-MEMORY DATA
# ============================================================

# Latest feed data per token
webSocketData = {}

# Current 1-minute candle per token
current_candles = {}


# ============================================================
# LOCKS
# ============================================================

candle_lock = threading.Lock()


# ============================================================
# PROGRAM CONTROL
# ============================================================

# Set to False when market window ends.
accept_feeds = True

# Used to stop the main thread.
shutdown_event = threading.Event()


# ============================================================
# SHOONYA API LOGIN
# ============================================================

api = NorenApiPy()

try:

    with open("cred.yml") as f:

        cred = yaml.load(
            f,
            Loader=yaml.FullLoader
        )

    ret = api.injectOAuthHeader(
        cred["Access_token"],
        cred["UID"],
        cred["Account_ID"]
    )

    if ret is not None:

        print(
            f"[{datetime.now()}] "
            f"Login successful"
        )

    else:

        print(
            f"[{datetime.now()}] "
            f"Login failed"
        )

        sys.exit(1)

    api.set_credentials(
        cred["Access_token"],
        cred["UID"],
        cred["Account_ID"]
    )

except Exception as e:

    print(
        f"[{datetime.now()}] "
        f"Login ERROR: {e}"
    )

    sys.exit(1)


# ============================================================
# TOKENS TO SUBSCRIBE
# ============================================================

tokens = [
    "25844",  #HYUNDAI
    "760",  #CGPOWER
    "2664", #PIDILITIND
    "1232", #GRASIM
    "236",  #ASIANPAINT
    "1964",  #TRENT
    "1394", #HINDUNILVR
    "17963",  #NESTLEIND
    "3432",  #TATACONSUM
    "10099", #GODREJCP
    "1333", #HDFCBANK
    "4963",  #ICICIBANK
    "3045",  #SBIN
    "317",  #BAJFINANCE
    "5900",  #AXISBANK
    "16675", #BAJAJFINSV
    "4306", #SHRIRAMFIN
    "21808", #SBILIFE
    "685", #CHOLAFIN
    "3351", #SUNPHARMA
    "7929", #ZYDUSLIFE
    "694", #CIPLA
    "881", #DRREDDY
    "22377", #MAXHEALTH
    "11536", #TCS
    "1594", #INFY
    "7229", #HCLTECH
    "13538", #TECHM
    "25", #ADANIENT
    "11723", #JSWSTEEL
    "1363", #HINDALCO
    "6733", #JINDALSTEL
    "2885", #RELIANCE
    "3563", #ADANIGREEN
    "10217", #ADANIENSOL
    "15083", #ADANIPORTS
    "10604", #BHARTIARTL
    "26000" # NIFTY50
    # Add remaining tokens here
]


# ============================================================
# MARKET TIME FUNCTIONS
# ============================================================

def get_current_time():

    return datetime.now().time()


def is_before_market_start():

    now = get_current_time()

    return now < MARKET_START


def is_market_open():

    now = get_current_time()

    return (
        now >= MARKET_START
        and
        now < MARKET_END
    )


def is_after_market_end():

    now = get_current_time()

    return now >= MARKET_END


def wait_for_market_start():

    """
    If program starts before 09:14,
    wait until 09:14.

    If program starts after 15:14,
    return immediately.
    """

    while True:

        now = datetime.now()

        current_time = now.time()

        # ----------------------------------------------------
        # Already inside market window
        # ----------------------------------------------------

        if (
            current_time >= MARKET_START
            and
            current_time < MARKET_END
        ):

            return True

        # ----------------------------------------------------
        # Market already closed
        # ----------------------------------------------------

        if current_time >= MARKET_END:

            print(
                f"[{datetime.now()}] "
                f"Market window already closed. "
                f"Current time: {current_time.strftime('%H:%M:%S')}"
            )

            return False

        # ----------------------------------------------------
        # Before market start
        # ----------------------------------------------------

        start_datetime = datetime.combine(
            now.date(),
            MARKET_START
        )

        wait_seconds = (
            start_datetime - now
        ).total_seconds()

        print(
            f"[{datetime.now()}] "
            f"Waiting for market start at "
            f"{MARKET_START.strftime('%H:%M:%S')}..."
        )

        # Don't sleep for too long.
        # This allows the program to detect 09:14 quickly.
        time.sleep(
            min(
                max(wait_seconds, 1),
                30
            )
        )


# ============================================================
# REDIS UPDATE
# ============================================================

def update_redis(feed):

    """
    Every processed feed is stored in Redis.

    Redis key:

        HTA:<token>

    Example:

        HTA:26000

    Maintains latest values for:

        lp
        h
        l
        pc
        updated_time
    """

    try:

        if "tk" not in feed:

            return

        token = feed["tk"]

        latest_key = f"HTA:{token}"

        updateData = False

        # ----------------------------------------------------
        # First feed for this token
        # ----------------------------------------------------

        if token not in webSocketData:

            webSocketData[token] = feed.copy()

            updateData = True

        else:

            # ------------------------------------------------
            # LTP
            # ------------------------------------------------

            if "lp" in feed:

                webSocketData[token]["lp"] = feed["lp"]

                updateData = True

            # ------------------------------------------------
            # High
            # ------------------------------------------------

            if "h" in feed:

                webSocketData[token]["h"] = feed["h"]

                updateData = True

            # ------------------------------------------------
            # Low
            # ------------------------------------------------

            if "l" in feed:

                webSocketData[token]["l"] = feed["l"]

                updateData = True

            # ------------------------------------------------
            # Previous close
            # ------------------------------------------------

            if "pc" in feed:

                webSocketData[token]["pc"] = feed["pc"]

                updateData = True

            # ------------------------------------------------
            # Volume
            # ------------------------------------------------

            if "v" in feed:

                webSocketData[token]["v"] = feed["v"]

                updateData = True

        # ----------------------------------------------------
        # Write Redis
        # ----------------------------------------------------

        if updateData:

            webSocketData[token]["updated_time"] = (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            latest_feed = json.dumps(
                webSocketData[token]
            )

            redisObject.set(
                latest_key,
                latest_feed
            )
            # print(f"buy Data: {json.loads(redisObject.get(latest_key))}")

    except Exception as e:

        print(
            f"[{datetime.now()}] "
            f"Redis ERROR: {e} | Feed: {feed}"
        )


# ============================================================
# CREATE NEW 1-MINUTE CANDLE
# ============================================================

def create_candle(feed, minute_time):

    if "lp" not in feed:

        return None

    try:

        price = float(
            feed["lp"]
        )

    except (
        ValueError,
        TypeError
    ):

        return None

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    volume = 0

    if "v" in feed:

        try:

            volume = float(
                feed["v"]
            )

        except (
            ValueError,
            TypeError
        ):

            volume = 0

    # --------------------------------------------------------
    # Candle
    # --------------------------------------------------------

    candle = {

        "date_time":
            minute_time.strftime(
                "%Y-%m-%d %H:%M"
            ),

        "open": price,

        "close": price,

        "high": price,

        "low": price,

        "volume": volume
    }

    return candle

# ============================================================
# CALCULATE PRICE RANGES
# ============================================================

def calculate_price_ranges(token, current_candle=None):

    try:

        file_path = os.path.join(
            LIVE_DATA_FOLDER,
            f"{token}.csv"
        )

        frames = []

        # ----------------------------------------------------
        # Read existing completed candles
        # ----------------------------------------------------

        if os.path.exists(file_path):

            df = pd.read_csv(file_path)

            if not df.empty:

                df["date_time"] = pd.to_datetime(
                    df["date_time"]
                )

                frames.append(df)

        # ----------------------------------------------------
        # Add candle which is about to be saved
        # ----------------------------------------------------

        if current_candle is not None:

            temp = current_candle.copy()

            temp["date_time"] = pd.to_datetime(
                temp["date_time"]
            )

            frames.append(
                pd.DataFrame([temp])
            )

        # ----------------------------------------------------
        # No data
        # ----------------------------------------------------

        if not frames:

            return {
                "day_high": None,
                "day_low": None,

                "high_15m": None,
                "low_15m": None,

                "high_30m": None,
                "low_30m": None,

                "high_1h": None,
                "low_1h": None,

                "high_2h": None,
                "low_2h": None,

                "high_4h": None,
                "low_4h": None
            }

        # ----------------------------------------------------
        # Combine
        # ----------------------------------------------------

        df = pd.concat(
            frames,
            ignore_index=True
        )

        # ----------------------------------------------------
        # Remove duplicate candles
        # ----------------------------------------------------

        df = df.drop_duplicates(
            subset=["date_time"],
            keep="last"
        )

        df = df.sort_values(
            "date_time"
        )

        # ----------------------------------------------------
        # Only today's candles
        # ----------------------------------------------------

        today = datetime.now().date()

        df = df[
            df["date_time"].dt.date == today
        ]

        if df.empty:

            return {}

        # ====================================================
        # DAY HIGH / LOW
        # ====================================================

        day_high = df["high"].max()

        day_low = df["low"].min()

        # ====================================================
        # CURRENT CANDLE TIME
        # ====================================================

        current_time = df["date_time"].max()

        # ====================================================
        # ROLLING RANGE
        # ====================================================

        def get_range(minutes):

            start_time = (
                current_time
                - pd.Timedelta(
                    minutes=minutes
                )
            )

            temp = df[
                df["date_time"] >= start_time
            ]

            if temp.empty:

                return None, None

            return (
                temp["high"].max(),
                temp["low"].min()
            )

        # ----------------------------------------------------
        # 15 minutes
        # ----------------------------------------------------

        high_15m, low_15m = get_range(15)

        # ----------------------------------------------------
        # 30 minutes
        # ----------------------------------------------------

        high_30m, low_30m = get_range(30)

        # ----------------------------------------------------
        # 1 hour
        # ----------------------------------------------------

        high_1h, low_1h = get_range(60)

        # ----------------------------------------------------
        # 2 hours
        # ----------------------------------------------------

        high_2h, low_2h = get_range(120)

        # ----------------------------------------------------
        # 4 hours
        # ----------------------------------------------------

        high_4h, low_4h = get_range(240)

        return {

            "day_high": day_high,
            "day_low": day_low,

            "high_15m": high_15m,
            "low_15m": low_15m,

            "high_30m": high_30m,
            "low_30m": low_30m,

            "high_1h": high_1h,
            "low_1h": low_1h,

            "high_2h": high_2h,
            "low_2h": low_2h,

            "high_4h": high_4h,
            "low_4h": low_4h
        }

    except Exception as e:

        print(
            f"[{datetime.now()}] "
            f"RANGE ERROR {token}: {e}"
        )

        return {}

# ============================================================
# SAVE COMPLETED CANDLE
# ============================================================

def save_candle(token, candle):

    try:

        file_path = os.path.join(
            LIVE_DATA_FOLDER,
            f"{token}.csv"
        )

        columns = [
            "date_time",
            "open",
            "close",
            "high",
            "low",
            "volume",

            "day_high",
            "day_low",

            "high_15m",
            "low_15m",

            "high_30m",
            "low_30m",

            "high_1h",
            "low_1h",

            "high_2h",
            "low_2h",

            "high_4h",
            "low_4h"
        ]

        # ----------------------------------------------------
        # Calculate ranges using existing CSV + current candle
        # ----------------------------------------------------

        ranges = calculate_price_ranges(
            token,
            candle
        )

        # ----------------------------------------------------
        # Add calculated values to candle
        # ----------------------------------------------------

        candle["day_high"] = ranges["day_high"]
        candle["day_low"] = ranges["day_low"]

        candle["high_15m"] = ranges["high_15m"]
        candle["low_15m"] = ranges["low_15m"]

        candle["high_30m"] = ranges["high_30m"]
        candle["low_30m"] = ranges["low_30m"]

        candle["high_1h"] = ranges["high_1h"]
        candle["low_1h"] = ranges["low_1h"]

        candle["high_2h"] = ranges["high_2h"]
        candle["low_2h"] = ranges["low_2h"]

        candle["high_4h"] = ranges["high_4h"]
        candle["low_4h"] = ranges["low_4h"]

        # ----------------------------------------------------
        # Create row
        # ----------------------------------------------------

        new_row = pd.DataFrame(
            [candle],
            columns=columns
        )

        # ----------------------------------------------------
        # First row
        # ----------------------------------------------------

        if not os.path.exists(file_path):

            new_row.to_csv(
                file_path,
                index=False
            )

        # ----------------------------------------------------
        # Append
        # ----------------------------------------------------

        else:

            new_row.to_csv(
                file_path,
                mode="a",
                header=False,
                index=False
            )

        print(
            f"[{datetime.now()}] "
            f"CANDLE SAVED: {token} "
            f"{candle}"
        )

    except Exception as e:

        print(
            f"[{datetime.now()}] "
            f"CSV ERROR for {token}: {e}"
        )

# ============================================================
# UPDATE 1-MINUTE CANDLE
# ============================================================

def update_candle(feed):

    try:

        if "tk" not in feed:

            return

        if "lp" not in feed:

            return

        token = feed["tk"]

        # ----------------------------------------------------
        # Convert price
        # ----------------------------------------------------

        try:

            price = float(
                feed["lp"]
            )

        except (
            ValueError,
            TypeError
        ):

            return

        # ----------------------------------------------------
        # Current minute
        # ----------------------------------------------------

        minute_time = datetime.now().replace(
            second=0,
            microsecond=0
        )

        with candle_lock:

            # =================================================
            # FIRST FEED FOR THIS TOKEN
            # =================================================

            if token not in current_candles:

                candle = create_candle(
                    feed,
                    minute_time
                )

                if candle is not None:

                    current_candles[token] = {

                        "minute":
                            minute_time,

                        "candle":
                            candle
                    }

                return

            # =================================================
            # CURRENT CANDLE
            # =================================================

            current = current_candles[token]

            current_minute = current["minute"]

            candle = current["candle"]

            # =================================================
            # SAME MINUTE
            # =================================================

            if minute_time == current_minute:

                # ------------------------------------------------
                # Close
                # ------------------------------------------------

                candle["close"] = price

                # ------------------------------------------------
                # High
                # ------------------------------------------------

                if price > candle["high"]:

                    candle["high"] = price

                # ------------------------------------------------
                # Low
                # ------------------------------------------------

                if price < candle["low"]:

                    candle["low"] = price

                # ------------------------------------------------
                # Volume
                # ------------------------------------------------

                if "v" in feed:

                    try:

                        candle["volume"] = float(
                            feed["v"]
                        )

                    except (
                        ValueError,
                        TypeError
                    ):

                        pass

            # =================================================
            # NEW MINUTE
            # =================================================

            else:

                # ------------------------------------------------
                # Save completed previous candle
                # ------------------------------------------------

                save_candle(
                    token,
                    candle
                )

                # ------------------------------------------------
                # Create new candle
                # ------------------------------------------------

                new_candle = create_candle(
                    feed,
                    minute_time
                )

                if new_candle is not None:

                    current_candles[token] = {

                        "minute":
                            minute_time,

                        "candle":
                            new_candle
                    }

    except Exception as e:

        print(
            f"[{datetime.now()}] "
            f"CANDLE ERROR: {e}"
        )


# ============================================================
# PROCESS EVERY FEED
# ============================================================

def process_feed():

    print(
        f"[{datetime.now()}] "
        f"Feed processing thread started."
    )

    while True:

        # ----------------------------------------------------
        # Wait for feed
        # ----------------------------------------------------

        feed = data_queue.get()

        try:

            # ------------------------------------------------
            # Redis
            # ------------------------------------------------

            update_redis(feed)

            # ------------------------------------------------
            # 1-minute candle
            # ------------------------------------------------

            update_candle(feed)

        except Exception as e:

            print(
                f"[{datetime.now()}] "
                f"PROCESS ERROR: {e}"
            )

        finally:

            data_queue.task_done()


# ============================================================
# WEBSOCKET FEED CALLBACK
# ============================================================

def event_handler_feed_update(feed):

    """
    VERY FAST CALLBACK.

    Do not write CSV here.
    Do not perform expensive processing here.

    Simply put every feed into the queue.

    The processing thread handles:
        Redis
        Candle
        CSV
    """

    global accept_feeds

    try:

        # ----------------------------------------------------
        # After 15:14 don't accept new feeds
        # ----------------------------------------------------

        if not accept_feeds:

            return

        # ----------------------------------------------------
        # Put every feed into queue
        # ----------------------------------------------------

        data_queue.put(feed)

    except Exception as e:

        print(
            f"[{datetime.now()}] "
            f"QUEUE ERROR: {e}"
        )


# ============================================================
# ORDER UPDATE CALLBACK
# ============================================================

def event_handler_order_update(message):

    print(
        f"[{datetime.now()}] "
        f"ORDER EVENT: {message}"
    )


# ============================================================
# WEBSOCKET OPEN CALLBACK
# ============================================================

def socket_open_callback():

    global accept_feeds

    print(
        f"[{datetime.now()}] "
        f"WebSocket connection opened."
    )

    # --------------------------------------------------------
    # Make sure we are still inside market window
    # --------------------------------------------------------

    if not is_market_open():

        print(
            f"[{datetime.now()}] "
            f"Outside market window. "
            f"Not subscribing."
        )

        accept_feeds = False

        return

    try:

        # ----------------------------------------------------
        # Subscribe all tokens
        # ----------------------------------------------------

        for token in tokens:

            if not accept_feeds:

                break

            try:

                ret = api.subscribe(
                    f"NSE|{token}"
                )

                print(
                    f"[{datetime.now()}] "
                    f"Subscribed NSE|{token} : {ret}"
                )

            except Exception as e:

                print(
                    f"[{datetime.now()}] "
                    f"Subscribe ERROR NSE|{token}: {e}"
                )

    except Exception as e:

        print(
            f"[{datetime.now()}] "
            f"Subscription ERROR: {e}"
        )


# ============================================================
# WEBSOCKET CLOSE CALLBACK
# ============================================================

def socket_close_callback():

    print(
        f"[{datetime.now()}] "
        f"WebSocket connection closed."
    )


# ============================================================
# UNSUBSCRIBE ALL TOKENS
# ============================================================

def unsubscribe_all():

    print(
        f"[{datetime.now()}] "
        f"Unsubscribing tokens..."
    )

    try:

        if len(tokens) == 0:

            return

        symbols = [
            f"NSE|{token}"
            for token in tokens
        ]

        try:

            ret = api.unsubscribe(
                symbols
            )

            print(
                f"[{datetime.now()}] "
                f"Unsubscribe result: {ret}"
            )

        except Exception as e:

            print(
                f"[{datetime.now()}] "
                f"Bulk unsubscribe failed: {e}"
            )

            # ------------------------------------------------
            # Try individually
            # ------------------------------------------------

            for symbol in symbols:

                try:

                    api.unsubscribe(symbol)

                except Exception as inner_e:

                    print(
                        f"[{datetime.now()}] "
                        f"Unsubscribe ERROR "
                        f"{symbol}: {inner_e}"
                    )

    except Exception as e:

        print(
            f"[{datetime.now()}] "
            f"Unsubscribe ERROR: {e}"
        )


# ============================================================
# SAVE CURRENT CANDLES
# ============================================================

def save_current_candles():

    print(
        f"[{datetime.now()}] "
        f"Saving current candles..."
    )

    with candle_lock:

        for token, current in current_candles.items():

            try:

                candle = current["candle"]

                save_candle(
                    token,
                    candle
                )

            except Exception as e:

                print(
                    f"[{datetime.now()}] "
                    f"Shutdown save ERROR "
                    f"{token}: {e}"
                )


# ============================================================
# QUEUE MONITOR
# ============================================================

def monitor_queue():

    """
    Displays queue size every 10 seconds.

    If queue continuously increases,
    feed processing is slower than
    incoming WebSocket feeds.
    """

    while not shutdown_event.is_set():

        try:

            size = data_queue.qsize()

            if size > 0:

                print(
                    f"[{datetime.now()}] "
                    f"Queue size: {size}"
                )

            shutdown_event.wait(10)

        except Exception as e:

            print(
                f"[{datetime.now()}] "
                f"Queue monitor ERROR: {e}"
            )

            break


# ============================================================
# MAIN
# ============================================================

def main():

    global accept_feeds

    print("=" * 70)

    print(
        "SHOONYA WEBSOCKET MARKET DATA"
    )

    print("=" * 70)

    print(
        f"[{datetime.now()}] "
        f"Tokens: {len(tokens)}"
    )

    print(
        f"[{datetime.now()}] "
        f"Live data folder: {LIVE_DATA_FOLDER}"
    )

    print(
        f"[{datetime.now()}] "
        f"Market window: "
        f"{MARKET_START.strftime('%H:%M:%S')} - "
        f"{MARKET_END.strftime('%H:%M:%S')}"
    )

    # ========================================================
    # WAIT FOR 09:14
    # ========================================================

    if not wait_for_market_start():

        print(
            f"[{datetime.now()}] "
            f"Program stopped. "
            f"Market window has ended."
        )

        return

    print(
        f"[{datetime.now()}] "
        f"Market window started."
    )

    # ========================================================
    # START FEED PROCESSING THREAD
    # ========================================================

    processor_thread = threading.Thread(
        target=process_feed,
        daemon=True,
        name="FeedProcessor"
    )

    processor_thread.start()

    # ========================================================
    # START QUEUE MONITOR
    # ========================================================

    monitor_thread = threading.Thread(
        target=monitor_queue,
        daemon=True,
        name="QueueMonitor"
    )

    monitor_thread.start()

    # ========================================================
    # START WEBSOCKET
    # ========================================================

    try:

        print(
            f"[{datetime.now()}] "
            f"Starting WebSocket..."
        )

        api.start_websocket(

            subscribe_callback=
                event_handler_feed_update,

            order_update_callback=
                event_handler_order_update,

            socket_open_callback=
                socket_open_callback,

            socket_close_callback=
                socket_close_callback
        )

        print(
            f"[{datetime.now()}] "
            f"WebSocket started."
        )

        # ====================================================
        # KEEP PROGRAM RUNNING UNTIL 15:14
        # ====================================================

        while is_market_open():

            time.sleep(1)

        # ====================================================
        # MARKET END
        # ====================================================

        print(
            f"[{datetime.now()}] "
            f"Market end time reached."
        )

    except KeyboardInterrupt:

        print(
            f"\n[{datetime.now()}] "
            f"Keyboard interrupt received."
        )

    except Exception as e:

        print(
            f"[{datetime.now()}] "
            f"WebSocket ERROR: {e}"
        )

    finally:

        # ====================================================
        # STOP ACCEPTING NEW FEEDS
        # ====================================================

        accept_feeds = False

        print(
            f"[{datetime.now()}] "
            f"Stopped accepting new feeds."
        )

        # ====================================================
        # UNSUBSCRIBE
        # ====================================================

        unsubscribe_all()

        # ====================================================
        # WAIT FOR QUEUED FEEDS
        # ====================================================

        print(
            f"[{datetime.now()}] "
            f"Feeds remaining in queue: "
            f"{data_queue.qsize()}"
        )

        print(
            f"[{datetime.now()}] "
            f"Waiting for queued feeds to finish..."
        )

        data_queue.join()

        print(
            f"[{datetime.now()}] "
            f"All queued feeds processed."
        )

        # ====================================================
        # SAVE CURRENT INCOMPLETE CANDLES
        # ====================================================

        save_current_candles()

        # ====================================================
        # STOP MONITOR
        # ====================================================

        shutdown_event.set()

        print(
            f"[{datetime.now()}] "
            f"Program stopped."
        )


# ============================================================
# START PROGRAM
# ============================================================

if __name__ == "__main__":

    main()
