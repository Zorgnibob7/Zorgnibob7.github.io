-- Run only after fixture.sql in disposable CI PostgreSQL.
alter table public.tournament add column slug text unique;
grant select (id,slug) on public.tournament to authenticated;
create policy read_tournament on public.tournament for select to authenticated using (true);
create table public.import_test_scores (id integer, rows jsonb);
create sequence public.import_test_id start with 10;
create function public.v11_is_architect() returns boolean language sql as
$$ select coalesce(current_setting('qa.architect',true),'')='yes' $$;
create function public.v11_create_tournament(text,text,text) returns integer language plpgsql security definer as $$
declare new_id integer := nextval('public.import_test_id');
begin
 insert into public.tournament(id,status,slug) values (new_id,'active',$2||'-'||new_id);
 return new_id;
end $$;
create function public.v111_commit_state(integer,text,bigint,text,jsonb) returns bigint language plpgsql security definer as $$
begin
 if jsonb_typeof($5)<>'array' then raise exception 'invalid scores'; end if;
 insert into public.import_test_scores values ($1,$5);
 return 1;
end $$;
\ir ../patches/import_tournament_backup.sql
set role authenticated;
set qa.architect='yes';
do $$
declare req uuid:=gen_random_uuid(); created integer; retry integer; failed_req uuid:=gen_random_uuid();
begin
 created:=public.import_tournament_backup(req,'{}','test password','[{"id":"0-1","a":7}]');
 retry:=public.import_tournament_backup(req,'{}','test password','[]');
 if created<>retry then raise exception 'Duplicate tournament'; end if;
 begin
  perform public.import_tournament_backup(failed_req,'{}','test password','{}');
  raise exception 'Expected score validation failure';
 exception when others then
  if sqlerrm<>'invalid scores' then raise; end if;
 end;
 if exists(select 1 from public.tournament where slug like 'backup-'||failed_req||'-%') then
  raise exception 'Partial tournament';
 end if;
end $$;
reset role;
do $$ begin
 if (select count(*) from public.import_test_scores)<>1 or not exists(
   select 1 from public.import_test_scores where rows='[{"id":"0-1","a":7}]'::jsonb
 ) then raise exception 'Score import mismatch'; end if;
 if has_function_privilege('anon','public.import_tournament_backup(uuid,text,text,jsonb)','EXECUTE') then
  raise exception 'Unexpected grant'; end if;
end $$;
