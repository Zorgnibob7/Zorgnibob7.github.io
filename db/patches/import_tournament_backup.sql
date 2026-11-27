begin;
create or replace function public.import_tournament_backup(
    p_request uuid, p_json text, p_pin text, p_rows jsonb
) returns integer
language plpgsql security invoker set search_path = ''
as $$
declare
    prefix text := 'backup-' || p_request::text;
    tournament_id integer;
begin
    if not public.v11_is_architect() then
        raise exception 'Accesso Architetto richiesto';
    end if;
    if p_request is null then
        raise exception 'Identificativo importazione mancante';
    end if;
    -- A retry after a lost response returns the same tournament.
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(prefix, 0));
    select t.id into tournament_id from public.tournament t
    where t.slug = prefix || '-' || t.id::text;
    if found then return tournament_id; end if;

    tournament_id := public.v11_create_tournament(p_json, prefix, p_pin);
    perform public.v111_commit_state(tournament_id, null, 0, p_json, p_rows);
    return tournament_id;
end;
$$;

revoke all on function public.import_tournament_backup(uuid,text,text,jsonb) from public, anon;
grant execute on function public.import_tournament_backup(uuid,text,text,jsonb) to authenticated;
commit;
