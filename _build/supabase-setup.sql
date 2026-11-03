-- ============================================================================
--  Shared comments for a course site built with this kit.
--
--  Paste this whole file into the Supabase SQL Editor and run it once.
--  Put the project URL and the publishable key into site.json under
--  "comments": { "url": ..., "anon_key": ... }
--
--  BEFORE YOU RUN IT: change the admin key on the marked line near the bottom.
--  That key is what lets you delete anyone's comment. It never appears in the
--  site's HTML -- you paste it into your own browser once, and it stays in that
--  browser's localStorage.
-- ============================================================================

-- ---------------------------------------------------------------- the table
create table if not exists public.comments (
  id           bigint generated always as identity primary key,
  page         text        not null,          -- manifest name: part3, t7, mock2
  cid          text,                          -- card id, or NULL for a page-wide note
  author       text        not null,
  body         text        not null,
  owner_token  text        not null,          -- random per browser; allows self-delete
  created_at   timestamptz not null default now(),

  -- Enforced here and not only in the browser, because the browser is not the
  -- only thing that can call the API.
  constraint author_len check (char_length(author) between 1 and 40),
  constraint body_len   check (char_length(body)   between 1 and 2000),
  constraint page_len   check (char_length(page)   between 1 and 40),
  constraint cid_len    check (cid is null or char_length(cid) between 1 and 40)
);

create index if not exists comments_page_idx on public.comments (page, created_at);

-- ------------------------------------------------------- the admin key store
-- Its own table so the key is never in the site's source. RLS is on and there
-- is deliberately NO policy, so the anonymous role cannot read it at all --
-- only the SECURITY DEFINER function below can, because that function runs as
-- its owner rather than as the caller.
create table if not exists public.admin_key (
  key text primary key
);
alter table public.admin_key enable row level security;

-- ------------------------------------------------------------------ policies
alter table public.comments enable row level security;

drop policy if exists comments_read  on public.comments;
drop policy if exists comments_write on public.comments;

-- anyone may read
create policy comments_read on public.comments
  for select to anon, authenticated
  using (true);

-- anyone may add, and nothing else. No update policy and no delete policy
-- exist, so those operations are refused outright for the anonymous role.
create policy comments_write on public.comments
  for insert to anon, authenticated
  with check (
    char_length(author) between 1 and 40
    and char_length(body) between 1 and 2000
    and char_length(owner_token) between 8 and 64
  );

-- --------------------------------------------------------------- deletion
-- The only way a row is ever removed. It deletes at most one row, and only
-- when the caller proves one of two things: they hold the random token that
-- created the comment (so it is theirs), or they hold the admin key.
create or replace function public.delete_comment(p_id bigint, p_token text)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  gone integer;
begin
  if p_token is null or char_length(p_token) < 8 then
    return false;
  end if;

  delete from public.comments
   where id = p_id
     and (owner_token = p_token
          or exists (select 1 from public.admin_key where key = p_token));

  get diagnostics gone = row_count;
  return gone > 0;
end;
$$;

revoke all on function public.delete_comment(bigint, text) from public;
grant execute on function public.delete_comment(bigint, text) to anon, authenticated;

-- ------------------------------------------------- owner hash (read-safe)
-- Visitors read sha256(owner_token), never the token -- see supabase-fix-owner-hash.sql.
alter table public.comments add column if not exists owner_hash text;

-- Computed by the database on every insert/update, so a client cannot forge it.
create or replace function public.comments_hash_owner()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.owner_hash := encode(sha256(convert_to(new.owner_token, 'UTF8')), 'hex');
  return new;
end;
$$;

drop trigger if exists comments_hash_owner on public.comments;
create trigger comments_hash_owner
  before insert or update on public.comments
  for each row execute function public.comments_hash_owner();

-- Backfill rows written before this script.
update public.comments
   set owner_hash = encode(sha256(convert_to(owner_token, 'UTF8')), 'hex')
 where owner_hash is null;

-- Column-level read access: everything except owner_token.
revoke select on public.comments from anon, authenticated;
grant select (id, page, cid, author, body, owner_hash, created_at)
  on public.comments to anon, authenticated;

-- ------------------------------------------------------------- YOUR ADMIN KEY
-- Change this string, then run. Keep it somewhere you will not lose it.
insert into public.admin_key (key)
values ('CHANGE-ME-to-a-long-random-string')
on conflict (key) do nothing;

-- ============================================================================
--  After running, in your own browser's console, once, on the site:
--
--      localStorage.setItem('st2admin', 'the string you chose above')
--
--  From then on every comment shows a delete link for you. Nobody else sees
--  it, because nobody else has the key.
--
--  To read everything from the dashboard:  Table Editor -> comments.
--  To wipe one page:   delete from comments where page = 'part3';
--  To wipe everything: truncate comments;
--
--  If spam ever starts: replace the insert policy with one that also requires
--  a shared class password, by adding a `write_key` table the same way, and
--  a `with check (exists (select 1 from write_key where key = post_key))`.
-- ============================================================================
