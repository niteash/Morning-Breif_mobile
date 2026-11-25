BEGIN;
CREATE INDEX pronunciation_reports_briefing_idx
  ON public.pronunciation_reports(briefing_id);
COMMIT;
