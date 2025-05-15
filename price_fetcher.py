# price_fetcher.py — responsible for price fetching, multicall, gas price and pool loading

import os
import time
import pandas as pd
from web3 import Web3
from eth_abi import decode

# === Constants ===
WSS_PROVIDERS = [
    "wss://arbitrum-mainnet.core.chainstack.com/fa34c578b02f22a93bdd5c733dc64fa5",
    "wss://arb-mainnet.g.alchemy.com/v2/qExQSGxnWrwwQa4bka8I2RAxpQsOsSCB"
]
MULTICALL_ADDRESS = "0x842eC2c7D803033Edf55E478F461FC547Bc54EB2"
MULTICALL_ABI = [{
    "constant": True,
    "inputs": [{
        "components": [
            {"name": "target", "type": "address"},
            {"name": "callData", "type": "bytes"}
        ],
        "name": "calls",
        "type": "tuple[]"
    }],
    "name": "aggregate",
    "outputs": [
        {"name": "blockNumber", "type": "uint256"},
        {"name": "returnData", "type": "bytes[]"}
    ],
    "stateMutability": "view",
    "type": "function"
}]

# === Gas caching ===
GAS_UPDATE_INTERVAL = 600
last_gas_update = time.time()
gas_price = None

def get_web3_ws():
    for wss in WSS_PROVIDERS:
        try:
            print(f"[WS DEBUG] Trying {wss}")
            web3_ws = Web3(Web3.LegacyWebSocketProvider(wss))
            _ = web3_ws.eth.get_block('latest')
            print(f"[WS] Connected via {wss}")
            return web3_ws
        except Exception as e:
            print(f"[WS ERROR] {wss} rejected: {e}")
            continue
    raise ConnectionError("No working WebSocket provider found.")

def get_gas_price(web3):
    global last_gas_update, gas_price
    now = time.time()
    if gas_price is None or now - last_gas_update > GAS_UPDATE_INTERVAL:
        block = web3.eth.get_block('latest')
        gas_price = block["baseFeePerGas"]
        last_gas_update = now
    return gas_price

def load_pools():
    pools_file = os.path.join(os.path.dirname(__file__), "matching_pools.csv")
    df = pd.read_csv(pools_file)
    df["Uniswap Pool ID"] = df["Uniswap Pool ID"].apply(Web3.to_checksum_address)
    df["Camelot Pool ID"] = df["Camelot Pool ID"].apply(Web3.to_checksum_address)
    eth_usdt_price = df["ETH_USDT"].iloc[0]
    return df, eth_usdt_price

def get_pool_data_multicall(pools, web3):
    multicall = web3.eth.contract(address=Web3.to_checksum_address(MULTICALL_ADDRESS), abi=MULTICALL_ABI)

    slot0_abi = [{"inputs": [], "name": "slot0", "outputs": [{"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"}], "stateMutability": "view", "type": "function"}]
    globalState_abi = [{"inputs": [], "name": "globalState", "outputs": [{"internalType": "uint160", "name": "price", "type": "uint160"}], "stateMutability": "view", "type": "function"}]
    erc20_abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "stateMutability": "view", "type": "function"}]

    uniswap_contract = web3.eth.contract(abi=slot0_abi)
    camelot_contract = web3.eth.contract(abi=globalState_abi)
    erc20_contract = web3.eth.contract(abi=erc20_abi)

    calls, pool_ids = [], []
    for _, row in pools.iterrows():
        pid_uni = Web3.to_checksum_address(row["Uniswap Pool ID"])
        pid_cam = Web3.to_checksum_address(row["Camelot Pool ID"])
        token0 = Web3.to_checksum_address(row["Token0 ID"])
        token1 = Web3.to_checksum_address(row["Token1 ID"])

        calls += [
            (pid_uni, uniswap_contract.functions.slot0()._encode_transaction_data()),
            (pid_cam, camelot_contract.functions.globalState()._encode_transaction_data()),
            (token0, erc20_contract.functions.balanceOf(pid_uni)._encode_transaction_data()),
            (token1, erc20_contract.functions.balanceOf(pid_uni)._encode_transaction_data()),
            (token0, erc20_contract.functions.balanceOf(pid_cam)._encode_transaction_data()),
            (token1, erc20_contract.functions.balanceOf(pid_cam)._encode_transaction_data())
        ]
        pool_ids.append((pid_uni, pid_cam, token0, token1))

    _, return_data = multicall.functions.aggregate(calls).call()

    pool_data = {}
    for i in range(0, len(return_data), 6):
        pool_id, camelot_id, token0, token1 = pool_ids[i // 6]
        pool_data[pool_id] = {
            "uniswap_price": decode(["uint160"], return_data[i])[0],
            "camelot_price": decode(["uint160"], return_data[i + 1])[0],
            "token0_balance_uni": decode(["uint256"], return_data[i + 2])[0],
            "token1_balance_uni": decode(["uint256"], return_data[i + 3])[0],
            "token0_balance_cam": decode(["uint256"], return_data[i + 4])[0],
            "token1_balance_cam": decode(["uint256"], return_data[i + 5])[0],
        }
    return pool_data
