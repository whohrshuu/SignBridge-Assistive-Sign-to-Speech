create extension if not exists pgcrypto;
create table if not exists public.gesture_samples (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 label varchar(48) not null check (label ~ '^[A-Za-z][A-Za-z0-9 _''-]{0,47}$'),
 handedness varchar(8) not null check (handedness in ('Left','Right','Unknown')),
 landmarks jsonb not null check (jsonb_typeof(landmarks)='array' and jsonb_array_length(landmarks)=21),
 created_at timestamptz not null default now()
);
create table if not exists public.recognition_history (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 event_type varchar(20) not null check (event_type in ('recognized','quick','spoken','saved')),
 phrase text not null check (char_length(phrase) between 1 and 500),
 source varchar(32) not null,
 created_at timestamptz not null default now()
);
create index if not exists samples_user_label on public.gesture_samples(user_id,label);
create index if not exists history_user_date on public.recognition_history(user_id,created_at desc);
alter table public.gesture_samples enable row level security;
alter table public.recognition_history enable row level security;
revoke all on public.gesture_samples,public.recognition_history from anon,authenticated;
grant select,insert,delete on public.gesture_samples,public.recognition_history to authenticated;
create policy "samples_select" on public.gesture_samples for select to authenticated using ((select auth.uid())=user_id);
create policy "samples_insert" on public.gesture_samples for insert to authenticated with check ((select auth.uid())=user_id);
create policy "samples_delete" on public.gesture_samples for delete to authenticated using ((select auth.uid())=user_id);
create policy "history_select" on public.recognition_history for select to authenticated using ((select auth.uid())=user_id);
create policy "history_insert" on public.recognition_history for insert to authenticated with check ((select auth.uid())=user_id);
create policy "history_delete" on public.recognition_history for delete to authenticated using ((select auth.uid())=user_id);
