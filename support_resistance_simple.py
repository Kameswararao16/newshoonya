import os
import glob
import pandas as pd


DATA_FOLDER = "nifty100_data"
LOOKBACK = 60

MERGE_FACTOR = 0.1

# =====================================================
# Create levels only from HIGH and LOW
# =====================================================

def build_levels(df, merge_step):

    prices = []

    # only High and Low create levels
    prices.extend(df["High"].tolist())
    prices.extend(df["Low"].tolist())

    prices = sorted(prices)

    levels = []

    for price in prices:

        if not levels:

            levels.append({
                "level": price,
                "count": 1
            })

        else:

            last = levels[-1]

            if abs(price - last["level"]) <= merge_step:

                old = last["count"]

                last["level"] = (
                    (last["level"] * old) + price
                ) / (old + 1)

                last["count"] += 1

            else:

                levels.append({
                    "level": price,
                    "count": 1
                })


    return levels



# =====================================================
# Add OPEN/CLOSE hits only
# =====================================================

def add_open_close_hits(df, levels, merge_step):

    for _, row in df.iterrows():

        values = [
            row["Open"],
            row["Close"]
        ]

        for value in values:

            for level in levels:

                if abs(value - level["level"]) <= merge_step:

                    level["count"] += 1

                    break


    for x in levels:
        x["level"] = round(x["level"], 2)

    return levels



# =====================================================
# Support / Resistance
# =====================================================

def get_support_resistance(levels, close):

    supports = [
        x for x in levels
        if x["level"] < close
    ]


    resistances = [
        x for x in levels
        if x["level"] > close
    ]


    # Get all supports below close, sort by level, take top 50, then sort by count and take top 5
    supports = sorted(
        supports,
        key=lambda x:x["level"],
        reverse=True
    )[:10]
    # Get top 5 by count
    supports = sorted(
        supports,
        key=lambda x: x["count"],
        reverse=True
    )[:5]
    supports = sorted(
        supports,
        key=lambda x: x["level"],
        reverse=False
    )[:5]
    # Get all resistances above close, sort by level, take top 50, then sort by count and take top 5
    resistances = sorted(
        resistances,
        key=lambda x:x["level"]
    )[:10]
    # Get top 5 by count
    resistances = sorted(
        resistances,
        key=lambda x: x["count"],
        reverse=True
    )[:5]
    resistances = sorted(
        resistances,
        key=lambda x: x["level"],
        reverse=False
    )[:5]

    return supports,resistances

#=========================================================
# Cluster levels that are close to each other
#=========================================================
def get_merge_step(df, lookback=14, factor=0.25):

    recent = df.tail(lookback)

    avg_range = (
        recent["High"] - recent["Low"]
    ).mean()

    merge_step = avg_range * factor

    return round(merge_step, 2)

# =====================================================
# Process one stock
# =====================================================

def process_stock(file):

    stock = os.path.basename(file).replace(".csv","")


    df = pd.read_csv(file)


    required = [
        "Open",
        "High",
        "Low",
        "Close"
    ]


    if not all(c in df.columns for c in required):
        return None


    df = df.tail(LOOKBACK)


    close = float(df.iloc[-1]["Close"])
    merge_step = get_merge_step(
        df,
        lookback=14,
        factor=MERGE_FACTOR
    )


    # High/Low only
    levels = build_levels(
        df,
        merge_step
    )


    # add confirmation from Open/Close
    levels = add_open_close_hits(
        df,
        levels,
        merge_step
    )


    supports,resistances = get_support_resistance(
        levels,
        close
    )


    result = {
        "Stock":stock,
        "Close":round(close,2)
    }


    # supports
    for i in range(5):

        if i < len(supports):

            result[f"S{i+1}"] = supports[i]["level"]
            result[f"S{i+1}_Hits"] = supports[i]["count"]

        else:

            result[f"S{i+1}"] = None
            result[f"S{i+1}_Hits"] = None



    # resistances

    for i in range(5):

        if i < len(resistances):

            result[f"R{i+1}"] = resistances[i]["level"]
            result[f"R{i+1}_Hits"] = resistances[i]["count"]

        else:

            result[f"R{i+1}"] = None
            result[f"R{i+1}_Hits"] = None


    return result



# =====================================================
# MAIN
# =====================================================

def main():

    files = glob.glob(
        os.path.join(
            DATA_FOLDER,
            "*.csv"
        )
    )


    output = []


    for file in sorted(files):

        try:

            row = process_stock(file)

            if row:
                output.append(row)

                print(
                    row["Stock"],
                    "Close",
                    row["Close"],
                    "S1",
                    row["S1"],
                    "R1",
                    row["R1"]
                )

        except Exception as e:

            print(file,e)



    result = pd.DataFrame(output)


    result.sort_values(
        "Stock",
        inplace=True
    )


    result.to_csv(
        "support_resistance_levels.csv",
        index=False
    )


    print("\nCreated support_resistance_levels.csv")



if __name__ == "__main__":
    main()