-- Database ephemeral for CI: intentionally simplified V11.1 login contract.
-- Do NOT run against a real Supabase project.
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
GRANT USAGE ON SCHEMA public TO anon,authenticated;
CREATE SCHEMA extensions;
CREATE EXTENSION pgcrypto WITH SCHEMA extensions;

CREATE TABLE public.tournament (
 id integer PRIMARY KEY,
 status text NOT NULL CHECK (status IN ('active','archived'))
);
CREATE TABLE public.secrets (
 id integer PRIMARY KEY REFERENCES public.tournament(id) ON DELETE CASCADE,
 pin_hash text
);
CREATE TABLE public.v111_login_attempts (
 tournament_id integer NOT NULL REFERENCES public.tournament(id) ON DELETE CASCADE,
 client_hash text NOT NULL,
 failed integer NOT NULL DEFAULT 0,
 blocked_until timestamptz,
 PRIMARY KEY(tournament_id,client_hash)
);
CREATE TABLE public.tournament_sessions (
 token_hash text PRIMARY KEY,
 expires_at timestamptz NOT NULL,
 tournament_id integer NOT NULL REFERENCES public.tournament(id) ON DELETE CASCADE
);

ALTER TABLE public.tournament ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.secrets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.v111_login_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tournament_sessions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.tournament,public.secrets,
 public.v111_login_attempts,public.tournament_sessions
 FROM PUBLIC,anon,authenticated;

-- Stub con la stessa firma RPC esistente: la patch deve sostituirla.
CREATE FUNCTION public.v111_login(
 p_tournament_id integer,p_pin text,p_client_id text
) RETURNS text LANGUAGE sql SECURITY DEFINER SET search_path=''
AS $$ SELECT NULL::text $$;

INSERT INTO public.tournament(id,status) VALUES (1,'active'),(2,'active');
-- Cost factor 4: solo per accelerare i test effimeri.
INSERT INTO public.secrets(id,pin_hash) VALUES
 (1,extensions.crypt('VALID-PASSWORD-111',extensions.gen_salt('bf',4))),
 (2,extensions.crypt('VALID-PASSWORD-222',extensions.gen_salt('bf',4)));
