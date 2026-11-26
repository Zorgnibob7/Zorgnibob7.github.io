\set ON_ERROR_STOP on
\echo 'Testing V11.2 login guard against disposable PostgreSQL'

-- L'endpoint deve restare invocabile, ma nessuna tabella di stato deve essere pubblica.
DO $$
BEGIN
 IF NOT (SELECT c.relrowsecurity FROM pg_class c
         WHERE c.oid='public.v112_login_limits'::regclass) THEN
  RAISE EXCEPTION 'RLS missing on login rate limit table';
 END IF;
 IF has_table_privilege('anon','public.v112_login_limits','SELECT')
   OR has_table_privilege('authenticated','public.v112_login_limits','SELECT') THEN
  RAISE EXCEPTION 'Rate limit table unexpectedly readable';
 END IF;
 IF NOT has_function_privilege(
       'anon','public.v111_login(integer,text,text)','EXECUTE') THEN
  RAISE EXCEPTION 'Anon V11.1 RPC access broken';
 END IF;
END $$;

SET ROLE anon;
-- Rotazione di 20 client_id diversi: il vecchio limite browser non basta,
-- quello aggregato deve invece scattare e bloccare il 21° tentativo.
DO $$
DECLARE i integer; result text;
BEGIN
 FOR i IN 1..20 LOOP
  result:=public.v111_login(1,'WRONG-PASSWORD-123',
                            'rotating-client-identifier-'||i::text);
  IF result IS NOT NULL THEN
   RAISE EXCEPTION 'Invalid password accepted at attempt %',i;
  END IF;
 END LOOP;
 result:=public.v111_login(1,'VALID-PASSWORD-111',
                           'another-completely-new-client');
 IF result IS NOT NULL THEN
  RAISE EXCEPTION 'Rotating client IDs bypassed the global throttle';
 END IF;

 -- Un attacco al torneo 1 non deve bloccare il torneo 2.
 result:=public.v111_login(2,'VALID-PASSWORD-222',
                           'independent-correct-client-2222');
 IF result IS NULL OR result !~ '^[a-f0-9]{64}$' THEN
  RAISE EXCEPTION 'Independent tournament wrongly blocked';
 END IF;

 IF public.v111_login(2,'VALID-PASSWORD-222','short') IS NOT NULL THEN
  RAISE EXCEPTION 'Invalid client ID accepted';
 END IF;
END $$;
RESET ROLE;

DO $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM public.v112_login_limits
                WHERE tournament_id=1 AND blocked_until>clock_timestamp()) THEN
  RAISE EXCEPTION 'Global throttle state missing';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM public.tournament_sessions WHERE tournament_id=2) THEN
  RAISE EXCEPTION 'Valid login did not create a session';
 END IF;
END $$;

-- Avanzamento temporale controllato senza attendere 60s nella CI.
UPDATE public.v112_login_limits
SET blocked_until=clock_timestamp()-interval '1 second',
    window_started_at=clock_timestamp()-interval '2 minutes',
    failures=0
WHERE tournament_id=1;

SET ROLE anon;
DO $$
DECLARE token text;
BEGIN
 token:=public.v111_login(1,'VALID-PASSWORD-111','unblocked-correct-client-aaaa');
 IF token IS NULL OR token !~ '^[a-f0-9]{64}$' THEN
  RAISE EXCEPTION 'Valid login failed after cooldown';
 END IF;

 -- Il limite secondario del browser continua a funzionare.
 PERFORM public.v111_login(1,'WRONG-PASSWORD-123','fixed-client-identifier-aaaaaa');
 PERFORM public.v111_login(1,'WRONG-PASSWORD-123','fixed-client-identifier-aaaaaa');
 PERFORM public.v111_login(1,'WRONG-PASSWORD-123','fixed-client-identifier-aaaaaa');
 PERFORM public.v111_login(1,'WRONG-PASSWORD-123','fixed-client-identifier-aaaaaa');
 PERFORM public.v111_login(1,'WRONG-PASSWORD-123','fixed-client-identifier-aaaaaa');
 IF public.v111_login(1,'VALID-PASSWORD-111',
                     'fixed-client-identifier-aaaaaa') IS NOT NULL THEN
  RAISE EXCEPTION 'Per-browser throttle no longer working';
 END IF;
 IF public.v111_login(1,'VALID-PASSWORD-111',
                     'different-client-identifier-zzzz') IS NULL THEN
  RAISE EXCEPTION 'Client-specific throttle leaked to unrelated client';
 END IF;
END $$;
RESET ROLE;

UPDATE public.tournament SET status='archived' WHERE id=1;

SET ROLE anon;
DO $$
BEGIN
 IF public.v111_login(1,'VALID-PASSWORD-111',
                     'another-client-identifier-zzzz') IS NOT NULL THEN
  RAISE EXCEPTION 'Archived tournament accepted a login';
 END IF;
END $$;
RESET ROLE;

\echo 'PASS: PostgreSQL integration test (anon role, 2 tournaments, rotating IDs, cooldown, RLS)'
