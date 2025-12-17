import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any, List

DB_DIR = "data"
DB_NAME = os.path.join(DB_DIR, "alta_master.db")
os.makedirs(DB_DIR, exist_ok=True)


def _get_conn():
    return sqlite3.connect(DB_NAME, timeout=10)


def init_db():
    conn = _get_conn()
    c = conn.cursor()

    # Tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            decision_json TEXT,
            entry_price REAL,
            sl REAL,
            tp REAL,
            position_size REAL,
            reason TEXT,
            timestamp DATETIME,
            status TEXT DEFAULT 'OPEN',
            outcome_note TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS learning_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type TEXT,
            keyword TEXT,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


# --- HISTORY FUNCTIONS ---
def save_trade(symbol: str, decision: Dict[str, Any]) -> int:
    conn = _get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    entry = decision.get("entry_price") or (decision.get("risk") or {}).get("entry") or None
    sl = (decision.get("risk") or {}).get("stop_loss")
    tp = (decision.get("risk") or {}).get("take_profit")
    size = (decision.get("risk") or {}).get("position_size")
    reason = json.dumps({
        "technical": decision.get("technical") or {},
        "fundamental": decision.get("fundamental") or {},
        "anomaly": decision.get("anomaly") or {},
        "notes": decision.get("notes") or []
    }, default=str)

    c.execute('''
        INSERT INTO trade_history (symbol, decision_json, entry_price, sl, tp, position_size, reason, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (symbol, json.dumps(decision, default=str), entry, sl, tp, size, reason, now))

    rowid = c.lastrowid
    conn.commit()
    conn.close()
    return int(rowid)


def get_history(limit: int = 100) -> List[Dict[str, Any]]:
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM trade_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "symbol": r["symbol"],
            "decision": json.loads(r["decision_json"]) if r["decision_json"] else None,
            "entry_price": r["entry_price"],
            "sl": r["sl"],
            "tp": r["tp"],
            "position_size": r["position_size"],
            "reason": r["reason"],
            "timestamp": r["timestamp"],
            "status": r["status"],
            "outcome_note": r["outcome_note"]
        })
    return results


def update_outcome(trade_id: int, status: str, note: str = ""):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("UPDATE trade_history SET status = ?, outcome_note = ? WHERE id = ?", (status, note, trade_id))
    conn.commit()
    conn.close()


def update_outcome_and_learn(trade_id: int, status: str, note: str):
    """
    Update history and add an adaptive rule for RL.
    """
    conn = _get_conn()
    c = conn.cursor()
    c.execute("UPDATE trade_history SET status = ?, outcome_note = ? WHERE id = ?", (status, note, trade_id))

    if status.upper() == 'LOSS':
        c.execute("INSERT INTO learning_rules (rule_type, keyword, description) VALUES (?, ?, ?)",
                  ('AVOID', 'user_feedback', note))
    elif status.upper() == 'WIN':
        c.execute("INSERT INTO learning_rules (rule_type, keyword, description) VALUES (?, ?, ?)",
                  ('PREFER', 'winning_pattern', note))

    conn.commit()
    conn.close()


def get_adaptive_rules(limit: int = 10) -> Dict[str, List[str]]:
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT description FROM learning_rules WHERE rule_type = 'AVOID' ORDER BY id DESC LIMIT ?", (limit,))
    avoids = [r["description"] for r in c.fetchall()]

    c.execute("SELECT description FROM learning_rules WHERE rule_type = 'PREFER' ORDER BY id DESC LIMIT ?", (limit,))
    prefers = [r["description"] for r in c.fetchall()]

    conn.close()
    return {"avoid": avoids, "prefer": prefers}


# --- STATISTICS ---
def get_performance_stats() -> Dict[str, Any]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT status FROM trade_history WHERE status IN ('WIN','LOSS')")
    rows = c.fetchall()
    conn.close()
    total = len(rows)
    if total == 0:
        return {"win_rate": 0.0, "wins": 0, "losses": 0, "total": 0}
    wins = sum(1 for r in rows if r[0] == 'WIN')
    losses = total - wins
    return {"win_rate": (wins / total) * 100.0, "wins": wins, "losses": losses, "total": total}


# Init DB on import
init_db()


# quick self-test
if __name__ == "__main__":
    sample = {
        "status": "EXECUTE",
        "direction": "LONG",
        "confidence": 0.82,
        "risk": {"position_size": 0.1, "stop_loss": 42000, "take_profit": 43000},
        "technical": {"direction": "LONG"},
        "fundamental": {"flag": "GREEN"},
        "anomaly": {"anomaly": False},
        "notes": ["demo"]
    }
    id = save_trade("BTC/USDT", sample)
    print("saved id:", id)
    print("history:", get_history(5))
