ALTER TABLE public.profiles
  ADD COLUMN automatic_briefing_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN daily_reminder_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN auto_play_when_open boolean NOT NULL DEFAULT false,
  ADD COLUMN delivery_schedule text NOT NULL DEFAULT 'daily';

ALTER TABLE public.profiles
  ADD CONSTRAINT profiles_delivery_schedule_check
  CHECK (delivery_schedule IN ('daily', 'weekdays'));

-- Audio may be prepared up to 30 minutes early. Queue notifications for the
-- user's chosen local delivery time, or immediately when generation finishes late.
CREATE OR REPLACE FUNCTION public.enqueue_briefing_notifications()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  IF NEW.status = 'ready' AND NEW.audio_url IS NOT NULL THEN
    INSERT INTO public.notification_deliveries(
      briefing_id, device_id, user_id, briefing_date, fcm_token, available_at
    )
    SELECT
      NEW.id,
      d.id,
      NEW.user_id,
      NEW.briefing_date,
      d.fcm_token,
      greatest(
        clock_timestamp(),
        (
          NEW.briefing_date
          + make_time(p.delivery_hour, p.delivery_minute, 0)
        ) AT TIME ZONE p.timezone
      )
    FROM public.device_tokens d
    JOIN public.profiles p ON p.id = d.user_id
    WHERE d.user_id = NEW.user_id
      AND d.is_active
      AND d.platform = 'android'
      AND p.daily_reminder_enabled
    ON CONFLICT (briefing_id, device_id) DO NOTHING;
  END IF;
  RETURN NEW;
END
$$;

REVOKE ALL ON FUNCTION public.enqueue_briefing_notifications()
FROM PUBLIC, anon, authenticated, service_role;
