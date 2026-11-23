"""Run against an EMPTY disposable local database; never reads .env or production URLs."""
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

url = os.environ.get('DATABASE_TEST_URL', '')
parsed = urlparse(url)
if parsed.hostname not in {'127.0.0.1', 'localhost'} or not parsed.path.startswith('/morning_brief_test'):
    raise SystemExit('Set DATABASE_TEST_URL to a disposable localhost morning_brief_test* database')
root = Path(__file__).resolve().parent

def sql(statement, ok=True):
    result = subprocess.run(['psql', url, '-XAt', '-v', 'ON_ERROR_STOP=1', '-c', statement], capture_output=True, text=True)
    if ok and result.returncode:
        raise AssertionError(result.stderr)
    if not ok:
        assert result.returncode != 0, 'Expected statement to fail'
    return result.stdout.strip()

assert sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'") == '0', 'Database must be empty'
sql(root.joinpath('fixture.sql').read_text())
sql(root.parent.joinpath('migrations/001_reliable_writes.sql').read_text())
u='00000000-0000-0000-0000-000000000001'
v='00000000-0000-0000-0000-000000000002'
a='10000000-0000-0000-0000-000000000001'
b='10000000-0000-0000-0000-000000000002'
c='10000000-0000-0000-0000-000000000003'
def as_user(statement):
    return f"SET ROLE authenticated; SET request.jwt.claim.sub='{u}'; {statement}"

sql(as_user(f"SELECT public.replace_my_categories(ARRAY['{a}','{a}']::uuid[])"))
assert sql(f"SELECT count(*) FROM user_categories WHERE user_id='{u}'") == '1'
sql(as_user(f"SELECT public.replace_my_categories(ARRAY['{c}']::uuid[])"), ok=False)
assert sql(f"SELECT category_id FROM user_categories WHERE user_id='{u}'") == a
# Force an insert failure AFTER the delete: entire transaction must roll back.
sql(f"CREATE FUNCTION reject_test_insert() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.category_id='{b}' THEN RAISE EXCEPTION 'fixture insertion failure'; END IF; RETURN NEW; END $$; CREATE TRIGGER reject_insert BEFORE INSERT ON user_categories FOR EACH ROW EXECUTE FUNCTION reject_test_insert()")
sql(as_user(f"SELECT public.replace_my_categories(ARRAY['{b}']::uuid[])"), ok=False)
assert sql(f"SELECT category_id FROM user_categories WHERE user_id='{u}'") == a
sql('DROP TRIGGER reject_insert ON user_categories')
sql(f"INSERT INTO user_categories VALUES('{v}','{a}')")
sql(as_user(f"SELECT public.replace_my_categories(ARRAY['{b}']::uuid[])"))
assert sql(f"SELECT category_id FROM user_categories WHERE user_id='{v}'") == a
print('PASS: category validation, deduplication, rollback and user isolation')

def claim(force=False, request="request-one"):
    return json.loads(sql(f"SET ROLE service_role; SELECT claim_briefing_v2('{u}','2026-11-08',{str(force).lower()},'{request}')").splitlines()[-1])
with ThreadPoolExecutor(max_workers=8) as executor:
    claims=list(executor.map(lambda _: claim(), range(8)))
assert sum(x['outcome']=='claimed' for x in claims)==1
assert sum(x['outcome']=='busy' for x in claims)==7
old=next(x['token'] for x in claims if x['outcome']=='claimed')
sql(f"UPDATE briefing_generation_jobs SET lease_until=now()-interval '1 second'")
new=claim()['token']
assert old != new

def finish(token):
    return sql(f"SET ROLE service_role; SELECT coalesce(finish_briefing_v2('{u}','2026-11-08','{token}','script','{u}/2026-11-08/test.mp3',42)::text,'NULL')").splitlines()[-1]
assert finish(old)=='NULL'
sql(f"SET ROLE service_role; SELECT fail_briefing_v2('{u}','2026-11-08','{old}')")
assert sql('SELECT state FROM briefing_generation_jobs')=='generating'
assert json.loads(finish(new))['duration_seconds']==42
assert claim()['outcome']=='ready'
assert claim(True)['outcome']=='ready', 'Retry of completed request must not spend another attempt'
third=claim(True, 'request-two')['token']
sql(f"SET ROLE service_role; SELECT fail_briefing_v2('{u}','2026-11-08','{third}')")
assert sql('SELECT status FROM briefings')=='ready', 'Failed regeneration must retain playable briefing'
assert claim(True)['outcome']=='limited'
assert claim()['outcome']=='ready'
print('PASS: concurrent claims, expired leases, stale-worker fencing, persistence and attempt limits')
sql(as_user(f"SELECT claim_briefing_v2('{u}','2026-11-08')"),ok=False)
sql(as_user(f"UPDATE briefings SET script='tampered' WHERE user_id='{u}'"),ok=False)
sql('SET ROLE authenticated; SELECT * FROM briefing_generation_jobs',ok=False)
sql(f"SET ROLE anon; SELECT replace_my_categories(ARRAY['{a}']::uuid[])",ok=False)
print('PASS: privileged RPCs, jobs and briefing mutations denied to clients')
for role in ('anon', 'authenticated'):
    for table in ('profiles', 'categories', 'user_categories', 'briefings'):
        for privilege in ('TRUNCATE', 'REFERENCES', 'TRIGGER'):
            assert sql(f"SELECT has_table_privilege('{role}', 'public.{table}', '{privilege}')") == 'f'
    sql(f'SET ROLE {role}; TRUNCATE public.briefings', ok=False)
print('PASS: table-wide privileges denied even when inherited from PUBLIC')

sql(f"SET ROLE service_role; SELECT claim_briefing_generation('{u}')",ok=False)
print('PASS: legacy claim RPC execution revoked')

# Initial failures persist status and enforce cooldown, even with attempts remaining.
initial=json.loads(sql(f"SET ROLE service_role; SELECT claim_briefing_v2('{u}','2026-11-09')").splitlines()[-1])
sql(f"SET ROLE service_role; SELECT fail_briefing_v2('{u}','2026-11-09','{initial['token']}')")
assert sql("SELECT status FROM briefings WHERE briefing_date='2026-11-09'")=='failed'
retry=json.loads(sql(f"SET ROLE service_role; SELECT claim_briefing_v2('{u}','2026-11-09')").splitlines()[-1])
assert retry['outcome']=='busy'
print('PASS: completed-request replay and failure cooldown')


# Notification queue integration uses the same disposable schema and local-only guard.
sql(root.parent.joinpath('migrations/20261109024013_durable_notification_delivery.sql').read_text())
exec(root.joinpath('notification_checks.py').read_text())

sql(root.parent.joinpath('migrations/20261109025525_recoverable_account_deletion.sql').read_text())
sql(root.parent.joinpath('migrations/20261113173705_private_account_availability.sql').read_text())
exec(root.joinpath('account_deletion_checks.py').read_text())
