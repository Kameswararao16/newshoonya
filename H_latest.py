import pandas as pd
import os

# file = os.path.join(DATA_FOLDER, ticker+".csv")
DATA_FOLDER = "nifty100_data"
file = os.path.join(DATA_FOLDER, "NIFTY50.csv")
df = pd.read_csv(file)


df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date").reset_index(drop=True)

# Previous day
df["prev_high"] = df["High"].shift(1)
df["prev_low"] = df["Low"].shift(1)
df["prev_close"] = df["Close"].shift(1)

# Previous-previous day
df["prev2_high"] = df["High"].shift(2)
df["prev2_low"] = df["Low"].shift(2)

# Previous day's range
df["prev_range"] = df["prev_high"] - df["prev_low"]


# --------------------------------------------------
# BUY / SELL SIGNAL
# --------------------------------------------------

def get_signal(row):

    if row["prev_close"] > row["prev2_high"]:
        return "BUY"

    elif row["prev_close"] < row["prev2_low"]:
        return "SELL"

    return "NO SIGNAL"


df["Buy/Sell"] = df.apply(get_signal, axis=1)


# --------------------------------------------------
# ENTRY LEVELS
# --------------------------------------------------

def calculate_entries(row):

    if row["Buy/Sell"] == "BUY":

        # From previous day's HIGH downward
        entry_20 = row["prev_high"] - (row["prev_range"] * 0.20)
        entry_40 = row["prev_high"] - (row["prev_range"] * 0.40)

    elif row["Buy/Sell"] == "SELL":

        # From previous day's LOW upward
        entry_20 = row["prev_low"] + (row["prev_range"] * 0.20)
        entry_40 = row["prev_low"] + (row["prev_range"] * 0.40)

    else:
        entry_20 = None
        entry_40 = None

    return pd.Series([entry_20, entry_40])


df[["entry_20", "entry_40"]] = df.apply(
    calculate_entries,
    axis=1
)


# --------------------------------------------------
# CHECK WHETHER TODAY REACHED ENTRY
# --------------------------------------------------

def check_entry(row):

    if row["Buy/Sell"] == "BUY":

        # Price falls down to entry
        if row["Low"] <= row["entry_40"]:
            return "40%"

        elif row["Low"] <= row["entry_20"]:
            return "20%"

        return "NO ENTRY"

    elif row["Buy/Sell"] == "SELL":

        # Price rises up to entry
        if row["High"] >= row["entry_40"]:
            return "40%"

        elif row["High"] >= row["entry_20"]:
            return "20%"

        return "NO ENTRY"

    return "NO SIGNAL"


df["Entry"] = df.apply(check_entry, axis=1)


# --------------------------------------------------
# CURRENT DAY DIRECTION
# --------------------------------------------------

def get_direction(row):

    if row["Close"] > row["Open"]:
        return "GREEN"

    elif row["Close"] < row["Open"]:
        return "RED"

    return "FLAT"


df["Direction"] = df.apply(get_direction, axis=1)


# --------------------------------------------------
# RESULT BASED ON CURRENT DAY CLOSE
# --------------------------------------------------

def get_result(row):

    if row["Entry"] == "NO ENTRY":
        return "NO ENTRY"

    if row["Entry"] == "NO SIGNAL":
        return "NO SIGNAL"

    if row["Entry"] == "40%":
        entry_price = row["entry_40"]
    else:
        entry_price = row["entry_20"]

    if row["Buy/Sell"] == "BUY":

        return "PROFIT" if row["Close"] > entry_price else "LOSS"

    elif row["Buy/Sell"] == "SELL":

        return "PROFIT" if row["Close"] < entry_price else "LOSS"


df["Result"] = df.apply(get_result, axis=1)


# --------------------------------------------------
# DISPLAY
# --------------------------------------------------

result_df = df[
    [
        "Date",
        "Open",
        "Low",
        "High",
        # "prev_high",
        # "prev_low",
        # "prev_close",
        "prev_range",
        "entry_20",
        "entry_40",
        "Buy/Sell",
        "Entry",
        "Direction",
        "Close",
        "Result"
    ]
]

print(result_df.to_string(index=False))