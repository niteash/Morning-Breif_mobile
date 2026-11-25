# Executed by run.py with its guarded local sql helper. No network/FCM access.
def push_claim():
    return json.loads(sql('SET ROLE service_role; SELECT coalesce(claim_notification_delivery(),\'null\'::jsonb)').splitlines()[-1])
def push_finish(job, outcome):
    return sql(f"SET ROLE service_role; SELECT finish_notification_delivery('{job['id']}','{job['lease_token']}','{outcome}')").splitlines()[-1]

dev='20000000-0000-0000-0000-000000000001'
sql(f"INSERT INTO device_tokens(id,user_id,fcm_token) VALUES('{dev}','{u}','fake-token-no-firebase')")
# Completion and queue are atomic; no backfill of old ready briefings.
assert sql('SELECT count(*) FROM notification_deliveries')=='0'
sql(f"UPDATE briefings SET status='ready',audio_url='test.mp3' WHERE user_id='{u}' AND briefing_date='2026-11-08'")
sql(f"UPDATE briefings SET audio_url='regenerated.mp3' WHERE user_id='{u}' AND briefing_date='2026-11-08'")
assert sql('SELECT count(*) FROM notification_deliveries')=='1'
with ThreadPoolExecutor(max_workers=8) as executor:
    claimed=list(executor.map(lambda _: push_claim(), range(8)))
assert sum(x is not None for x in claimed)==1
old=next(x for x in claimed if x)
sql("UPDATE notification_deliveries SET lease_until=now()-interval '1 second'")
new=push_claim()
assert new['lease_token'] != old['lease_token']
assert push_finish(old,'sent')=='f'
assert push_finish(new,'retry')=='t'
assert push_claim() is None, 'Backoff must stop immediate retries'
sql('UPDATE notification_deliveries SET available_at=now()')
job=push_claim()
assert push_finish(job,'sent')=='t'
assert push_claim() is None
assert sql('SELECT attempts FROM notification_deliveries')=='3'
print('PASS: atomic enqueue, per-device dedupe, concurrent claims, stale lease fencing and backoff')

# Account switching cancels pending delivery and cannot deactivate the new owner.
sql(f"UPDATE briefings SET status='ready',audio_url='test.mp3' WHERE user_id='{u}' AND briefing_date='2026-11-09'")
job=push_claim()
sql(f"UPDATE device_tokens SET user_id='{v}' WHERE id='{dev}'")
assert push_finish(job,'invalid')=='t'
assert sql(f"SELECT is_active FROM device_tokens WHERE id='{dev}'")=='t'
sql(f"UPDATE device_tokens SET user_id='{u}' WHERE id='{dev}'")
sql(f"INSERT INTO briefings(user_id,briefing_date,status,audio_url) VALUES('{u}','2026-11-10','ready','test.mp3')")
sql(f"UPDATE device_tokens SET is_active=false WHERE id='{dev}'")
assert push_claim() is None
assert sql("SELECT state FROM notification_deliveries WHERE briefing_date='2026-11-10'")=='cancelled'
sql(f"UPDATE device_tokens SET is_active=true WHERE id='{dev}'")
sql(f"INSERT INTO briefings(user_id,briefing_date,status,audio_url) VALUES('{u}','2026-11-11','ready','test.mp3')")
job=push_claim()
assert push_finish(job,'invalid')=='t'
assert sql(f"SELECT is_active FROM device_tokens WHERE id='{dev}'")=='f'
print('PASS: logout cancellation, account reassignment safety and invalid-token cleanup')

sql(f"UPDATE device_tokens SET is_active=true WHERE id='{dev}'")
sql(f"INSERT INTO briefings(user_id,briefing_date,status,audio_url) VALUES('{u}','2026-11-12','ready','test.mp3')")
for attempt in range(5):
    job=push_claim()
    assert job['attempts']==attempt+1
    assert push_finish(job,'retry')=='t'
    sql('UPDATE notification_deliveries SET available_at=now()')
assert push_claim() is None
assert sql("SELECT state FROM notification_deliveries WHERE briefing_date='2026-11-12'")=='dead'
sql(f"INSERT INTO briefings(user_id,briefing_date,status,audio_url) VALUES('{u}','2026-11-13','ready','test.mp3')")
sql("UPDATE notification_deliveries SET expires_at=now()-interval '1 second' WHERE briefing_date='2026-11-13'")
assert push_claim() is None
for role in ('anon','authenticated'):
    sql(f'SET ROLE {role}; SELECT * FROM notification_deliveries',ok=False)
    sql(f'SET ROLE {role}; SELECT claim_notification_delivery()',ok=False)
    sql(f"SET ROLE {role}; SELECT finish_notification_delivery('{job['id']}','{job['lease_token']}','sent')",ok=False)
    sql(f'SET ROLE {role}; TRUNCATE notification_deliveries',ok=False)
print('PASS: expiry, attempt cap and client queue/RPC access denied')

# A queue insert failure must roll back the briefing finish and generation lease state.
sql("CREATE FUNCTION reject_notification_fixture() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'fixture queue unavailable'; END $$; CREATE TRIGGER reject_notification_fixture BEFORE INSERT ON notification_deliveries FOR EACH ROW EXECUTE FUNCTION reject_notification_fixture()")
claimed=json.loads(sql(f"SET ROLE service_role; SELECT claim_briefing_v2('{u}','2026-11-14')").splitlines()[-1])
sql(f"SET ROLE service_role; SELECT finish_briefing_v2('{u}','2026-11-14','{claimed['token']}','script','{u}/2026-11-14/test.mp3',42)",ok=False)
assert sql("SELECT status FROM briefings WHERE briefing_date='2026-11-14'")=='generating'
assert sql("SELECT state FROM briefing_generation_jobs WHERE briefing_date='2026-11-14'")=='generating'
assert sql("SELECT count(*) FROM notification_deliveries WHERE briefing_date='2026-11-14'")=='0'
sql('DROP TRIGGER reject_notification_fixture ON notification_deliveries')
sql(f"SET ROLE service_role; SELECT finish_briefing_v2('{u}','2026-11-14','{claimed['token']}','script','{u}/2026-11-14/test.mp3',42)")
assert sql("SELECT count(*) FROM notification_deliveries WHERE briefing_date='2026-11-14'")=='1'
print('PASS: queue failure rolls back briefing completion; retry enqueues atomically')
