// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

using SafeERC20 for IERC20;

/// @title AtomicTerminator
/// @notice Executes two-step atomic arbitrage between two DEX routers (e.g., Uniswap and Camelot)
/// @dev Only the contract owner can trigger execution, supports fail-safe try/catch on both swaps
contract AtomicTerminator is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    /// @notice Immutable router addresses for Camelot and Uniswap
    address public immutable camelotRouter;
    address public immutable uniswapRouter;

    /// @notice Emitted when arbitrage is successfully executed
    event ArbitrageExecuted(uint256 amountIn, uint256 amountMid, uint256 amountOut, uint256 profit);

    constructor(address _camelotRouter, address _uniswapRouter) Ownable(msg.sender) {
        camelotRouter = _camelotRouter;
        uniswapRouter = _uniswapRouter;
    }

    /// @notice Executes atomic arbitrage across two routers
    /// @param routerA First router (tokenIn -> tokenOut)
    /// @param routerB Second router (tokenOut -> tokenIn)
    /// @param tokenIn Initial token
    /// @param tokenOut Intermediate token
    /// @param feeA Pool fee for routerA (Uniswap only)
    /// @param feeB Pool fee for routerB (Uniswap only)
    /// @param amountIn Amount of tokenIn to start arbitrage with
    function executeArbitrage(
        address routerA,
        address routerB,
        address tokenIn,
        address tokenOut,
        uint24 feeA,
        uint24 feeB,
        uint256 amountIn
    ) external nonReentrant onlyOwner {
        uint256 initialBalance = IERC20(tokenIn).balanceOf(address(this));
        uint256 amountMid;

        // First swap: tokenIn -> tokenOut
        if (routerA == camelotRouter) {
            try ICamelotRouter(routerA).exactInputSingle(
                ICamelotRouter.ExactInputSingleParams({
                    tokenIn: tokenIn,
                    tokenOut: tokenOut,
                    recipient: address(this),
                    deadline: block.timestamp + 60,
                    amountIn: amountIn,
                    amountOutMinimum: 0,
                    limitSqrtPrice: 0
                })
            ) returns (uint256 mid) {
                amountMid = mid;
            } catch Error(string memory reason) {
                revert(reason);
            } catch {
                revert("Swap A failed");
            }
        } else {
            try ISwapRouter(routerA).exactInputSingle(
                ISwapRouter.ExactInputSingleParams({
                    tokenIn: tokenIn,
                    tokenOut: tokenOut,
                    fee: feeA,
                    recipient: address(this),
                    deadline: block.timestamp + 60,
                    amountIn: amountIn,
                    amountOutMinimum: 0,
                    sqrtPriceLimitX96: 0
                })
            ) returns (uint256 mid) {
                amountMid = mid;
            } catch Error(string memory reason) {
                revert(reason);
            } catch {
                revert("Swap A failed");
            }
        }

        uint256 amountOut;

        // Second swap: tokenOut -> tokenIn
        if (routerB == camelotRouter) {
            try ICamelotRouter(routerB).exactInputSingle(
                ICamelotRouter.ExactInputSingleParams({
                    tokenIn: tokenOut,
                    tokenOut: tokenIn,
                    recipient: address(this),
                    deadline: block.timestamp + 60,
                    amountIn: amountMid,
                    amountOutMinimum: 0,
                    limitSqrtPrice: 0
                })
            ) returns (uint256 out) {
                amountOut = out;
            } catch Error(string memory reason) {
                revert(reason);
            } catch {
                revert("Swap B failed");
            }
        } else {
            try ISwapRouter(routerB).exactInputSingle(
                ISwapRouter.ExactInputSingleParams({
                    tokenIn: tokenOut,
                    tokenOut: tokenIn,
                    fee: feeB,
                    recipient: address(this),
                    deadline: block.timestamp + 60,
                    amountIn: amountMid,
                    amountOutMinimum: 0,
                    sqrtPriceLimitX96: 0
                })
            ) returns (uint256 out) {
                amountOut = out;
            } catch Error(string memory reason) {
                revert(reason);
            } catch {
                revert("Swap B failed");
            }
        }

        uint256 finalBalance = IERC20(tokenIn).balanceOf(address(this));
        int256 profit = int256(finalBalance) - int256(initialBalance);

        require(profit > 0, "No profit");
        emit ArbitrageExecuted(amountIn, amountMid, amountOut, uint256(profit));
    }

    /// @notice Approves max allowance of token for a router
    function approveToken(address token, address router) external onlyOwner {
        IERC20(token).approve(router, type(uint256).max);
    }

    /// @notice Withdraws tokens from contract to specified address
    function withdraw(address token, uint256 amount, address to) external onlyOwner {
        IERC20(token).safeTransfer(to, amount);
    }
}

/// @dev Interface for Uniswap V3-style routers
interface ISwapRouter {
    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint24 fee;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 sqrtPriceLimitX96;
    }
    function exactInputSingle(ExactInputSingleParams calldata params) external returns (uint256 amountOut);
}

/// @dev Interface for Camelot-style routers
interface ICamelotRouter {
    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 limitSqrtPrice;
    }
    function exactInputSingle(ExactInputSingleParams calldata params) external returns (uint256 amountOut);
}
