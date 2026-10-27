-- Scheme monofilare — schema bazei de date Supabase (conturi + proiecte în cloud).
-- Rulează O SINGURĂ DATĂ: Supabase → proiectul tău → SQL Editor → New query → lipește tot fișierul → Run.
-- Se poate rula din nou fără pierderi (create … if not exists / create or replace / drop policy if exists).
-- RLS e activat pe toate tabelele: fiecare utilizator vede și modifică DOAR rândurile lui.
-- Aplicația folosește doar cheia publică „anon”; cheia service_role nu se pune niciodată în aplicație.

create extension if not exists pgcrypto;

-- ------------------------------------------------------------------ profiles (1 rând per cont)
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  nume        text,
  firma       text,
  atestat     text,
  cartus      jsonb not null default '{}'::jsonb,      -- datele proiectantului pentru cartuș (profilele de firmă)
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- ------------------------------------------------------------------ projects (planșele)
create table if not exists public.projects (
  id          uuid primary key default gen_random_uuid(),
  owner       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  titlu       text not null default 'Schemă fără titlu',
  tip_schema  text,
  model       jsonb not null,
  miniatura   text,                                     -- imagine mică (data:image/jpeg;base64,…), opțională
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists projects_owner_updated on public.projects (owner, updated_at desc);

-- ------------------------------------------------------------------ project_versions (istoric la salvare)
create table if not exists public.project_versions (
  id          bigint generated always as identity primary key,
  project_id  uuid not null references public.projects (id) on delete cascade,
  owner       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  titlu       text,
  model       jsonb not null,
  created_at  timestamptz not null default now()
);
create index if not exists project_versions_project on public.project_versions (project_id, created_at desc);

-- ------------------------------------------------------------------ updated_at automat
create or replace function public.set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists profiles_updated_at on public.profiles;
create trigger profiles_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();
drop trigger if exists projects_updated_at on public.projects;
create trigger projects_updated_at before update on public.projects
  for each row execute function public.set_updated_at();

-- proprietarul nu se poate schimba (nici la insert nu se poate pune alt cont)
create or replace function public.owner_fix() returns trigger
language plpgsql as $$
begin
  if tg_op = 'INSERT' then
    new.owner := auth.uid();
  else
    new.owner := old.owner;
  end if;
  return new;
end $$;
drop trigger if exists projects_owner_fix on public.projects;
create trigger projects_owner_fix before insert or update on public.projects
  for each row execute function public.owner_fix();
drop trigger if exists project_versions_owner_fix on public.project_versions;
create trigger project_versions_owner_fix before insert on public.project_versions
  for each row execute function public.owner_fix();

-- istoricul păstrează ultimele 50 de versiuni pentru fiecare proiect
create or replace function public.versions_trim() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  delete from public.project_versions v
   where v.project_id = new.project_id
     and v.id not in (select id from public.project_versions
                       where project_id = new.project_id order by created_at desc, id desc limit 50);
  return null;
end $$;
drop trigger if exists project_versions_trim on public.project_versions;
create trigger project_versions_trim after insert on public.project_versions
  for each row execute function public.versions_trim();

-- profilul se creează singur la înregistrare
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, nume) values (new.id, coalesce(new.raw_user_meta_data ->> 'nume', ''))
  on conflict (id) do nothing;
  return new;
end $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ------------------------------------------------------------------ Row Level Security
alter table public.profiles         enable row level security;
alter table public.projects         enable row level security;
alter table public.project_versions enable row level security;

drop policy if exists "profil: citește propriul" on public.profiles;
drop policy if exists "profil: creează propriul" on public.profiles;
drop policy if exists "profil: modifică propriul" on public.profiles;
create policy "profil: citește propriul"  on public.profiles for select to authenticated using (id = auth.uid());
create policy "profil: creează propriul"  on public.profiles for insert to authenticated with check (id = auth.uid());
create policy "profil: modifică propriul" on public.profiles for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

drop policy if exists "proiecte: citește proprii" on public.projects;
drop policy if exists "proiecte: creează proprii" on public.projects;
drop policy if exists "proiecte: modifică proprii" on public.projects;
drop policy if exists "proiecte: șterge proprii" on public.projects;
create policy "proiecte: citește proprii"  on public.projects for select to authenticated using (owner = auth.uid());
create policy "proiecte: creează proprii"  on public.projects for insert to authenticated with check (owner = auth.uid());
create policy "proiecte: modifică proprii" on public.projects for update to authenticated using (owner = auth.uid()) with check (owner = auth.uid());
create policy "proiecte: șterge proprii"   on public.projects for delete to authenticated using (owner = auth.uid());

drop policy if exists "versiuni: citește proprii" on public.project_versions;
drop policy if exists "versiuni: creează proprii" on public.project_versions;
drop policy if exists "versiuni: șterge proprii" on public.project_versions;
create policy "versiuni: citește proprii" on public.project_versions for select to authenticated using (owner = auth.uid());
create policy "versiuni: creează proprii" on public.project_versions for insert to authenticated
  with check (owner = auth.uid() and exists (select 1 from public.projects p where p.id = project_id and p.owner = auth.uid()));
create policy "versiuni: șterge proprii"  on public.project_versions for delete to authenticated using (owner = auth.uid());

-- accesul de bază (RLS de mai sus filtrează rândurile); utilizatorii anonimi nu văd nimic
revoke all on public.profiles, public.projects, public.project_versions from anon;
grant select, insert, update on public.profiles to authenticated;
grant select, insert, update, delete on public.projects to authenticated;
grant select, insert, delete on public.project_versions to authenticated;
