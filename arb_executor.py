# arb_executor.py — prepares and sends arbitrage tx via AtomicTerminator

from web3 import Web3
import json
import os
from dotenv import load_dotenv
load_dotenv()

# === Config ===
ARB_RPC = os.getenv("ARB_RPC", "https://arb1.arbitrum.io/rpc")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")  # ⚠️ Set via .env
ACCOUNT = os.getenv("ACCOUNT")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

last_used_nonce = None

# === ABI for AtomicTerminator ===
contract_abi = json.loads("""
[
  {
    "inputs": [
      {"internalType": "address", "name": "routerA", "type": "address"},
      {"internalType": "address", "name": "routerB", "type": "address"},
      {"internalType": "address", "name": "tokenIn", "type": "address"},
      {"internalType": "address", "name": "tokenOut", "type": "address"},
      {"internalType": "uint24", "name": "feeA", "type": "uint24"},
      {"internalType": "uint24", "name": "feeB", "type": "uint24"},
      {"internalType": "uint256", "name": "amountIn", "type": "uint256"}
    ],
    "name": "executeArbitrage",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
]
""")

# === Web3 Initialization ===
web3 = Web3(Web3.HTTPProvider(ARB_RPC))
assert web3.is_connected(), "[ERROR] Failed to connect to Arbitrum RPC"

contract = web3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=contract_abi)

def send_arbitrage_tx(routerA, routerB, tokenIn, tokenOut, feeA, feeB, amountIn):
    global last_used_nonce
    try:
        current_nonce = web3.eth.get_transaction_count(ACCOUNT)
        nonce = current_nonce if last_used_nonce is None else max(current_nonce, last_used_nonce + 1)

        routerA = Web3.to_checksum_address(routerA)
        routerB = Web3.to_checksum_address(routerB)
        tokenIn = Web3.to_checksum_address(tokenIn)
        tokenOut = Web3.to_checksum_address(tokenOut)

        tx = contract.functions.executeArbitrage(
            routerA, routerB, tokenIn, tokenOut, feeA, feeB, amountIn
        ).build_transaction({
            'from': ACCOUNT,
            'nonce': nonce,
            'gas': 550000,
            'gasPrice': web3.to_wei('0.2', 'gwei')
        })

        signed_tx = web3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        last_used_nonce = nonce

        print(f"[TX] Sent arbitrage tx: {web3.to_hex(tx_hash)}")
        return tx_hash

    except Exception as e:
        print(f"[TX ERROR] Failed to send arbitrage tx: {e}")
        return None
