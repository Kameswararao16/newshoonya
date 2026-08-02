import pandas as pd
import zipfile
import requests
# ---------------Download file-------------------
url = "https://api.shoonya.com/NFO_symbols.txt.zip"
filename = "NFO_symbols.txt.zip"

response = requests.get(url, timeout=60)
response.raise_for_status()

with open(filename, "wb") as f:
    f.write(response.content)

print("Downloaded:", filename)

with zipfile.ZipFile("NFO_symbols.txt.zip") as z:
    z.extractall(".")

#--------------Prepare file-----------------------
NFO_FILE = "NFO_symbols.txt"
OUTPUT_FILE = "FNO_LotSize_Expiry.csv"

# Read Shoonya NFO symbol master
df = pd.read_csv(
    NFO_FILE,
    sep=",",
    low_memory=False
)

df.columns = df.columns.str.strip()

# Convert columns
df["Expiry"] = pd.to_datetime(
    df["Expiry"],
    errors="coerce"
)

df["StrikePrice"] = pd.to_numeric(
    df["StrikePrice"],
    errors="coerce"
)

today = pd.Timestamp.today()

# -------------------------------
# 1. Get upcoming Stock Futures
# -------------------------------

fut = df[
    # (df["Instrument"] == "FUTSTK") &
    (df["Expiry"] >= today)
].copy()

# nearest expiry
fut = fut.sort_values(
    ["Symbol", "Expiry"]
)

fut = fut.drop_duplicates(
    subset=["Symbol"],
    keep="first"
)

# -------------------------------
# 2. Calculate Strike Difference
# -------------------------------

opt = df[
    df["OptionType"].isin(["CE", "PE"])
].copy()


strike_diff = {}

for symbol, group in opt.groupby("Symbol"):

    strikes = sorted(
        group["StrikePrice"]
        .dropna()
        .unique()
    )

    if len(strikes) > 1:
        diff = min(
            b - a
            for a, b in zip(strikes, strikes[1:])
            if b - a > 0
        )

        strike_diff[symbol] = int(diff)


# -------------------------------
# 3. Merge Futures + Strike Diff
# -------------------------------

result = fut[
    ["Symbol", "Expiry", "LotSize"]
].copy()


result["StrikeDiff"] = result["Symbol"].map(
    strike_diff
)


# Format expiry like 29SEP26
result["Expiry"] = result["Expiry"].dt.strftime(
    "%d%b%y"
).str.upper()


# Save
result.to_csv(
    OUTPUT_FILE,
    index=False
)


print("Created:", OUTPUT_FILE)
