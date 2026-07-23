"""Labeled evaluation dataset for the code reviewer.

Each case is a small file of code with KNOWN planted bugs — this is the
"answer key" (ground truth). We locate each bug by a unique substring on
its line, so the line numbers are computed automatically and can't drift
if the code is edited.

Some cases are intentionally CLEAN (no bugs) to test whether the reviewer
invents problems (false positives).

Categories: security | correctness | error-handling
"""

CASES = [
    # ---------------------------------------------------------------- security
    {
        "id": "weak_hash",
        "filename": "auth.py",
        "category": "security",
        "code": '''import hashlib

def check_password(pw, stored_hash):
    digest = hashlib.md5(pw.encode()).hexdigest()
    return digest == stored_hash
''',
        "bugs": [{"match": "hashlib.md5", "note": "MD5 is broken; unsafe for passwords"}],
    },
    {
        "id": "hardcoded_secret",
        "filename": "config.py",
        "category": "security",
        "code": '''import os

API_KEY = "sk-live-1234567890abcdef"

def client():
    return connect(API_KEY)
''',
        "bugs": [{"match": 'API_KEY = "sk-live', "note": "hardcoded secret in source"}],
    },
    {
        "id": "sql_injection",
        "filename": "db.py",
        "category": "security",
        "code": '''def get_user(conn, name):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE name = '{name}'")
    return cur.fetchone()
''',
        "bugs": [{"match": "execute(f", "note": "SQL injection via f-string"}],
    },
    {
        "id": "eval_user_input",
        "filename": "calc.py",
        "category": "security",
        "code": '''def compute(expr):
    # expr comes straight from an HTTP request
    return eval(expr)
''',
        "bugs": [{"match": "eval(expr)", "note": "eval on untrusted input = RCE"}],
    },
    # ------------------------------------------------------------- correctness
    {
        "id": "index_no_check",
        "filename": "users.py",
        "category": "correctness",
        "code": '''def get_user(users, user_id):
    return users[user_id]
''',
        "bugs": [{"match": "users[user_id]", "note": "KeyError if user_id missing"}],
    },
    {
        "id": "division_by_zero",
        "filename": "stats.py",
        "category": "correctness",
        "code": '''def average(numbers):
    total = sum(numbers)
    return total / len(numbers)
''',
        "bugs": [{"match": "total / len(numbers)", "note": "ZeroDivisionError on empty list"}],
    },
    {
        "id": "off_by_one",
        "filename": "loop.py",
        "category": "correctness",
        "code": '''def last_three(items):
    result = []
    for i in range(len(items) - 3, len(items) + 1):
        result.append(items[i])
    return result
''',
        "bugs": [{"match": "len(items) + 1", "note": "off-by-one: IndexError on last iter"}],
    },
    {
        "id": "mutable_default",
        "filename": "cache.py",
        "category": "correctness",
        "code": '''def add_item(item, bucket=[]):
    bucket.append(item)
    return bucket
''',
        "bugs": [{"match": "bucket=[]", "note": "mutable default arg shared across calls"}],
    },
    # ----------------------------------------------------------- error-handling
    {
        "id": "bare_except",
        "filename": "worker.py",
        "category": "error-handling",
        "code": '''def run(task):
    try:
        return task.execute()
    except:
        return None
''',
        "bugs": [{"match": "except:", "note": "bare except swallows everything incl. KeyboardInterrupt"}],
    },
    {
        "id": "resource_leak",
        "filename": "files.py",
        "category": "error-handling",
        "code": '''def read_config(path):
    f = open(path)
    data = f.read()
    return data
''',
        "bugs": [{"match": "open(path)", "note": "file never closed (use a context manager)"}],
    },
    # ------------------------------------------------------------------- clean
    {
        "id": "clean_hash",
        "filename": "hashing.py",
        "category": "clean",
        "code": '''import hashlib

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
''',
        "bugs": [],
    },
    {
        "id": "clean_average",
        "filename": "safe_stats.py",
        "category": "clean",
        "code": '''def average(numbers):
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)
''',
        "bugs": [],
    },
    {
        "id": "clean_read",
        "filename": "safe_files.py",
        "category": "clean",
        "code": '''def read_config(path):
    with open(path) as f:
        return f.read()
''',
        "bugs": [],
    },
]
