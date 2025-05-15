# profit_calculator.py — handles profitability logic, normalization, and slippage simulation

from web3 import Web3

# === PROFIT CALCULATION ===
def calculate_profit(row, pool_data, gas_price, variant, eth_usdt_price, amount_in_usdt):
    pool_id = Web3.to_checksum_address(row["Uniswap Pool ID"])
    data = pool_data.get(pool_id, {})
    uniswap_price = data.get("uniswap_price", 0)
    camelot_price = data.get("camelot_price", 0)
    if uniswap_price == 0 or camelot_price == 0:
        return 0

    token0_decimals = row["Token0 Decimals"]
    token1_decimals = row["Token1 Decimals"]

    normalized_uniswap_price = (uniswap_price ** 2) / (2 ** 192) * (10 ** (token0_decimals - token1_decimals))
    normalized_camelot_price = (camelot_price ** 2) / (2 ** 192) * (10 ** (token0_decimals - token1_decimals))

    if normalized_uniswap_price > 0 and normalized_camelot_price > 0:
        ratio = normalized_uniswap_price / normalized_camelot_price
        if ratio < 1/3 or ratio > 3:
            return 0

    amount_token0 = amount_in_usdt / row["Token0 to USDT Price"] if row["Token0 to USDT Price"] > 0 else 0
    amount_token1 = amount_in_usdt / row["Token1 to USDT Price"] if row["Token1 to USDT Price"] > 0 else 0

    token_in_price = token0_price = row["Token0 to USDT Price"]
    token1_price = row["Token1 to USDT Price"]

    if variant == "Uniswap → Camelot (Token0 → Token1)":
        amount_in = amount_token0
        price_in = normalized_uniswap_price
        price_out = 1 / normalized_camelot_price
        fee_in = row["Uniswap Fee"]
        fee_out = row["Camelot Fee"]
        token_in_price = token0_price

    elif variant == "Uniswap → Camelot (Token1 → Token0)":
        amount_in = amount_token1
        price_in = 1 / normalized_uniswap_price
        price_out = normalized_camelot_price
        fee_in = row["Uniswap Fee"]
        fee_out = row["Camelot Fee"]
        token_in_price = token1_price

    elif variant == "Camelot → Uniswap (Token0 → Token1)":
        amount_in = amount_token0
        price_in = normalized_camelot_price
        price_out = 1 / normalized_uniswap_price
        fee_in = row["Camelot Fee"]
        fee_out = row["Uniswap Fee"]
        token_in_price = token0_price

    elif variant == "Camelot → Uniswap (Token1 → Token0)":
        amount_in = amount_token1
        price_in = 1 / normalized_camelot_price
        price_out = normalized_uniswap_price
        fee_in = row["Camelot Fee"]
        fee_out = row["Uniswap Fee"]
        token_in_price = token1_price

    else:
        return 0

    amount_after_swap_1 = amount_in * price_in * (1 - fee_in / 100000)
    token_out_price = token0_price if "Token0" in variant else token1_price
    if token_out_price <= 0:
        return 0

    amount_after_swap_2 = amount_after_swap_1 * price_out * (1 - fee_out / 100000)
    gas_cost_eth = (450000 * gas_price) / 10**18
    gas_cost_usdt = gas_cost_eth * eth_usdt_price

    profit_usdt = (amount_after_swap_2 - amount_in) * token_in_price if token_in_price > 0 else 0
    net_profit = profit_usdt - gas_cost_usdt
    return net_profit


# === TVL PRE-FLIGHT FILTER ===
def pre_flight_check(row, pool_data, eth_usdt_price):
    pool_id = Web3.to_checksum_address(row["Uniswap Pool ID"])
    data = pool_data.get(pool_id)
    if not data:
        return False

    required_keys = [
        "token0_balance_uni", "token1_balance_uni",
        "token0_balance_cam", "token1_balance_cam"
    ]
    if not all(k in data for k in required_keys):
        return False

    try:
        token0_decimals = row["Token0 Decimals"]
        token1_decimals = row["Token1 Decimals"]
        token0_price = row["Token0 to USDT Price"]
        token1_price = row["Token1 to USDT Price"]

        token0_balance_uni = data["token0_balance_uni"] / (10 ** token0_decimals)
        token1_balance_uni = data["token1_balance_uni"] / (10 ** token1_decimals)
        token0_balance_cam = data["token0_balance_cam"] / (10 ** token0_decimals)
        token1_balance_cam = data["token1_balance_cam"] / (10 ** token1_decimals)

        tvl0_usd_uni = token0_balance_uni * token0_price
        tvl1_usd_uni = token1_balance_uni * token1_price
        tvl0_usd_cam = token0_balance_cam * token0_price
        tvl1_usd_cam = token1_balance_cam * token1_price

        return all(tvl >= 1500 for tvl in [tvl0_usd_uni, tvl1_usd_uni, tvl0_usd_cam, tvl1_usd_cam])

    except Exception:
        return False
