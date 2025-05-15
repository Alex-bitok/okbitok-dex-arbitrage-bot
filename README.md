# Okbitok Arbitrage Bot — DEX Version

A professional-grade arbitrage bot for decentralized exchanges (Uniswap V3 and Camelot) on Arbitrum. Built for precision execution, slippage-aware profitability modeling, and atomic smart contract-based routing.

---

## Overview

This version of Okbitok is designed for two-hop arbitrage between Uniswap and Camelot. It uses normalized on-chain prices, gas-aware profit simulation, and an `AtomicTerminator` smart contract to ensure atomic execution. The bot is modular, configurable, and optimized for running on live networks.

---

## Features

* Arbitrage execution across Uniswap V3 and Camelot
* Real-time price tracking using WebSocket + Multicall
* Accurate sqrtPriceX96 decoding with decimal normalization
* Simulation of profit net of gas cost
* Smart contract-based execution with revert protection
* Pre-trade TVL filtering and token whitelisting
* Optional latency logging for optimization

---

## Contract

The `AtomicTerminator` contract executes two swaps in sequence:

1. `tokenIn` → `tokenOut` (via routerA)
2. `tokenOut` → `tokenIn` (via routerB)

Profit is validated on-chain by checking balance differences. Execution is permissioned and safe against reverts. Contract source is available in `contracts/AtomicTerminator.sol`.

---

## Architecture

* `main.py` — Entry point: coordinates block subscriptions and arbitrage loop
* `arb_executor.py` — Prepares and sends transactions to the contract
* `price_fetcher.py` — Multicall interface and pool data loading
* `profit_calculator.py` — Handles slippage-aware profit modeling and TVL checks
* `pool_filter.py` — Optional revert filter and latency CSV logger

---

## Usage

### Requirements

* Python 3.10+
* Packages: `web3`, `pandas`, `eth_abi`, `python-dotenv`

### Setup

1. Deploy the `AtomicTerminator` contract to Arbitrum
2. Create a `.env` file (see `.env.example`)
3. Place a valid `matching_pools.csv` with token pairs and pool metadata
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
5. Run the bot:

   ```bash
   python main.py
   ```

---

## Notes

* Only whitelisted tokens are used for execution
* No trade is executed unless simulated net profit > 0
* TVL threshold is enforced on both token sides and both pools
* Transactions are routed via the deployed smart contract
* Latency and arbitrage results are logged in CSV

---

## License

MIT License — free to use with attribution.

---

## Author

Alex Bel  —  [https://github.com/Alex-bitok](https://github.com/Alex-bitok)
