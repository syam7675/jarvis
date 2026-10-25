"""User-scoped consent-based memory; store on a protected local volume."""
import json
import sqlite3
from datetime import datetime, timezone

class Memory:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS memories (owner TEXT, key TEXT, value TEXT, updated TEXT, PRIMARY KEY(owner,key))')
    def put(self, owner, key, value, *, consent=False):
        if not consent:
            raise ValueError('Explicit memory consent is required')
        if not owner or not key or not isinstance(value, str) or len(value)>8000:
            raise ValueError('Invalid memory')
        if any(x in key.casefold() for x in ('password','token','secret','api_key','credential')):
            raise ValueError('Store credentials in a secret manager, not memory')
        self.db.execute('INSERT OR REPLACE INTO memories VALUES (?,?,?,?)', (owner,key,value,datetime.now(timezone.utc).isoformat()))
        self.db.commit()
    def inspect(self, owner):
        return [dict(zip(('key','value','updated'), row)) for row in self.db.execute('SELECT key,value,updated FROM memories WHERE owner=? ORDER BY key',(owner,))]
    def forget(self, owner, key=None):
        if key is None:
            self.db.execute('DELETE FROM memories WHERE owner=?',(owner,))
        else:
            self.db.execute('DELETE FROM memories WHERE owner=? AND key=?',(owner,key))
        self.db.commit()
    def export(self, owner):
        return json.dumps(self.inspect(owner),ensure_ascii=False,indent=2)
    def close(self):
        self.db.close()
