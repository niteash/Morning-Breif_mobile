begin;

alter table public.profiles
  add column phone_number text,
  add column avatar_path text;

alter table public.profiles
  add constraint profiles_phone_number_check check (
    phone_number is null or phone_number ~ '^\+[1-9][0-9]{6,14}$'
  ),
  add constraint profiles_avatar_path_check check (
    avatar_path is null or avatar_path ~ (
      '^' || id::text || '/[0-9]{13}-[0-9a-f-]{36}\.(jpg|jpeg|png|webp)$'
    )
  );

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'profile-images',
  'profile-images',
  false,
  5242880,
  array['image/jpeg', 'image/png', 'image/webp']
);

create policy "Users can read own profile images"
on storage.objects for select to authenticated
using (
  bucket_id = 'profile-images'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy "Users can upload own profile images"
on storage.objects for insert to authenticated
with check (
  bucket_id = 'profile-images'
  and (storage.foldername(name))[1] = (select auth.uid())::text
  and storage.extension(name) in ('jpg', 'jpeg', 'png', 'webp')
);

create policy "Users can update own profile images"
on storage.objects for update to authenticated
using (
  bucket_id = 'profile-images'
  and (storage.foldername(name))[1] = (select auth.uid())::text
)
with check (
  bucket_id = 'profile-images'
  and (storage.foldername(name))[1] = (select auth.uid())::text
  and storage.extension(name) in ('jpg', 'jpeg', 'png', 'webp')
);

create policy "Users can delete own profile images"
on storage.objects for delete to authenticated
using (
  bucket_id = 'profile-images'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

commit;
