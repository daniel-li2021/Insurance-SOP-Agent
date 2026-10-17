"""Encrypted SQLite sessions, durable per-session leases, and bounded public usage."""
import hashlib
import hmac
import os
import secrets
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from cryptography.fernet import Fernet
from .models import Session


class Conflict(Exception):
    pass


class Limited(Exception):
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class Store:
    def __init__(self, directory: Path, encryption_key: str | None = None):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / 'sessions.sqlite3'
        if encryption_key:
            key = encryption_key.encode()
        else:
            keypath = directory / 'session.key'
            if keypath.is_symlink(): raise ValueError('Session key cannot be a symlink')
            try:
                with keypath.open('xb') as f:
                    os.chmod(keypath, 0o600)
                    f.write(Fernet.generate_key())
            except FileExistsError:
                pass
            key = keypath.read_bytes()
        self.cipher = Fernet(key)
        self.digest_key = key
        with self.db() as db:
            db.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, csrf TEXT NOT NULL, payload BLOB NOT NULL,
                updated REAL NOT NULL, lease TEXT, lease_until REAL DEFAULT 0);
              CREATE TABLE IF NOT EXISTS requests (
                session_id TEXT, request_id TEXT, fingerprint TEXT, PRIMARY KEY(session_id, request_id));
              CREATE TABLE IF NOT EXISTS limits (key TEXT PRIMARY KEY, used INTEGER NOT NULL, expires REAL DEFAULT 0);
              CREATE TABLE IF NOT EXISTS budget (day INTEGER PRIMARY KEY, tokens INTEGER NOT NULL);
            ''')
            if 'expires' not in {r['name'] for r in db.execute('PRAGMA table_info(limits)')}:
                db.execute('ALTER TABLE limits ADD COLUMN expires REAL DEFAULT 0')
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def encode(self, state: Session):
        return self.cipher.encrypt(state.model_dump_json().encode())

    def decode(self, payload):
        return Session.model_validate_json(self.cipher.decrypt(payload))

    @staticmethod
    def hashed(value: str):
        return hashlib.sha256(value.encode()).hexdigest()

    def fingerprint(self, value: str):
        return hmac.new(self.digest_key, value.encode(), hashlib.sha256).hexdigest()

    def create(self, now: float, initial: Session | None = None) -> tuple[str, str, Session]:
        cookie = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        s = initial if initial is not None else Session()
        with self.db() as db:
            db.execute('DELETE FROM requests WHERE session_id IN (SELECT id FROM sessions WHERE updated < ?)', (now - 86400,))
            db.execute('DELETE FROM sessions WHERE updated < ?', (now - 86400,))
            db.execute('INSERT INTO sessions (id,csrf,payload,updated) VALUES (?,?,?,?)', (self.hashed(cookie), csrf, self.encode(s), now))
        return cookie, csrf, s

    def load(self, cookie: str, now: float):
        with self.db() as db:
            row = db.execute('SELECT * FROM sessions WHERE id=? AND updated>=?', (self.hashed(cookie), now-86400)).fetchone()
        if not row: raise KeyError('Session expired')
        return self.decode(row['payload']), row['csrf']

    def remove(self, cookie: str):
        with self.db() as db:
            sid = self.hashed(cookie)
            db.execute('DELETE FROM requests WHERE session_id=?', (sid,))
            db.execute('DELETE FROM sessions WHERE id=?', (sid,))

    def acquire(self, cookie: str, request_id: str, version: int, fingerprint: str, now: float):
        sid = self.hashed(cookie)
        lease = secrets.token_hex(16)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
            if not row or row['updated'] < now - 86400: raise KeyError('Session expired')
            state = self.decode(row['payload'])
            old = db.execute('SELECT fingerprint FROM requests WHERE session_id=? AND request_id=?', (sid, request_id)).fetchone()
            if old:
                if old['fingerprint'] != fingerprint: raise Conflict('Request ID was reused for a different action.')
                return state, None
            if state.version >= 120: raise Limited('This session has reached its action limit. Start a fresh synthetic session.')
            if row['lease_until'] > now: raise Conflict('Another request is running. Wait, then refresh and retry.')
            if state.version != version: raise Conflict('The session changed. Refresh before retrying.')
            db.execute('UPDATE sessions SET lease=?, lease_until=? WHERE id=?', (lease, now+45, sid))
        return state, lease

    def commit(self, cookie: str, lease: str, request_id: str, fingerprint: str, state: Session, now: float):
        sid = self.hashed(cookie)
        state.version += 1
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT lease,lease_until FROM sessions WHERE id=?', (sid,)).fetchone()
            if not row or row['lease'] != lease or row['lease_until'] <= now:
                raise Conflict('This request was interrupted. Refresh to recover the session.')
            db.execute('UPDATE sessions SET payload=?,updated=?,lease=NULL,lease_until=0 WHERE id=?', (self.encode(state), now, sid))
            db.execute('INSERT INTO requests VALUES (?,?,?)', (sid, request_id, fingerprint))

    def release(self, cookie: str, lease: str):
        with self.db() as db:
            db.execute('UPDATE sessions SET lease=NULL,lease_until=0 WHERE id=? AND lease=?', (self.hashed(cookie), lease))

    def limit(self, key: str, maximum: int, period: int, now: float):
        bucket = int(now // period)
        encoded = self.hashed(key) + ':' + str(bucket)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT used FROM limits WHERE key=?', (encoded,)).fetchone()
            if old and old['used'] >= maximum:
                raise Limited('Too many requests. Please try again later.', max(1, math.ceil((bucket + 1) * period - now)))
            db.execute('DELETE FROM limits WHERE expires < ?', (now,))
            db.execute('INSERT INTO limits (key,used,expires) VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET used=used+1', (encoded, (bucket+1)*period))

    def reserve_tokens(self, amount: int, maximum: int, now: float):
        day = int(now // 86400)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT tokens FROM budget WHERE day=?', (day,)).fetchone()
            if (row['tokens'] if row else 0) + amount > maximum:
                raise Limited('The daily demo model budget is reached. Try again tomorrow or use offline mode after restarting the app.')
            db.execute('INSERT INTO budget VALUES (?,?) ON CONFLICT(day) DO UPDATE SET tokens=tokens+excluded.tokens', (day,amount))

    def settle_tokens(self, reserved: int, actual: int, now: float):
        with self.db() as db:
            db.execute('UPDATE budget SET tokens=MAX(0,tokens+?) WHERE day=?', (actual-reserved, int(now//86400)))
