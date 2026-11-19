"""Small transactional store, with encrypted source credentials and audit history."""
import json
import sqlite3
import threading
import time
from pathlib import Path
from cryptography.fernet import Fernet


class Store:
    def __init__(self, path: str, encryption_key: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.cipher = Fernet(encryption_key.encode())
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise RuntimeError("Studio database is newer than this version")
        with self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, at REAL, actor TEXT, action TEXT, outcome TEXT)")
            self.db.execute("CREATE TABLE IF NOT EXISTS seen (platform TEXT, message_id TEXT, at REAL, PRIMARY KEY(platform,message_id))")
            self.db.execute("PRAGMA user_version=1")

    def encrypt(self, text: str) -> str:
        return self.cipher.encrypt(text.encode()).decode()

    def decrypt(self, text: str) -> str:
        return self.cipher.decrypt(text.encode()).decode()

    def load(self):
        with self.lock:
            row = self.db.execute("SELECT data FROM config WHERE id=1").fetchone()
            return json.loads(row[0]) if row else None

    def save(self, data):
        with self.lock, self.db:
            self.db.execute("INSERT INTO config VALUES (1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (json.dumps(data),))

    def audit(self, actor, action, outcome):
        with self.lock, self.db:
            self.db.execute("INSERT INTO audit(at,actor,action,outcome) VALUES (?,?,?,?)", (time.time(), actor, action, outcome))
            self.db.execute("DELETE FROM audit WHERE id < (SELECT COALESCE(MAX(id),0)-1000 FROM audit)")

    def history(self):
        with self.lock:
            return [dict(zip(("id", "at", "actor", "action", "outcome"), row)) for row in self.db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100")]

    def claim_message(self, platform, message_id, now):
        with self.lock, self.db:
            self.db.execute("DELETE FROM seen WHERE at < ?", (now - 86400,))
            try:
                self.db.execute("INSERT INTO seen VALUES (?,?,?)", (platform, message_id, now))
                return True
            except sqlite3.IntegrityError:
                return False

    def close(self):
        self.db.close()
