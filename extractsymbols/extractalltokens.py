import pandas as pd

# Read the input CSV
df = pd.read_csv("NSEsymbols.csv")

# Keep only the required columns
output = df[[
    "Exchange",
    "Symbol",
    "TradingSymbol",
    "Token",
    "Instrument"
]]

# Write to a new CSV
output.to_csv("Extracted_Symbols.csv", index=False)

print("CSV file 'Extracted_Symbols.csv' created successfully.")