# Changelog

## 0.1.0 - Initial
- Added `Architecture.md` with full plan and constraints.
- Scaffolded PyQt6 app structure + theme (QSS + palette).
- Implemented Candlestick renderer with LOD + volume overlay.
- Implemented SQLite cache schema for OHLCV and symbol list.
- Added Binance data provider (klines + symbol list).
- Wired ChartView with symbol/timeframe UI, background fetch, and Load More backfill.
- Surfaced fetch, symbol list, and render errors in the error dock.
- Made symbol list loading non-blocking.
- Added Binance retry-once for network failures.
- Added `Readme.md` and `Changelog.md`.

