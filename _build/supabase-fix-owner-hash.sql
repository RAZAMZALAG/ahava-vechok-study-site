-- ============================================================================
--  Fix: stop exposing comment owner tokens.
--
--  owner_token is the credential delete_comment() checks, but the read policy
--  let anyone select it -- so any visitor could read another visitor's token
--  and delete their comment. After this script, visitors can read only a
--  SHA-256 of the token (owner_hash); the page compares hashes to decide which
--  comments are "mine", and the token itself never leaves the database.
--
--  Paste into the Supabase SQL Editor and run once. Safe to run again.
-- ============================================================================

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
