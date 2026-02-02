from __future__ import annotations

import sqlite3
from typing import Any, Dict, Iterable, List, Optional


class StrategyStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at INTEGER,
                    strategy_id TEXT,
                    strategy_name TEXT,
                    strategy_path TEXT,
                    symbol TEXT,
                    timeframe TEXT,
                    start_ts INTEGER,
                    end_ts INTEGER,
                    warmup_bars INTEGER,
                    initial_cash REAL,
                    leverage REAL,
                    commission_bps REAL,
                    slippage_bps REAL,
                    status TEXT,
                    params_json TEXT,
                    error_text TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    submitted_ts INTEGER,
                    fill_ts INTEGER,
                    side TEXT,
                    size REAL,
                    fill_price REAL,
                    fee REAL,
                    status TEXT,
                    reason TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    side TEXT,
                    size REAL,
                    entry_ts INTEGER,
                    entry_price REAL,
                    exit_ts INTEGER,
                    exit_price REAL,
                    pnl REAL,
                    fee_total REAL,
                    bars_held INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_equity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ts INTEGER,
                    equity REAL,
                    drawdown REAL,
                    position_size REAL,
                    price REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ts INTEGER,
                    level TEXT,
                    message TEXT,
                    bar_ts INTEGER
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_equity_run_ts ON strategy_equity (run_id, ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_orders_run_ts ON strategy_orders (run_id, submitted_ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_trades_run_ts ON strategy_trades (run_id, entry_ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_msgs_run_ts ON strategy_messages (run_id, ts)")

    def create_run(self, run: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO strategy_runs (
                    run_id, created_at, strategy_id, strategy_name, strategy_path,
                    symbol, timeframe, start_ts, end_ts, warmup_bars, initial_cash,
                    leverage, commission_bps, slippage_bps, status, params_json, error_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.get("run_id"), run.get("created_at"), run.get("strategy_id"), run.get("strategy_name"), run.get("strategy_path"),
                    run.get("symbol"), run.get("timeframe"), run.get("start_ts"), run.get("end_ts"), run.get("warmup_bars"),
                    run.get("initial_cash"), run.get("leverage"), run.get("commission_bps"), run.get("slippage_bps"),
                    run.get("status"), run.get("params_json"), run.get("error_text"),
                ),
            )

    def update_run_status(self, run_id: str, status: str, error_text: Optional[str] = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE strategy_runs SET status=?, error_text=? WHERE run_id=?",
                (status, error_text, run_id),
            )

    def insert_order_event(self, run_id: str, order: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO strategy_orders (
                    run_id, submitted_ts, fill_ts, side, size, fill_price, fee, status, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    order.get("submitted_ts"),
                    order.get("fill_ts"),
                    order.get("side"),
                    order.get("size"),
                    order.get("fill_price"),
                    order.get("fee"),
                    order.get("status"),
                    order.get("reason"),
                ),
            )

    def insert_trade(self, run_id: str, trade: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO strategy_trades (
                    run_id, side, size, entry_ts, entry_price, exit_ts, exit_price, pnl, fee_total, bars_held
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    trade.get("side"),
                    trade.get("size"),
                    trade.get("entry_ts"),
                    trade.get("entry_price"),
                    trade.get("exit_ts"),
                    trade.get("exit_price"),
                    trade.get("pnl"),
                    trade.get("fee_total"),
                    trade.get("bars_held"),
                ),
            )

    def insert_equity_point(self, run_id: str, point: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO strategy_equity (
                    run_id, ts, equity, drawdown, position_size, price
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    point.get("ts"),
                    point.get("equity"),
                    point.get("drawdown"),
                    point.get("position_size"),
                    point.get("price"),
                ),
            )

    def insert_equity_points(self, run_id: str, points: Iterable[Dict[str, Any]]) -> None:
        rows = [
            (
                run_id,
                p.get("ts"),
                p.get("equity"),
                p.get("drawdown"),
                p.get("position_size"),
                p.get("price"),
            )
            for p in points
        ]
        if not rows:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO strategy_equity (
                    run_id, ts, equity, drawdown, position_size, price
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def insert_orders(self, run_id: str, orders: Iterable[Dict[str, Any]]) -> None:
        rows = [
            (
                run_id,
                o.get("submitted_ts"),
                o.get("fill_ts"),
                o.get("side"),
                o.get("size"),
                o.get("fill_price"),
                o.get("fee"),
                o.get("status"),
                o.get("reason"),
            )
            for o in orders
        ]
        if not rows:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO strategy_orders (
                    run_id, submitted_ts, fill_ts, side, size, fill_price, fee, status, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def insert_trades(self, run_id: str, trades: Iterable[Dict[str, Any]]) -> None:
        rows = [
            (
                run_id,
                t.get("side"),
                t.get("size"),
                t.get("entry_ts"),
                t.get("entry_price"),
                t.get("exit_ts"),
                t.get("exit_price"),
                t.get("pnl"),
                t.get("fee_total"),
                t.get("bars_held"),
            )
            for t in trades
        ]
        if not rows:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO strategy_trades (
                    run_id, side, size, entry_ts, entry_price, exit_ts, exit_price, pnl, fee_total, bars_held
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def insert_messages(self, run_id: str, messages: Iterable[Dict[str, Any]]) -> None:
        rows = [
            (
                run_id,
                m.get("ts"),
                m.get("level"),
                m.get("message"),
                m.get("bar_ts"),
            )
            for m in messages
        ]
        if not rows:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO strategy_messages (
                    run_id, ts, level, message, bar_ts
                ) VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def insert_message(self, run_id: str, msg: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO strategy_messages (
                    run_id, ts, level, message, bar_ts
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, msg.get("ts"), msg.get("level"), msg.get("message"), msg.get("bar_ts")),
            )

    def load_latest_run_for(self, symbol: str, timeframe: str, strategy_id: str) -> Optional[str]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT run_id FROM strategy_runs
                WHERE symbol=? AND timeframe=? AND strategy_id=?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (symbol, timeframe, strategy_id),
            )
            row = cur.fetchone()
            if row:
                return row[0]
        return None
