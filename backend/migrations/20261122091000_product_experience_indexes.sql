CREATE INDEX briefing_requests_briefing_id_idx
  ON public.briefing_requests(briefing_id)
  WHERE briefing_id IS NOT NULL;
CREATE INDEX listening_progress_briefing_id_idx
  ON public.listening_progress(briefing_id);
