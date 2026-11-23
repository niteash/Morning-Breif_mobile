-- REVIEW-ONLY proposal: do not apply until the staging migration is explicitly approved.
-- Adds opt-in reminders, weekday delivery, and foreground auto-play preferences.
-- Requires the existing durable_notification_delivery objects.
BEGIN;

-- Preflight: stop before DDL if old rows contain invalid schedules/timezones.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM public.profiles p
    WHERE p.delivery_hour NOT BETWEEN 0 AND 23
       OR p.delivery_minute NOT BETWEEN 0 AND 59
       OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_timezone_names z WHERE z.name = p.timezone)
  ) THEN
    RAISE EXCEPTION 'Review invalid profile delivery time/timezone values before applying';
  END IF;
END $$;

ALTER TABLE public.profiles
  ADD COLUMN daily_reminder_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN auto_play_when_open boolean NOT NULL DEFAULT false,
  ADD COLUMN delivery_schedule text NOT NULL DEFAULT 'daily'
    CHECK (delivery_schedule IN ('daily', 'weekdays'));

-- Queue reminders for the user's preferred local delivery instant, only after a
-- playable briefing is saved and only when that account opted in. Time conversion
-- uses PostgreSQL's IANA timezone database, including DST transitions.
CREATE OR REPLACE FUNCTION public.enqueue_briefing_notifications() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
  due_at timestamptz;
  reminder_enabled boolean;
  schedule text;
BEGIN
  IF NEW.status <> 'ready' OR NEW.audio_url IS NULL THEN RETURN NEW; END IF;
  SELECT p.daily_reminder_enabled, p.delivery_schedule,
         ((NEW.briefing_date + make_time(p.delivery_hour, p.delivery_minute, 0)) AT TIME ZONE p.timezone)
    INTO reminder_enabled, schedule, due_at
    FROM public.profiles p
   WHERE p.id = NEW.user_id AND public.account_is_active(p.id);
  IF NOT FOUND OR reminder_enabled IS DISTINCT FROM true THEN RETURN NEW; END IF;
  IF schedule = 'weekdays' AND extract(isodow FROM NEW.briefing_date) > 5 THEN RETURN NEW; END IF;
  -- Do not send a stale push for an excessively late catch-up. The in-app saved
  -- briefing remains available even when this reminder window has passed.
  IF due_at < clock_timestamp() - interval '2 hours' THEN RETURN NEW; END IF;

  INSERT INTO public.notification_deliveries(
    briefing_id, device_id, user_id, briefing_date, fcm_token, available_at, expires_at
  )
  SELECT NEW.id, d.id, NEW.user_id, NEW.briefing_date, d.fcm_token,
         greatest(due_at, clock_timestamp()), greatest(due_at, clock_timestamp()) + interval '24 hours'
    FROM public.device_tokens d
   WHERE d.user_id = NEW.user_id AND d.is_active AND d.platform = 'android'
  ON CONFLICT (briefing_id, device_id) DO NOTHING;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.enqueue_briefing_notifications() FROM PUBLIC, anon, authenticated, service_role;

-- A reminder turned off after enqueue cancels pending deliveries. A send already
-- claimed by Firebase may finish; the worker's existing lease protects its result.
CREATE FUNCTION public.cancel_opted_out_briefing_notifications() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
  IF OLD.daily_reminder_enabled AND NOT NEW.daily_reminder_enabled THEN
    UPDATE public.notification_deliveries
       SET state = 'cancelled', lease_token = NULL, lease_until = NULL
     WHERE user_id = NEW.id AND state = 'pending';
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.cancel_opted_out_briefing_notifications() FROM PUBLIC, anon, authenticated, service_role;
CREATE TRIGGER cancel_opted_out_briefing_notifications
  AFTER UPDATE OF daily_reminder_enabled ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.cancel_opted_out_briefing_notifications();

-- Preference changes take effect for today's ready briefing as well: cancel
-- reminders that no longer match, or move/create a still-relevant pending item.
CREATE FUNCTION public.reschedule_profile_briefing_notifications() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
  local_today date;
  due_at timestamptz;
BEGIN
  local_today := (clock_timestamp() AT TIME ZONE NEW.timezone)::date;
  IF NOT NEW.daily_reminder_enabled
     OR NOT public.account_is_active(NEW.id)
     OR (NEW.delivery_schedule = 'weekdays' AND extract(isodow FROM local_today) > 5) THEN
    UPDATE public.notification_deliveries
       SET state = 'cancelled', lease_token = NULL, lease_until = NULL
     WHERE user_id = NEW.id AND state = 'pending';
    RETURN NEW;
  END IF;

  due_at := ((local_today + make_time(NEW.delivery_hour, NEW.delivery_minute, 0)) AT TIME ZONE NEW.timezone);
  IF due_at < clock_timestamp() - interval '2 hours' THEN RETURN NEW; END IF;

  INSERT INTO public.notification_deliveries AS existing(
    briefing_id, device_id, user_id, briefing_date, fcm_token, available_at, expires_at
  )
  SELECT b.id, d.id, NEW.id, b.briefing_date, d.fcm_token,
         greatest(due_at, clock_timestamp()), greatest(due_at, clock_timestamp()) + interval '24 hours'
    FROM public.briefings b
    JOIN public.device_tokens d ON d.user_id = NEW.id AND d.is_active AND d.platform = 'android'
   WHERE b.user_id = NEW.id AND b.briefing_date = local_today
     AND b.status = 'ready' AND b.audio_url IS NOT NULL
  ON CONFLICT (briefing_id, device_id) DO UPDATE
    SET state = 'pending', available_at = EXCLUDED.available_at, expires_at = EXCLUDED.expires_at,
        lease_token = NULL, lease_until = NULL
    WHERE existing.state = 'pending'
       OR (existing.state = 'cancelled' AND existing.expires_at > clock_timestamp() AND existing.sent_at IS NULL);
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.reschedule_profile_briefing_notifications() FROM PUBLIC, anon, authenticated, service_role;
CREATE TRIGGER reschedule_profile_briefing_notifications
  AFTER UPDATE OF daily_reminder_enabled, delivery_schedule, timezone, delivery_hour, delivery_minute
  ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.reschedule_profile_briefing_notifications();

COMMIT;
