import sqlite3
import pandas as pd

conn = sqlite3.connect('data_storage/bot_data.db')
print("--- TRADES ---")
print(pd.read_sql_query('SELECT * FROM trades', conn))
print("\n--- ACTIVE POSITIONS ---")
print(pd.read_sql_query('SELECT * FROM active_positions', conn))
print("\n--- WALLET ---")
print(pd.read_sql_query('SELECT * FROM wallet', conn))
print("\n--- BOT CONFIG ---")
print(pd.read_sql_query('SELECT * FROM bot_config', conn))
