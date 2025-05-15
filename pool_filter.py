# pool_filter.py — optional helpers: latency logging, revert filter management

import os
import csv

def log_latency(load_latency, multicall_latency, find_arb_latency, filepath="latency_log.csv"):
    """Appends latency stats into a CSV file."""
    file_exists = os.path.exists(filepath)
    with open(filepath, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Load Latency (s)", "Multicall Latency (s)", "Find Arb Latency (s)"])
        writer.writerow([load_latency, multicall_latency, find_arb_latency])


# Optional: logic for managing revert bans across blocks

def update_revert_counters(latest_block_number, revert_counter, revert_last_block, banned_pools, RESET_BLOCKS, BAN_BLOCKS, MAX_REVERTS):
    """Handles automatic reset and banning of pools after too many reverts."""
    to_reset = []
    for pool_key, last_block in revert_last_block.items():
        if revert_counter.get(pool_key, 0) > 0 and latest_block_number - last_block >= RESET_BLOCKS:
            to_reset.append(pool_key)
    for pool_key in to_reset:
        revert_counter[pool_key] = 0

    # Handle new bans (done in main when tx fails)
    for pool_key, count in revert_counter.items():
        if count >= MAX_REVERTS:
            banned_pools[pool_key] = latest_block_number + BAN_BLOCKS
            revert_counter[pool_key] = 0


def is_pool_banned(pool_key, banned_pools, latest_block_number):
    """Checks if a pool is still under revert ban."""
    ban_block = banned_pools.get(pool_key)
    return ban_block and latest_block_number < ban_block
