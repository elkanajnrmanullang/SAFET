import sqlite3
import json
from datetime import datetime

DB_NAME = "data/alta_master.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Table History
    c.execute('''CREATE TABLE IF NOT EXISTS trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    action TEXT,
                    entry TEXT,
                    sl TEXT,
                    tp TEXT,
                    reason TEXT,
                    timestamp DATETIME,
                    status TEXT DEFAULT 'OPEN', 
                    outcome_note TEXT
                )''')
    
    # Table Learning Rules
    c.execute('''CREATE TABLE IF NOT EXISTS learning_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_type TEXT,
                    keyword TEXT,
                    description TEXT
                )''')
    conn.commit()
    conn.close()

# --- HISTORY FUNCTIONS ---
def save_trade(symbol, data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO trade_history (symbol, action, entry, sl, tp, reason, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (symbol, data.get('keputusan'), data.get('entry'), data.get('sl'), 
               # Handle TP1/TP2 combination for storage
               f"TP1:{data.get('tp1')} | TP2:{data.get('tp2')}", 
               data.get('alasan'), datetime.now()))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM trade_history ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# --- UPDATE SIMPLE (FIX IMPORT ERROR) ---
def update_outcome(trade_id, status, note=""):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE trade_history SET status = ?, outcome_note = ? WHERE id = ?", (status, note, trade_id))
    conn.commit()
    conn.close()

# --- UPDATE & LEARN (SMART LOGIC) ---
def update_outcome_and_learn(trade_id, status, note):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Update Status
    c.execute("UPDATE trade_history SET status = ?, outcome_note = ? WHERE id = ?", (status, note, trade_id))
    
    # 2. Add Knowledge
    if status == 'LOSS':
        c.execute("INSERT INTO learning_rules (rule_type, keyword, description) VALUES (?, ?, ?)", 
                  ('AVOID', 'User Feedback', note))
    elif status == 'WIN':
        c.execute("INSERT INTO learning_rules (rule_type, keyword, description) VALUES (?, ?, ?)", 
                  ('PREFER', 'Winning Pattern', 'Pola sukses terkonfirmasi.'))
                  
    conn.commit()
    conn.close()

# --- RETRIEVE KNOWLEDGE ---
def get_adaptive_rules():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT description FROM learning_rules WHERE rule_type = 'AVOID'")
    avoids = [r['description'] for r in c.fetchall()]
    
    conn.close()
    
    rules_text = ""
    if avoids:
        rules_text += "HINDARI KESALAHAN BERIKUT (DARI PENGALAMAN MASA LALU):\n"
        for i, rule in enumerate(avoids):
            rules_text += f"{i+1}. {rule}\n"
            
    return rules_text

# Init on import
init_db()