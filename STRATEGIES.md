# Strategy Execution + Backtesting Architecture

This doc defines a detailed architecture for strategy management, execution, and
backtesting, including a deep backtester integration.

## Goals (V2+)
- Hot-reload Python strategies with schema-defined params.
- Unified runner that supports backtest and paper/live simulation.
- Deterministic, reproducible results + full execution logs.
- Deep backtester for realistic fills, slippage, partials, and floating equity.
- X-axis linked equity + price (bar-by-bar visibility into risk).

## File structure (planned)
```
app/strategies/
  builtins/                 # optional shipped strategies
  custom/                   # user strategies

app/core/strategies/
  registry.py               # discovery + hot reload
  runtime.py                # ctx + event loop
  orders.py                 # order models + helpers
  broker.py                 # fill models, slippage, commission
  portfolio.py              # cash/equity/margin/exposure
  execution.py              # sim + paper execution paths
  backtest.py               # backtest runner (bar loop)
  report.py                 # serialize results into UI schema

app/core/strategies/deep/
  engine.py                 # deep backtest engine
  models.py                 # order/fill models
  risk.py                   # drawdown + exposure tracking
  metrics.py                # MAE/MFE + regime stats

app/ui/
  strategy_panel.py         # strategy list + params + run controls
  strategy_report.py        # trade list + equity curve + stats
  strategy_equity.py        # equity curve view (linked to chart)
  strategy_deep_report.py   # deep backtest diagnostics

app/data/
  strategy.sqlite           # runs, orders, trades, equity
```

## Strategy module contract
Each strategy is a single Python file with:
- `schema() -> dict`
  - id, name, inputs (int/float/bool/select), defaults, min/max
  - optional metadata: category, version, tags
- `on_init(ctx)`
- `on_bar(ctx, i)`  (i = bar index)
- optional:
  - `on_order(ctx, order)`
  - `on_trade(ctx, trade)`
  - `on_finish(ctx)`

Strategies are pure logic. Execution is handled by the runtime.

## Strategy context (ctx) API
`ctx` is the strategy runtime surface:

Data:
- `ctx.bars`: NumPy OHLCV arrays (time, open, high, low, close, volume)
- `ctx.time`: alias of `bars[:,0]`
- `ctx.close`, `ctx.open`, `ctx.high`, `ctx.low`, `ctx.volume`
- `ctx.ind`: indicator helper API (same as indicators)

Orders:
- `ctx.buy(size, price=None, type="market"|"limit"|"stop", tif="GTC")`
- `ctx.sell(...)`
- `ctx.cancel(order_id)`
- `ctx.flatten()`  (close position)

Position/portfolio:
- `ctx.position.size`, `ctx.position.entry_price`, `ctx.position.pnl`
- `ctx.portfolio.cash`, `ctx.portfolio.equity`, `ctx.portfolio.margin`
- `ctx.portfolio.exposure`, `ctx.portfolio.leverage`

Params/logging:
- `ctx.params` (resolved inputs)
- `ctx.logger.info/warn/error`
- `ctx.state` (strategy state dict persisted during run)

Sizing helpers:
- `ctx.size.fixed(amount)` (contracts/units)
- `ctx.size.percent_equity(pct)` (percent of equity)
- `ctx.size.risk(risk_pct, stop_distance)` (risk-based sizing)

## Execution modes
- **Backtest**: deterministic simulation over historical bars.
- **Paper**: live data feed, simulated orders and fills.
- **Live** (future): real broker/exchange execution.


## Paper mode realism

### Market data sources (paper/live realism)
- Funding rates: pull from exchange funding endpoints and apply on schedule.
- Fees: maker/taker schedule from exchange info; fallback to configured defaults.
- Order book: best bid/ask + depth snapshot for spread/depth slippage models.
- Trade prints: live trades for market-impact approximations.


### Slippage modeling options (paper/live simulation)
Slippage must be modeled. Options:
1) **Fixed bps** (default):
   - `slippage = price * bps`
2) **Spread-aware**:
   - Use best bid/ask from order book.
   - Buy fills at `ask + slip`, sell fills at `bid - slip`.
3) **Depth-aware (VWAP)**:
   - Walk the order book for order size.
   - Fill price = size-weighted average across levels.
4) **ATR-based**:
   - `slip = ATR * k` for volatility-scaled slippage.
5) **Latency model**:
   - Delay N bars; price at fill = open of delayed bar.

Fallbacks:
- If order book unavailable, use spread or fixed bps.
- If ATR unavailable, fall back to fixed bps.
 (funding/fees/slippage)
- Paper mode uses live data feed but simulates execution locally.
- Funding can be fetched from exchange endpoints (if available) and applied on schedule.
- Fees/slippage models are configurable per run; defaults mirror backtest.
- If exchange funding data is unavailable, fall back to configured static rates.
- Paper runs log all applied funding/fees to the run log for audit.

## Strategy management

### Discovery + hot reload
- Watch `app/strategies/builtins/*.py` + `app/strategies/custom/*.py`
- Debounce file events (300-800ms)
- Reload module -> validate schema -> update UI list
- If a running strategy changed, re-run with same params
- Errors go to error dock; last good run stays visible

### Parameter UI
- Auto-generate form from schema inputs.
- Per-strategy presets (save/restore).
- Reset-to-default action.
- Param changes trigger recompute in backtest mode.

### Execution logs
- Event stream captured in SQLite + file logs:
  - orders + order state transitions
  - fills (partial/full)
  - trades (entry/exit/MAE/MFE)
  - position changes
  - equity snapshots (floating equity)
  - risk metrics (drawdown, exposure)
  - errors/exceptions

## Backtesting architecture

### Data pipeline
- Uses existing cache + window loader.
- Runner requests required lookback; fetch if missing.
- Supports multi-timeframe requests (same rules as indicators).

### Execution model
- Default: signal on close, fill on next open.
- Configurable:
  - close-to-close fills
  - partial fills and partial closes
  - slippage models (bps, ATR-based, fixed ticks)
  - commission models (bps, fixed, per fill)
  - funding/fees by schedule
  - latency model (fill delay in bars)
  - spread-aware fills (optional)
  - position sizing modes (fixed, % equity, risk-based)
  - per-strategy order attribution (track exact fills per strategy)

### Outputs
- Equity curve (bar-by-bar, floating equity)
- Trade log (entry/exit, MAE/MFE, PnL)
- Drawdown series
- Per-bar exposure + margin usage

## Deep backtester

The deep backtester is a custom engine built to model real exposure, floating equity,
fees, slippage, partial fills, and realistic order lifecycle behavior.

### Architecture (custom)
Core modules (custom engine only):
- `deep_backtest.py`: orchestration + simulation loop
- `execution.py`: order matching + fill logic
- `broker.py`: slippage/commission/funding models
- `portfolio.py`: cash/equity/margin/exposure accounting
- `orders.py`: order/state models
- `report.py`: results normalization + export

Data flow:
1) Load bars (window + lookback) -> normalize to NumPy arrays.
2) Initialize portfolio state (cash, leverage, margin).
3) Run bar loop (per-bar simulation):
   - process pending orders
   - apply fills
   - update position + PnL
   - update floating equity
   - capture snapshots + logs
4) Finalize run report (equity curve + stats + trades).

### Order lifecycle
- Order states: NEW -> ACTIVE -> FILLED/PARTIAL/CANCELED/EXPIRED
- Market: fills at next open (default)
- Limit: fills if bar trades through limit; gap fills at open
- Stop: triggers if bar trades through stop; fill at open
- Stop-limit: stop triggers, then limit logic applies

### Fill pipeline
1) Apply slippage model
2) Apply commission model
3) Apply funding (if interval boundary)
4) Update portfolio + position

### Portfolio accounting
- Average price position accounting
- Floating equity updated every bar
- Drawdown tracked from equity curve
- Exposure + margin tracked per bar

### Determinism guardrails
- All calculations are pure functions of inputs
- Same inputs produce same outputs
- No random seeds or external dependencies

### Output schema
- Orders, trades, equity curve, drawdown, exposure
- Designed to support chart-linked equity

### Optional Backtrader adapter (deferred)
- Possible future integration, but not part of V2 core

## Execution pipeline (high-level)
1) Strategy selected + params resolved (schema defaults applied).
2) Runtime loads bars (window + lookback); MTF requests fetched if needed.
3) Initialize portfolio state (cash, leverage, margin rules).
4) Bar loop:
   - process open orders
   - evaluate signals (strategy on_bar)
   - apply fills (slippage/fees/funding)
   - update position + floating equity
   - attribute fills to strategy (per-strategy position ledger)
   - snapshot logs + metrics
5) Finalize results (trades, equity curve, drawdown, exposure).
6) Render reports (chart overlays + stats) and persist to SQLite.


## Persistence (SQLite)
- `strategy_runs` (run id, strategy id, params, start/end, status)
- `strategy_orders` (run id, order details)
- `strategy_trades` (run id, trade details)
- `equity_curve` (run id, ts, equity)

## UI integration
- Strategy dock for:
  - active strategy list
  - params
  - run controls (start/stop/reset)
- Backtest report panel:
  - stats
  - trade list
  - equity curve pane
  - floating equity overlay on chart


## Strategy overlays (chart rendering)
Strategy results should render directly on the chart using an overlay renderer:
- Entry markers (buy/sell) with optional price + size label.
- Exit markers with PnL label.
- Optional stop/target level lines (dashed).
- Trade hover tooltips (entry, exit, MAE/MFE, duration).
- Click a trade in report -> jump to chart + highlight trade path.

Implementation:
- Extend report schema with `markers`, `levels`, and `trade_spans`.
- Add a `StrategyOverlayRenderer` similar to indicator renderer.
- Overlays live on price pane only (initially).

## Execution plan (phased)
1) Strategy registry + hot reload (schema discovery + validation).
2) Strategy runtime + ctx API (bars, params, logging, state).
3) Orders + portfolio accounting (fills, fees, slippage, funding).
4) Base backtest loop + result schema (equity, trades, exposure).
5) Strategy UI (list, params, run controls, logs).
6) Strategy overlay renderer (entries/exits, stop/target lines, tooltips).
7) Thorough backtest validation + trusted community testers.
8) Deep backtester engine (floating equity, diagnostics, order lifecycle).
9) Market realism (order book, funding fetch, trade prints).
10) Multi-timeframe + advanced risk metrics.



## Risk model (engine-level guards)
- Max drawdown cutoff (halt strategy/run).
- Max leverage cap.
- Max open trades / positions.
- Daily loss limit (optional).

## Run configuration schema (planned)
Each run stores a config blob:
- symbol(s), timeframe(s), date range
- initial cash, leverage
- fill model (close->open / close->close)
- fee model + slippage model
- funding schedule (if enabled)
- sizing model (fixed/%/risk)
  - sizing close policy (exact entry size vs percent equity on exit)

## Results schema (planned)
- trades: entry/exit, size, pnl, MAE/MFE, duration
- equity curve: ts, equity, exposure, drawdown
- orders: order lifecycle events

## Testing + validation
- Golden tests for fill logic (market/limit/stop gaps).
- Determinism tests (same inputs -> same outputs).
- Equity curve vs trade-equity checks.

## Multi-symbol (future)
- Unified portfolio across symbols.
- Exposure aggregation and risk limits per symbol.


## V3 plan: portfolio backtesting (multi-symbol + multi-strategy)
- Run multiple strategies across multiple symbols with shared capital.
- Portfolio-level risk controls (max exposure, max drawdown, sector caps).
- Cross-strategy conflict resolution (order priority, margin contention).
- Multi-strategy netting (record per-strategy fills, execute delta at broker).
- Unified equity curve + per-strategy attribution.
- Correlation metrics + portfolio stress testing.
- Portfolio replay mode (chart + equity synced across symbols).


## V3 scope (deferred from V2)
- Cross-strategy execution scheduling and contention rules.
- Portfolio delta execution (multi-strategy netting to a single order stream).
- Advanced risk attribution (per-strategy contribution, correlation matrix).
- Parameter optimization / sweeps (grid + optimizer runs).
- Walk-forward analysis (rolling train/test windows).
- Monte Carlo / stress tests (randomized fills, regime shifts).
- Live execution adapters (real broker/exchange routing).
- Multi-account / multi-wallet simulations
- Replay mode (drive chart + equity playback from backtest)
 - Deep backtester as a separate program module (data bank + batch runs)

## Open questions
- Gap handling for stop/limit orders? Options: fill at bar open vs fill at trigger price.
- Order priority when multiple triggers hit in the same bar? Options: stop > limit > market vs FIFO by submission time.
- Same-bar fills allowed? Options: allow close-to-close execution vs always next bar.
- Position sizing helpers? Options: fixed size, percent of equity, ATR-based risk sizing.
- Percent-of-equity exit sizing? Options: close exact entry size vs recompute from current equity.
- Time-in-force support? Options: GTC only vs add IOC/FOK.
- Funding schedule source/refresh rate? Options: cached per interval vs live polling.
- Paper mode realism? Options: always use order book depth (VWAP) vs fall back to fixed bps when depth unavailable.
- Max bars per run? Options: fixed cap vs adaptive cap based on machine performance.
- Log granularity? Options: full per-bar logging vs sampled snapshots (e.g., every N bars).
- Symbol metadata source? Options: exchange contract info vs manual overrides.
- Strategy state persistence? Options: persist ctx.state across runs vs reset each run.


## Run config example (JSON)
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "start": 1700000000000,
  "end": 1701000000000,
  "initial_cash": 10000,
  "leverage": 1,
  "fill_model": "close_to_open",
  "commission_bps": 4,
  "slippage_bps": 2,
  "funding": {"enabled": true, "rate": 0.0},
  "sizing": {"type": "percent_equity", "value": 0.1}
}
```

## Order state diagram (simple)
```
NEW -> ACTIVE -> PARTIAL -> FILLED
  \-> CANCELED
  \-> EXPIRED
```

## Metrics list (planned)
- Total return
- Max drawdown
- Win rate
- Profit factor
- Sharpe / Sortino
- Expectancy per trade
- MAE/MFE averages
- Exposure / time in market

## Example strategy (simple EMA cross)
```python
def schema():
    return {
        "id": "ema_cross",
        "name": "EMA Cross",
        "inputs": {
            "fast": {"type": "int", "default": 12, "min": 1, "max": 200},
            "slow": {"type": "int", "default": 26, "min": 1, "max": 200},
            "size": {"type": "float", "default": 1.0, "min": 0.1, "max": 10.0}
        }
    }

def on_init(ctx):
    pass

def on_bar(ctx, i):
    close = ctx.close
    fast = ctx.ind.ema(close, int(ctx.params["fast"]))
    slow = ctx.ind.ema(close, int(ctx.params["slow"]))

    if i < 1:
        return

    if fast[i] > slow[i] and fast[i-1] <= slow[i-1]:
        ctx.buy(ctx.params["size"])
    if fast[i] < slow[i] and fast[i-1] >= slow[i-1]:
        ctx.sell(ctx.params["size"])
```
