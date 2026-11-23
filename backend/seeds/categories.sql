-- Reference data only. Apply to the intended environment after its schema exists.
-- Resolve IDs by slug at runtime; never copy production-generated UUIDs.
INSERT INTO public.categories(slug,name_en,name_my,active) VALUES
  ('technology','Technology','နည်းပညာ',true),
  ('business','Business','စီးပွားရေး',true),
  ('football','Football','ဘောလုံး',true),
  ('world','World','ကမ္ဘာ့သတင်း',true),
  ('myanmar','Myanmar','မြန်မာသတင်း',true),
  ('crypto','Crypto','ခရစ်ပတို',true),
  ('psychology','Psychology','စိတ်ပညာ',true),
  ('horoscope','Horoscope','ရာသီခွင်ဟောကိန်း',true)
ON CONFLICT (slug) DO NOTHING;
