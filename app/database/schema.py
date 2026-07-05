CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_time TEXT NOT NULL,
    scan_type TEXT NOT NULL,
    total_stocks INTEGER DEFAULT 0,
    shortlisted INTEGER DEFAULT 0,
    status TEXT DEFAULT 'success',
    duration_seconds REAL DEFAULT 0,
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now', '+5:30'))
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER,
    symbol TEXT NOT NULL,
    scan_time TEXT NOT NULL,
    score REAL,
    confidence REAL,
    direction TEXT,
    entry_price REAL,
    stop_loss REAL,
    target_1 REAL,
    target_2 REAL,
    cmp REAL,
    atr REAL,
    volume_ratio REAL,
    rsi REAL,
    adx REAL,
    pcr REAL,
    oi_change INTEGER,
    iv REAL,
    sector TEXT,
    strategy TEXT,
    pattern_detected TEXT,
    expected_move_pct REAL,
    risk_reward REAL,
    position_size INTEGER,
    catalyst TEXT,
    bollinger_squeeze INTEGER DEFAULT 0,
    nr_detected INTEGER DEFAULT 0,
    breakout_proximity REAL,
    chart_path TEXT,
    created_at TEXT DEFAULT (datetime('now', '+5:30')),
    FOREIGN KEY (scan_id) REFERENCES scan_history(id)
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    direction TEXT,
    entry_price REAL,
    exit_price REAL,
    quantity INTEGER,
    entry_time TEXT,
    exit_time TEXT,
    pnl REAL,
    pnl_pct REAL,
    status TEXT DEFAULT 'open',
    strategy TEXT,
    scan_id INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', '+5:30')),
    FOREIGN KEY (scan_id) REFERENCES scan_history(id)
);

CREATE TABLE IF NOT EXISTS performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    total_scans INTEGER DEFAULT 0,
    total_signals INTEGER DEFAULT 0,
    bullish_count INTEGER DEFAULT 0,
    bearish_count INTEGER DEFAULT 0,
    avg_score REAL DEFAULT 0,
    top_symbol TEXT,
    best_score REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', '+5:30'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    message TEXT,
    status TEXT DEFAULT 'sent',
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now', '+5:30'))
);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    error_type TEXT,
    message TEXT,
    traceback TEXT,
    created_at TEXT DEFAULT (datetime('now', '+5:30'))
);

CREATE TABLE IF NOT EXISTS backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    strategy TEXT,
    start_date TEXT,
    end_date TEXT,
    total_trades INTEGER,
    win_rate REAL,
    total_pnl REAL,
    max_drawdown REAL,
    sharpe_ratio REAL,
    config_json TEXT,
    created_at TEXT DEFAULT (datetime('now', '+5:30'))
);
