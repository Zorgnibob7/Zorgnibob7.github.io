#!/usr/bin/env python3
"""Run the V11.1 browser QA suites against index.html, without contacting Supabase.

Usage: python qa/esegui_test.py index.html
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = re.compile(r'\bconst\s+CFG\s*=\s*(?:null|\{[^;\n]*\})\s*;')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('html', nargs='?', default='index.html')
    args = parser.parse_args()
    path = Path(args.html).resolve()
    if not path.is_file():
        parser.error(f'File non trovato: {path}')
    src = path.read_text(encoding='utf-8')
    if 'v111_commit_state' not in src or 'v111_get_snapshot' not in src:
        parser.error('Il file non sembra contenere la versione V11.1.')
    transformed, count = CONFIG.subn('const CFG=null;', src, count=1)
    if count != 1:
        parser.error('Configurazione CFG non riconosciuta.')
    # The published file is never edited. Tests use an isolated temporary copy,
    # and intercept all requests using a mock backend.
    with tempfile.TemporaryDirectory(prefix='qa_v111_') as tmp:
        sanitized = Path(tmp) / 'Beach_Torneo_Unificato_v11_1.html'
        sanitized.write_text(transformed, encoding='utf-8')
        print('File sottoposto a test:', path.name, flush=True)
        print('Configurazione Supabase sostituita soltanto nella copia temporanea.', flush=True)
        suites = ['test_regressioni_v11_1.py', 'test_aggiuntivi.py']
        codes = []
        for script in suites:
            print(f'\n=== {script} ===', flush=True)
            result = subprocess.run(
                [sys.executable, str(HERE / script), str(sanitized)],
                cwd=tmp,
                check=False,
            )
            codes.append(result.returncode)
        if all(code == 0 for code in codes):
            print('\nPASS: entrambe le suite superate (backend simulato).')
            return 0
        print('\nFAIL: almeno una suite non e stata superata.')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
