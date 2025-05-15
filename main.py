# MAIN MODULE (formerly Ok-bitok.py)
# This script coordinates all core logic: fetching prices, finding arbitrage, and executing atomic transactions

from price_fetcher import get_pool_data_multicall, get_gas_price, load_pools, get_web3_ws
from profit_calculator import calculate_profit, pre_flight_check
from pool_filter import log_latency
from arb_executor import send_arbitrage_tx

from web3 import Web3
import pandas as pd
import os
import time
import random
import csv

# === CONFIG ===
UNISWAP_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
CAMELOT_ROUTER = "0x1F721E2E82F6676FCE4eA07A5958cF098D339e18"
MULTICALL_ADDRESS = "0x842eC2c7D803033Edf55E478F461FC547Bc54EB2"
ALLOWED_TOKENS = ["0x82af49447d8a07e3bd95bd0d56f35241523fbab1"]
MIN_TVL_THRESHOLD = 1500
amount_in_usdt = 100
output_log = "arbitrage_log.csv"

iteration_count = 0
revert_counter, banned_pools, revert_last_block = {}, {}, {}
REVERT_FILTER_ENABLED = True
MAX_REVERTS_PER_POOL, REVERT_BAN_BLOCKS, REVERT_RESET_BLOCKS = 2, 150, 150


# === TX BUILDING ===
def prepare_tx_data(row, variant):
    uni_first = "Uniswap" in variant.split("→")[0]
    routerA = UNISWAP_ROUTER if uni_first else CAMELOT_ROUTER
    routerB = CAMELOT_ROUTER if uni_first else UNISWAP_ROUTER
    token_in_side, token_out_side = variant.split("(")[1].split(")")[0].strip().split("→")
    tokenIn = row["Token0 ID"] if token_in_side.strip() == "Token0" else row["Token1 ID"]
    tokenOut = row["Token0 ID"] if token_out_side.strip() == "Token0" else row["Token1 ID"]
    feeA = int(row["Uniswap Fee"]) if routerA == UNISWAP_ROUTER else 0
    feeB = int(row["Uniswap Fee"]) if routerB == UNISWAP_ROUTER else 0
    token_price = row[f"{token_in_side.strip()} to USDT Price"]
    token_decimals = row[f"{token_in_side.strip()} Decimals"]
    amount_in = int((amount_in_usdt / token_price) * (10 ** token_decimals))
    return dict(routerA=routerA, routerB=routerB, tokenIn=tokenIn, tokenOut=tokenOut, feeA=feeA, feeB=feeB, amountIn=amount_in)


# === ARBITRAGE SCANNER ===
def find_arbitrage_opportunities(pools, pool_data, gas_price, eth_usdt_price, latest_block_number, web3):
    global iteration_count
    opportunities = []

    for _, row in pools.iterrows():
        if not pre_flight_check(row, pool_data, eth_usdt_price):
            continue
        for variant in [
            "Uniswap → Camelot (Token0 → Token1)", "Uniswap → Camelot (Token1 → Token0)",
            "Camelot → Uniswap (Token0 → Token1)", "Camelot → Uniswap (Token1 → Token0)"
        ]:
            profit = calculate_profit(row, pool_data, gas_price, variant, eth_usdt_price, amount_in_usdt)
            token_in_id = row["Token0 ID"] if "Token0" in variant else row["Token1 ID"]
            if token_in_id.lower() not in [t.lower() for t in ALLOWED_TOKENS]:
                continue
            if profit > 0.1:
                opportunities.append([row["Token0 Symbol"], row["Token1 Symbol"], variant, profit, latest_block_number, row["Uniswap Pool ID"], row["Camelot Pool ID"]])

    if not opportunities:
        iteration_count += 1
        return

    df = pd.DataFrame(opportunities, columns=["Token0", "Token1", "Variant", "Profit", "Block", "Uniswap Pool ID", "Camelot Pool ID"])
    df = df.sort_values(by="Profit", ascending=False)
    df.iloc[[0]].to_csv(output_log, mode="a", header=not os.path.exists(output_log), index=False)

    for _, best_row in df.iterrows():
        row_data = pools[(pools["Uniswap Pool ID"] == best_row["Uniswap Pool ID"]) & (pools["Camelot Pool ID"] == best_row["Camelot Pool ID"])].iloc[0]
        token_in_side = best_row["Variant"].split("(")[1].split(")")[0].strip().split("→")[0].strip()
        token_in_id = row_data["Token0 ID"] if token_in_side == "Token0" else row_data["Token1 ID"]
        pool_key = (Web3.to_checksum_address(row_data["Uniswap Pool ID"]), Web3.to_checksum_address(row_data["Camelot Pool ID"]))
        ban_block = banned_pools.get(pool_key)
        if ban_block and latest_block_number < ban_block:
            continue

        tx_data = prepare_tx_data(row_data, best_row["Variant"])
        tx_hash = send_arbitrage_tx(**tx_data)
        if tx_hash:
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            if receipt["status"] == 0:
                revert_counter[pool_key] = revert_counter.get(pool_key, 0) + 1
                revert_last_block[pool_key] = latest_block_number
                if revert_counter[pool_key] >= MAX_REVERTS_PER_POOL:
                    banned_pools[pool_key] = latest_block_number + REVERT_BAN_BLOCKS
                    revert_counter[pool_key] = 0
            else:
                revert_counter[pool_key] = 0
        break

    iteration_count += 1


# === ENTRY POINT ===
if __name__ == "__main__":
    web3 = get_web3_ws()
    latest_block_number = web3.eth.block_number

    pools, eth_usdt_price = load_pools()
    gas_price = get_gas_price(web3)
    pool_data = get_pool_data_multicall(pools, web3)
    find_arbitrage_opportunities(pools, pool_data, gas_price, eth_usdt_price, latest_block_number, web3)
    log_latency(0, 0, 0)  # mocked for now

    def subscribe_new_blocks():
        global latest_block_number, web3
        block_filter = web3.eth.filter("latest")
        while True:
            try:
                new_entries = block_filter.get_new_entries()
                if new_entries:
                    latest_block = web3.eth.get_block(new_entries[-1])
                    latest_block_number = latest_block["number"]
                    pools, eth_usdt_price = load_pools()
                    gas_price = get_gas_price(web3)
                    pool_data = get_pool_data_multicall(pools, web3)
                    find_arbitrage_opportunities(pools, pool_data, gas_price, eth_usdt_price, latest_block_number, web3)
            except Exception as e:
                print(f"[WS RECONNECT] {e}")
                web3 = get_web3_ws()
                block_filter = web3.eth.filter("latest")

    subscribe_new_blocks()
