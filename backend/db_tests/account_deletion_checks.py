# Loaded only by run.py after its disposable localhost guard.
sql(f"INSERT INTO storage.objects(bucket_id,name) SELECT 'briefings','{u}/2026-11-09/'||n||'.mp3' FROM generate_series(1,125) n")
sql(f"INSERT INTO storage.objects(bucket_id,name) VALUES('briefings','{v}/other.mp3'),('unrelated','{u}/keep.bin')")
assert sql(f"SELECT account_is_active('{u}')")=='t'
with ThreadPoolExecutor(max_workers=4) as executor:
    requests=list(executor.map(lambda _: sql(f"SET ROLE service_role; SELECT request_account_deletion('{u}')"), range(4)))
assert sql('SELECT count(*) FROM account_deletion_jobs')=='1'
assert sql(f"SELECT account_is_active('{u}')")=='f'
assert sql(f"SELECT count(*) FROM notification_deliveries WHERE user_id='{u}'")=='0'
assert sql(f"SELECT count(*) FROM device_tokens WHERE user_id='{u}' AND is_active")=='0'
assert sql(as_user('SELECT count(*) FROM profiles')).splitlines()[-1]=='0'
assert sql(as_user('SELECT morning_brief_private.my_account_is_active()')).splitlines()[-1]=='f'
sql(f"INSERT INTO briefings(user_id,briefing_date) VALUES('{u}','2026-11-30')",ok=False)
sql(f"SET ROLE service_role; SELECT claim_briefing_v2('{u}','2026-11-30')",ok=False)
sql(f"UPDATE device_tokens SET is_active=true WHERE user_id='{u}'",ok=False)
assert sql('SELECT claim_account_deletion()')=='', 'Must allow in-flight generation to settle'
sql('UPDATE account_deletion_jobs SET available_at=now()')
def claim_delete():
    return json.loads(sql("SET ROLE service_role; SELECT coalesce(claim_account_deletion(),'null'::jsonb)").splitlines()[-1])
with ThreadPoolExecutor(max_workers=4) as executor:
    jobs=list(executor.map(lambda _: claim_delete(), range(4)))
assert sum(x is not None for x in jobs)==1
old=next(x for x in jobs if x)
sql("UPDATE account_deletion_jobs SET lease_until=now()-interval '1 second'")
job=claim_delete()
assert job['lease_token']!=old['lease_token']
sql(f"SELECT deletion_object_paths('{u}','{old['lease_token']}')",ok=False)
paths=sql(f"SET ROLE service_role; SELECT deletion_object_paths('{u}','{job['lease_token']}')").splitlines()[1:]
assert len(paths)==100 and all(path.startswith(u+'/') for path in paths)
sql(f"SELECT finish_account_deletion('{u}','{job['lease_token']}',true)",ok=False)
assert sql(f"SELECT finish_account_deletion('{u}','{job['lease_token']}',false)")=='t'
assert claim_delete() is None
sql('UPDATE account_deletion_jobs SET available_at=now()')
job=claim_delete()
# Fixture-only metadata mutation simulates Storage API removal; never run on hosted storage.
sql(f"DELETE FROM storage.objects WHERE bucket_id='briefings' AND name LIKE '{u}/%'")
sql(f"DELETE FROM auth.users WHERE id='{u}'")
assert sql('SELECT count(*) FROM account_deletion_jobs')=='1', 'Job survives Auth deletion/crash'
assert sql(f"SELECT finish_account_deletion('{u}','{job['lease_token']}',true)")=='t'
assert sql('SELECT count(*) FROM account_deletion_jobs')=='0'
assert sql(f"SELECT account_is_active('{u}')")=='f', 'Old JWT must remain denied after job removal'
assert sql(f"SELECT account_is_active('{v}')")=='t'
assert sql('SELECT count(*) FROM storage.objects')=='2', 'Other users and buckets must survive'
for role in ('anon','authenticated'):
    sql(f'SET ROLE {role}; SELECT * FROM account_deletion_jobs',ok=False)
    sql(f"SET ROLE {role}; SELECT request_account_deletion('{v}')",ok=False)
    sql(f'SET ROLE {role}; SELECT claim_account_deletion()',ok=False)
    sql(f"SET ROLE {role}; SELECT deletion_object_paths('{v}','{job['lease_token']}')",ok=False)
print('PASS: deletion request idempotency, write/RLS fencing, competing claims, retry and cleanup isolation')

assert sql("SELECT to_regprocedure('public.my_account_is_active()') IS NULL")=='t'
sql('SET ROLE anon; SELECT morning_brief_private.my_account_is_active()',ok=False)

# Exhaustion keeps an inspectable marker and must never reactivate the account.
sql(f"SELECT request_account_deletion('{v}')")
sql('UPDATE account_deletion_jobs SET attempts=19,available_at=now()')
last = claim_delete()
assert last['attempts'] == 20
sql(f"SELECT finish_account_deletion('{v}','{last['lease_token']}',false)")
assert sql('SELECT state FROM account_deletion_jobs') == 'failed'
assert claim_delete() is None
assert sql(f"SELECT account_is_active('{v}')") == 'f'
print('PASS: deletion attempt exhaustion retains a blocked account for operator review')
