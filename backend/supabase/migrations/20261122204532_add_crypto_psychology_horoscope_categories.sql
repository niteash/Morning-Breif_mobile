-- Reference categories used by RSS ingestion and user preferences.
-- Existing selections are unchanged; users opt into the new categories.
insert into public.categories (slug, name_en, name_my, active)
values
  ('crypto', 'Crypto', 'ခရစ်ပတို', true),
  ('psychology', 'Psychology', 'စိတ်ပညာ', true),
  ('horoscope', 'Horoscope', 'ရာသီခွင်ဟောကိန်း', true)
on conflict (slug) do update
set name_en = excluded.name_en,
    name_my = excluded.name_my,
    active = excluded.active;
