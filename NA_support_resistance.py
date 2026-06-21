import os
import glob
import numpy as np
import pandas as pd

# ==========================================================
# CONFIG
# ==========================================================

DATA_FOLDER = "nifty100_data"
LOOKBACK_DAYS = 60
SWING_WINDOW = 2
ATR_PERIOD = 14
ATR_MULTIPLIER = 0.50
MIN_TOUCHES = 2

# ==========================================================
# ATR
# ==========================================================

def calculate_atr(df, period=14):

    high_low = df["High"] - df["Low"]
    high_close = abs(df["High"] - df["Close"].shift(1))
    low_close = abs(df["Low"] - df["Close"].shift(1))

    tr = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    atr = tr.rolling(period).mean()

    return float(atr.iloc[-1])

# ==========================================================
# SWING HIGH / LOW
# ==========================================================

def find_swings(df, window=2):

    swing_highs = []
    swing_lows = []

    for i in range(window, len(df) - window):

        current_high = df.iloc[i]["High"]
        current_low = df.iloc[i]["Low"]

        left_highs = df.iloc[i-window:i]["High"]
        right_highs = df.iloc[i+1:i+window+1]["High"]

        left_lows = df.iloc[i-window:i]["Low"]
        right_lows = df.iloc[i+1:i+window+1]["Low"]

        if (
            current_high > left_highs.max()
            and current_high > right_highs.max()
        ):
            swing_highs.append(current_high)

        if (
            current_low < left_lows.min()
            and current_low < right_lows.min()
        ):
            swing_lows.append(current_low)

    return swing_highs, swing_lows

# ==========================================================
# ATR CLUSTERING
# ==========================================================

def cluster_levels(levels, atr):

    if len(levels) == 0:
        return []

    tolerance = atr * ATR_MULTIPLIER

    levels = sorted(levels)

    clusters = []
    current_cluster = [levels[0]]

    for level in levels[1:]:

        cluster_avg = np.mean(current_cluster)

        if abs(level - cluster_avg) <= tolerance:
            current_cluster.append(level)
        else:
            clusters.append(current_cluster)
            current_cluster = [level]

    clusters.append(current_cluster)

    results = []

    for cluster in clusters:

        touches = len(cluster)

        if touches < MIN_TOUCHES:
            continue

        results.append({
            "level": round(np.mean(cluster), 2),
            "touches": touches,
            "low": round(min(cluster), 2),
            "high": round(max(cluster), 2)
        })

    return results

# ==========================================================
# GET TOP 5 LEVELS
# ==========================================================

def get_levels(close_price, supports, resistances):

    support_levels = sorted(
        [x["level"] for x in supports if x["level"] < close_price],
        reverse=True
    )

    resistance_levels = sorted(
        [x["level"] for x in resistances if x["level"] > close_price]
    )

    support_levels = support_levels[:5]
    resistance_levels = resistance_levels[:5]

    while len(support_levels) < 5:
        support_levels.append(np.nan)

    while len(resistance_levels) < 5:
        resistance_levels.append(np.nan)

    return support_levels, resistance_levels

# ==========================================================
# PROCESS ONE STOCK
# ==========================================================

def process_stock(file_path):

    stock = os.path.basename(file_path).replace(".csv", "")

    try:

        df = pd.read_csv(file_path)

        required_cols = [
            "Open",
            "High",
            "Low",
            "Close"
        ]

        if not all(col in df.columns for col in required_cols):
            return None

        df = df.tail(LOOKBACK_DAYS).copy()

        if len(df) < 20:
            return None

        atr = calculate_atr(df, ATR_PERIOD)

        swing_highs, swing_lows = find_swings(
            df,
            SWING_WINDOW
        )

        supports = cluster_levels(
            swing_lows,
            atr
        )

        resistances = cluster_levels(
            swing_highs,
            atr
        )

        current_close = round(
            float(df.iloc[-1]["Close"]),
            2
        )

        supports_5, resistances_5 = get_levels(
            current_close,
            supports,
            resistances
        )

        row = {
            "Stock": stock,
            "Close": current_close,
            "ATR": round(atr, 2),

            "S1": supports_5[0],
            "S2": supports_5[1],
            "S3": supports_5[2],
            "S4": supports_5[3],
            "S5": supports_5[4],

            "R1": resistances_5[0],
            "R2": resistances_5[1],
            "R3": resistances_5[2],
            "R4": resistances_5[3],
            "R5": resistances_5[4]
        }

        return row

    except Exception as e:

        print(f"Error {stock}: {e}")
        return None

# ==========================================================
# MAIN
# ==========================================================

def main():

    files = glob.glob(
        os.path.join(DATA_FOLDER, "*.csv")
    )

    if not files:
        print("No CSV files found.")
        return

    results = []

    print(f"Processing {len(files)} files...\n")

    for file_path in sorted(files):

        row = process_stock(file_path)

        if row is not None:
            results.append(row)

            print(
                f"{row['Stock']:20}"
                f" Close={row['Close']:10.2f}"
            )

    result_df = pd.DataFrame(results)

    result_df = result_df.sort_values(
        "Stock"
    )

    result_df.to_csv(
        "support_resistance_levels.csv",
        index=False
    )

    print("\nSaved:")
    print("support_resistance_levels.csv")

    print("\nSample Output:")
    print(
        result_df.head(10).to_string(index=False)
    )

# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":
    main()