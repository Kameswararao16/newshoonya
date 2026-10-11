import os
import pandas as pd
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FOLDER = "live_data"
OUTPUT_FOLDER = "nifty100_data_today"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ============================================================
# PROCESS ONE STOCK FILE
# ============================================================

def process_file(input_file):

    filename = os.path.basename(input_file)

    output_file = os.path.join(
        OUTPUT_FOLDER,
        filename
    )

    print("\n" + "=" * 60)
    print(f"Processing: {filename}")
    print("=" * 60)

    # --------------------------------------------------------
    # READ 1-MINUTE DATA
    # --------------------------------------------------------

    try:
        df = pd.read_csv(input_file)
    except Exception as e:
        print(f"ERROR reading {input_file}: {e}")
        return

    if df.empty:
        print("No data found")
        return

    # --------------------------------------------------------
    # REQUIRED INPUT COLUMNS
    # --------------------------------------------------------

    required_columns = [
        "date_time",
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        print("Missing columns:", missing_columns)
        return

    # --------------------------------------------------------
    # CONVERT DATETIME
    # --------------------------------------------------------

    df["date_time"] = pd.to_datetime(
        df["date_time"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["date_time"]
    )

    if df.empty:
        print("No valid datetime data")
        return

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    df = df.sort_values(
        "date_time"
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # IGNORE 09:14 INITIALIZATION ROW
    # --------------------------------------------------------

    market_start = pd.to_datetime(
        "09:15"
    ).time()

    df = df[
        df["date_time"].dt.time >= market_start
    ]

    if df.empty:
        print("No market data after 09:15")
        return

    # ========================================================
    # CREATE 5-MINUTE BUCKET
    #
    # 09:15 - 09:19 -> 09:15
    # 09:20 - 09:24 -> 09:20
    # 09:25 - 09:29 -> 09:25
    # ========================================================

    df["candle_time"] = (
        df["date_time"]
        - pd.to_timedelta(
            df["date_time"].dt.minute % 5,
            unit="m"
        )
    )

    # ========================================================
    # FIND LAST CANDLE ALREADY STORED
    # ========================================================

    if os.path.exists(output_file):

        try:

            existing = pd.read_csv(
                output_file,
                usecols=["Date"]
            )

        except Exception as e:

            print(
                f"ERROR reading existing "
                f"{output_file}: {e}"
            )

            return

        if not existing.empty:

            existing["Date"] = pd.to_datetime(
                existing["Date"],
                dayfirst=True,
                errors="coerce"
            )

            existing = existing.dropna(
                subset=["Date"]
            )

        if not existing.empty:

            # ------------------------------------------------
            # Last 5-minute candle in output
            # ------------------------------------------------

            last_candle = existing[
                "Date"
            ].max()

            # ------------------------------------------------
            # Next 5-minute candle required
            # ------------------------------------------------

            start_time = (
                last_candle
                + pd.Timedelta(minutes=5)
            )

            print(
                f"Last stored candle : "
                f"{last_candle.strftime('%d-%m-%Y %H:%M:%S')}"
            )

            print(
                f"Next required      : "
                f"{start_time.strftime('%d-%m-%Y %H:%M:%S')}"
            )

        else:

            start_time = df[
                "candle_time"
            ].min()

            print(
                "Output file is empty"
            )

    else:

        # ----------------------------------------------------
        # First run
        # ----------------------------------------------------

        start_time = df[
            "candle_time"
        ].min()

        print(
            "Output file does not exist"
        )

        print(
            f"Starting from      : "
            f"{start_time.strftime('%d-%m-%Y %H:%M:%S')}"
        )

    # ========================================================
    # ONLY PROCESS MISSING CANDLES
    # ========================================================

    df = df[
        df["candle_time"] >= start_time
    ].copy()

    if df.empty:

        print("No new 1-minute data")
        return

    # ========================================================
    # CURRENT TIME
    # ========================================================

    now = pd.Timestamp.now()

    # ========================================================
    # ONLY COMPLETED 5-MINUTE CANDLES
    # ========================================================

    df = df[
        df["candle_time"]
        + pd.Timedelta(minutes=5)
        <= now
    ]

    if df.empty:

        print(
            "No completed 5-minute candles"
        )

        return

    # ========================================================
    # CREATE 5-MINUTE CANDLES
    # ========================================================

    candles = []

    for candle_time, group in df.groupby(
        "candle_time"
    ):

        # ----------------------------------------------------
        # Sort
        # ----------------------------------------------------

        group = group.sort_values(
            "date_time"
        )

        # ----------------------------------------------------
        # Need exactly 5 one-minute candles
        # ----------------------------------------------------

        if len(group) != 5:

            print(
                f"Skipping "
                f"{candle_time.strftime('%H:%M')} "
                f"- found {len(group)} minutes"
            )

            continue

        # ----------------------------------------------------
        # Check all 5 minutes are present
        # ----------------------------------------------------

        expected_times = pd.date_range(
            start=candle_time,
            periods=5,
            freq="min"
        )

        actual_times = (
            group["date_time"]
            .dt.floor("min")
            .tolist()
        )

        if actual_times != list(expected_times):

            print(
                f"Skipping "
                f"{candle_time.strftime('%H:%M')} "
                f"- missing minute"
            )

            continue

        # ----------------------------------------------------
        # CREATE OHLCV
        # ----------------------------------------------------

        candle = {
            "Date": candle_time,

            # First minute OPEN
            "Open": group.iloc[0]["open"],

            # Highest HIGH
            "High": group["high"].max(),

            # Lowest LOW
            "Low": group["low"].min(),

            # Last minute CLOSE
            "Close": group.iloc[-1]["close"],

            # Total volume
            "Volume": group["volume"].sum()
        }

        candles.append(candle)

    # ========================================================
    # NOTHING TO WRITE
    # ========================================================

    if not candles:

        print(
            "No new complete 5-minute candles"
        )

        return

    # ========================================================
    # RESULT DATAFRAME
    # ========================================================

    result = pd.DataFrame(
        candles
    )

    result = result.sort_values(
        "Date"
    ).reset_index(drop=True)

    # ========================================================
    # FORMAT DATE
    # ========================================================

    result["Date"] = result[
        "Date"
    ].dt.strftime(
        "%d-%m-%Y %H:%M:%S"
    )

    # ========================================================
    # FORMAT PRICE
    # ========================================================

    for column in [
        "Open",
        "High",
        "Low",
        "Close"
    ]:

        result[column] = result[column].map(
            lambda x: f"{float(x):.2f}"
        )

    # ========================================================
    # FORMAT VOLUME
    # ========================================================

    result["Volume"] = result[
        "Volume"
    ].fillna(0)

    # ========================================================
    # ENSURE EXACT COLUMN ORDER
    # ========================================================

    result = result[
        [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]
    ]

    # ========================================================
    # APPEND TO OUTPUT FILE
    # ========================================================

    file_exists = os.path.exists(
        output_file
    )

    result.to_csv(
        output_file,
        mode="a",
        header=not file_exists,
        index=False
    )

    # ========================================================
    # DISPLAY
    # ========================================================

    print(
        f"\nAdded {len(result)} "
        f"new 5-minute candles:"
    )

    for _, row in result.iterrows():

        print(
            f"{row['Date']},"
            f"{row['Open']},"
            f"{row['High']},"
            f"{row['Low']},"
            f"{row['Close']},"
            f"{row['Volume']}"
        )


# ============================================================
# PROCESS ALL STOCK FILES
# ============================================================

def process_all():

    if not os.path.exists(
        INPUT_FOLDER
    ):

        print(
            f"ERROR: Input folder "
            f"'{INPUT_FOLDER}' does not exist"
        )

        return

    files = [
        filename
        for filename in os.listdir(
            INPUT_FOLDER
        )
        if filename.lower().endswith(".csv")
    ]

    if not files:

        print(
            f"No CSV files found in "
            f"'{INPUT_FOLDER}'"
        )

        return

    print(
        f"\nFound {len(files)} CSV files"
    )

    # --------------------------------------------------------
    # Process every stock
    # --------------------------------------------------------

    for filename in sorted(files):

        input_file = os.path.join(
            INPUT_FOLDER,
            filename
        )

        try:

            process_file(
                input_file
            )

        except Exception as e:

            print(
                f"ERROR processing "
                f"{filename}: {e}"
            )


# # ============================================================
# # MAIN
# # ============================================================

# if __name__ == "__main__":

#     print(
#         "\n"
#         + "=" * 60
#     )

#     print(
#         "5-MINUTE CANDLE PROCESSOR"
#     )

#     print(
#         "=" * 60
#     )

#     print(
#         "Start:",
#         datetime.now().strftime(
#             "%Y-%m-%d %H:%M:%S"
#         )
#     )

#     print(
#         f"Input : {INPUT_FOLDER}"
#     )

#     print(
#         f"Output: {OUTPUT_FOLDER}"
#     )

#     process_all()

#     print(
#         "\n"
#         + "=" * 60
#     )

#     print(
#         "Completed:",
#         datetime.now().strftime(
#             "%Y-%m-%d %H:%M:%S"
#         )
#     )

#     print(
#         "=" * 60
#     )