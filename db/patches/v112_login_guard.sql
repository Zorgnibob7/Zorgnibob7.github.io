-- Beach Torneo V11.2 — protezione complementare login mini-organizzatore.
-- Incrementale sulla V11.1. NON modifica tornei, punteggi o password.
-- Eseguire manualmente SOLTANTO DOPO la verifica dei test e un backup.
-- Non è una difesa WAF/IP: il blocco è condiviso per torneo e può
-- temporaneamente ritardare anche l'accesso legittimo in caso di abuso.
BEGIN;

DO $$ BEGIN
 IF to_regclass('public.v111_login_attempts') IS NULL OR
    to_regprocedure('public.v111_login(integer,text,text)') IS NULL OR
    to_regclass('public.tournament_sessions') IS NULL THEN
  RAISE EXCEPTION 'Serve lo schema V11.1: aggiornamento V11.2 annullato';
 END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.v112_login_limits (
 tournament_id integer PRIMARY KEY
   REFERENCES public.tournament(id) ON DELETE CASCADE,
 failures integer NOT NULL DEFAULT 0 CHECK (failures BETWEEN 0 AND 19),
 window_started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 blocked_until timestamptz
);

ALTER TABLE public.v112_login_limits ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.v112_login_limits FROM PUBLIC, anon, authenticated;

-- Conserviamo la firma RPC V11.1: l'HTML pubblicato resta compatibile.
-- Doppio limite: per browser (V11.1) e aggregato per torneo (V11.2).
-- L'aggregato non dipende da p_client_id, che è modificabile dal chiamante.
-- La riga FOR UPDATE serializza i tentativi concorrenti sullo stesso torneo.
CREATE OR REPLACE FUNCTION public.v111_login(
 p_tournament_id integer, p_pin text, p_client_id text
)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
 s public.secrets%ROWTYPE;
 guard public.v112_login_limits%ROWTYPE;
 token text;
 h text;
 client_blocked timestamptz;
 now_at timestamptz;
BEGIN
 IF p_client_id IS NULL OR length(p_client_id)<20 OR length(p_client_id)>128 THEN
  RETURN NULL;
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM public.tournament
   WHERE id=p_tournament_id AND status='active'
 ) THEN RETURN NULL; END IF;

 INSERT INTO public.v112_login_limits(tournament_id)
 VALUES(p_tournament_id) ON CONFLICT(tournament_id) DO NOTHING;
 SELECT * INTO guard FROM public.v112_login_limits
 WHERE tournament_id=p_tournament_id FOR UPDATE;
 now_at=clock_timestamp();

 IF guard.blocked_until>now_at THEN RETURN NULL; END IF;
 IF guard.window_started_at<=now_at-interval '60 seconds' THEN
  UPDATE public.v112_login_limits
  SET failures=0, window_started_at=now_at, blocked_until=NULL
  WHERE tournament_id=p_tournament_id;
 END IF;

 h=encode(extensions.digest(p_client_id,'sha256'),'hex');
 SELECT blocked_until INTO client_blocked FROM public.v111_login_attempts
 WHERE tournament_id=p_tournament_id AND client_hash=h;
 IF client_blocked>now_at THEN RETURN NULL; END IF;

 SELECT * INTO s FROM public.secrets WHERE id=p_tournament_id;
 IF NOT FOUND OR s.pin_hash IS NULL THEN RETURN NULL; END IF;

 IF p_pin IS NULL OR octet_length(p_pin)<12 OR octet_length(p_pin)>72
    OR extensions.crypt(p_pin,s.pin_hash) IS DISTINCT FROM s.pin_hash THEN

  -- Al 20° tentativo errato nell'arco di 60s: blocco di 60s.
  UPDATE public.v112_login_limits
  SET blocked_until=CASE WHEN failures>=19
                         THEN now_at+interval '60 seconds' ELSE NULL END,
      window_started_at=CASE WHEN failures>=19
                             THEN now_at ELSE window_started_at END,
      failures=CASE WHEN failures>=19 THEN 0 ELSE failures+1 END
  WHERE tournament_id=p_tournament_id;

  -- Manteniamo il limite per browser già presente nella V11.1.
  INSERT INTO public.v111_login_attempts(tournament_id,client_hash,failed,blocked_until)
  VALUES(p_tournament_id,h,1,NULL)
  ON CONFLICT(tournament_id,client_hash) DO UPDATE
  SET blocked_until=CASE WHEN public.v111_login_attempts.failed>=4
                         THEN now_at+interval '60 seconds' ELSE NULL END,
      failed=CASE WHEN public.v111_login_attempts.failed>=4
                  THEN 0 ELSE public.v111_login_attempts.failed+1 END;
  RETURN NULL;
 END IF;

 DELETE FROM public.v111_login_attempts
 WHERE tournament_id=p_tournament_id AND client_hash=h;
 UPDATE public.v112_login_limits
 SET failures=0, window_started_at=now_at, blocked_until=NULL
 WHERE tournament_id=p_tournament_id;
 DELETE FROM public.tournament_sessions WHERE expires_at<=clock_timestamp();

 token=encode(extensions.gen_random_bytes(32),'hex');
 INSERT INTO public.tournament_sessions(token_hash,expires_at,tournament_id)
 VALUES(encode(extensions.digest(token,'sha256'),'hex'),
        clock_timestamp()+interval '24 hours',p_tournament_id);
 RETURN token;
END $$;

REVOKE ALL ON FUNCTION public.v111_login(integer,text,text)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.v111_login(integer,text,text)
 TO anon,authenticated;
COMMIT;

-- Verifica non distruttiva dopo l'applicazione:
-- SELECT relrowsecurity FROM pg_class WHERE oid='public.v112_login_limits'::regclass;
-- SELECT has_table_privilege('anon','public.v112_login_limits','SELECT');
-- SELECT pg_get_functiondef('public.v111_login(integer,text,text)'::regprocedure);
