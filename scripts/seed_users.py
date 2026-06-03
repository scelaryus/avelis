"""Seed 5 user accounts with role-based module access."""
import psycopg2
import uuid
from hashlib import sha256

conn = psycopg2.connect("postgresql://gfi_user:gfi_password@localhost:5432/gfi_v7")
cur = conn.cursor()

PASSWORD = sha256("gfi2026".encode()).hexdigest()

users = [
    ("ahmed@gfi.dz",  PASSWORD, "Ahmed Admin",  "DAF",                True),
    ("yazid@gfi.dz",  PASSWORD, "Yazid Assoc",  "RESPONSABLE_ADV",    True),
    ("sara@gfi.dz",   PASSWORD, "Sara Benmoussa", "AGENT_COMMERCIAL",   False),
    ("hayat@gfi.dz",  PASSWORD, "Hayat Cherifi",  "GESTIONNAIRE_STOCK", False),
    ("rh@gfi.dz",     PASSWORD, "Service RH",     "DRH",                False),
]

# Clear old users (keep any non-test users)
cur.execute("DELETE FROM auth_user WHERE email IN (%s,%s,%s,%s,%s)",
            tuple(u[0] for u in users))
conn.commit()

for email, pwd, name, role, rf2 in users:
    cur.execute("""
        INSERT INTO auth_user (id, email, password_hash, full_name, role, has_rf2_access, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, true, NOW())
        ON CONFLICT (email) DO UPDATE SET password_hash = %s, full_name = %s, role = %s, has_rf2_access = %s
    """, (str(uuid.uuid4()), email, pwd, name, role, rf2, pwd, name, role, rf2))

conn.commit()
conn.close()

print("Users seeded:")
for email, _, name, role, rf2 in users:
    print(f"  {email:20s}  {name:20s}  {role:20s}  RF2={'Yes' if rf2 else 'No'}")
print(f"\nPassword for all: gfi2026")
