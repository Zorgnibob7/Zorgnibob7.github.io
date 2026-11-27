#!/usr/bin/env python3
"""Regressioni complementari V11.1. Test locali: NON contattano Supabase."""
import shutil
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML = Path(sys.argv[1]).resolve()
SRC = HTML.read_text(encoding='utf8')
RESULTS = []
ERRORS = []

def check(title, fn):
    try:
        assert fn() is not False
        RESULTS.append((title, True))
        print('PASS', title, flush=True)
    except Exception as err:
        RESULTS.append((title, False))
        print('FAIL', title, repr(err), flush=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        executable_path=shutil.which('chromium') or None,
        args=['--no-sandbox']
    )
    ctx = browser.new_context(viewport={'width':390,'height':844}, accept_downloads=True)
    p = ctx.new_page()
    p.on('pageerror', lambda err: ERRORS.append(str(err)))
    # Isolated storage even on about:blank. No persistent user browser state.
    p.evaluate("""() => {let store={};Object.defineProperty(window,'localStorage',{configurable:true,value:{
      getItem:k=>Object.prototype.hasOwnProperty.call(store,k)?store[k]:null,
      setItem:(k,v)=>{store[k]=String(v)},removeItem:k=>{delete store[k]},clear:()=>{store={}}
    }});}""")
    p.set_content(SRC, wait_until='domcontentloaded')
    p.wait_for_selector('#v')

    check('Beach: punteggio a tempo e pareggio ammesso', lambda:p.evaluate("v91BeachValid('tempo',21,15,15)===''"))
    check('Beach: punti fissi richiedono punteggio esatto', lambda:p.evaluate("v91BeachValid('punti_fissi',21,21,19)==='' && v91BeachValid('punti_fissi',21,23,21)!==''"))
    check('Beach: set unico richiede due punti di vantaggio', lambda:p.evaluate("v91BeachValid('set_unico',21,23,21)==='' && v91BeachValid('set_unico',21,21,20)!==''"))
    check('Beach: playoff non ammettono risultato pari', lambda:p.evaluate("v91BeachValid('tempo',21,15,15,true)!==''"))
    check('Padel a tempo: pareggio nel risultato', lambda:p.evaluate("(()=>{const m={padelResult:{mode:'timed',games:[5,5]}}; const q=v91Metric(m,{a:5,b:5,d:1},'padel'); return q.win===null&&q.ga===5&&q.gb===5})()"))
    check('Classifica: considera il quarto criterio di spareggio', lambda:p.evaluate("v91Compare([1,0,1,21],[1,0,1,25])>0 && v91Compare([1,0,1,25],[1,0,1,21])<0"))
    check('Classifica: ordinamento effettivo con pari vittorie e differenza punti', lambda:p.evaluate("""(()=>{
       const ms=[{id:'0-1',s:0,f:1,a:['Alfa','X'],b:['Y','Z']},{id:'1-1',s:1,f:1,a:['Beta','U'],b:['V','W']}];
       const scores={'0-1':{a:21,b:20,d:1},'1-1':{a:25,b:24,d:1}};
       const ranked=v91Rank(['Alfa','X','Y','Z','Beta','U','V','W'],[],ms,m=>scores[m.id],'beach','v');
       const alpha=ranked.find(x=>x.p==='Alfa'),beta=ranked.find(x=>x.p==='Beta');
       return alpha.v===beta.v && alpha.pf-alpha.ps===beta.pf-beta.ps && beta.r<alpha.r;
    })()"""))
    check('Backup JSON: snapshot e validazione compatibili', lambda:p.evaluate("(()=>{const b=v6Snapshot();const q=v6ValidateBackup(b);return b.schema==='beach-torneo-backup'&&JSON.stringify(q.torneo)===JSON.stringify(torneo)})()"))
    check('Backup JSON: rifiuta anagrafiche con nomi duplicati', lambda:p.evaluate("""(()=>{const b=v6Snapshot();b.tournament.players=[{id:'a',name:'Omonimo',gender:'M'},{id:'b',name:'Omonimo',gender:'F'}];try{v6ValidateBackup(b);return false}catch(e){return /duplicati/i.test(e.message)}})()"""))
    check('Backup JSON: rifiuta un incontro con campo/orario non valido', lambda:p.evaluate("""(()=>{const b=v6Snapshot();b.tournament.matches=[{id:'90-1',s:90,f:1,a:['A','B'],b:['C','D']}];try{v6ValidateBackup(b);return false}catch(e){return true}})()"""))
    check('HTML: nomi con markup vengono escapati nelle card delle partite', lambda:p.evaluate("""(()=>{
        const original=torneo,saved=scores;
        try{
         torneo={...defaultTournament,players:['<img src=x onerror=alert(1)>','B','C','D'].map((n,i)=>({id:'p'+i,name:n,gender:'M'})),slots:[['10:00','10:20']],matches:[{id:'0-1',s:0,f:1,a:['<img src=x onerror=alert(1)>','B'],b:['C','D']}],numCourts:1};scores={};
         const html=renderTurni();return html.includes('&lt;img')&&!html.includes('<img src=x onerror=alert(1)>');
        } finally{torneo=original;scores=saved;}
    })()"""))

    def conflict_visibility():
        button = p.locator('#v111-resolve')
        assert button.is_hidden()
        p.evaluate("LIVE=true;EDITOR=true;v111Conflict=true;v9Status()")
        try:
            assert button.is_visible()
        finally:
            p.evaluate("LIVE=false;v111Conflict=false;v9Status()")
        assert button.is_hidden()
    check('Conflitto: visibile solo durante un conflitto online', conflict_visibility)

    def player_timing():
        now = p.evaluate("new Date().setHours(13,40,0,0)")
        page = ctx.new_page()
        try:
            html = p.evaluate("""stamp=>{
                const orig=torneo;
                try {
                    const match=(s,a,b)=>({id:s+'-1',s,f:1,a,b});
                    torneo={...defaultTournament,players:'ABCDEFGHIJKL'.split('').map(name=>({name})),
                        slots:[['14:00','14:20'],['14:20','14:40'],['14:40','15:00']],
                        matches:[{...match(0,['E','F'],['G','H']),firstConfirmedAt:stamp},
                            match(1,['I','J'],['K','L']),match(2,['A','B'],['C','D'])]};
                    return buildPlayerHTML({live:true});
                } finally {torneo=orig;}
            }""",now)
            page.clock.install(time=now)
            page.set_content(html)
            page.evaluate("""()=>{st.me='A';st.tab='mie';st.res={'0-1':{d:1,a:21,b:18}};render()}""")
            banner=page.locator('.nx').first
            assert '14:00' in banner.inner_text() and '20 min' in banner.inner_text()
            page.evaluate("""()=>{M.push({s:1,f:2,a:['C','Y'],b:['Z','W']});render()}""")
            assert 'altro campo' in banner.inner_text() and 'Inizio stimato' not in banner.inner_text()
            page.evaluate("M.pop();delete M[0].firstConfirmedAt;render()")
            assert 'Una partita' in banner.inner_text() and 'Inizio stimato' not in banner.inner_text()
        finally:
            page.close()
    check('Scheda giocatore: anticipo, compagno impegnato e risultato storico', player_timing)

    def print_calendar():
        p.evaluate("""()=>{
          torneo={...defaultTournament,name:'Prova stampa QA',numCourts:1,slots:[['10:00','10:20']],matches:[{id:'0-1',s:0,f:1,a:['A','B'],b:['C','D']}],players:['A','B','C','D'].map((name,i)=>({id:'p'+i,name,gender:'M'}))};
          scores={'0-1':{a:21,b:17,d:1}};
        }""")
        with p.expect_popup(timeout=6000) as opened:
            p.evaluate("v6Print('calendar')")
        popup = opened.value
        popup.wait_for_load_state('domcontentloaded')
        html = popup.content()
        popup.close()
        assert 'A4' in html and 'Prova stampa QA' in html and 'Campo 1' in html and '21' in html
        return True
    check('Stampa calendario: finestra generata con formato A4', print_calendar)

    def replan_guard():
        p.evaluate("""()=>{
          torneo={...defaultTournament,name:'Replan QA',formatType:'baraonda',targetMatches:2,numCourts:1,
            players:['A','B','C','D'].map((name,i)=>({id:'p'+i,name,gender:i<2?'M':'F'})),
            slots:[['10:00','10:20'],['10:20','10:40']],
            matches:[{id:'0-1',s:0,f:1,a:['A','B'],b:['C','D']},{id:'1-1',s:1,f:1,a:['A','C'],b:['B','D']}]
          };scores={'0-1':{a:21,b:18,d:1}};
        }""")
        state = p.evaluate('JSON.stringify({t:torneo,s:scores})')
        p.evaluate('v6ReplanDialog()')
        assert p.locator('#modal').is_visible()
        assert p.locator('#v6-cutoff option').first.get_attribute('value') == '1'
        assert p.evaluate('JSON.stringify({t:torneo,s:scores})') == state
        p.locator('[data-act=close-modal]').click()
        return True
    check('Riorganizzazione: impedisce di modificare il turno confermato', replan_guard)

    def small_screen():
        p.evaluate("document.getElementById('modal')?.remove();activeTab='regole';render()")
        for width in (320,390):
            p.set_viewport_size({'width':width,'height':780})
            p.wait_for_timeout(100)
            result=p.evaluate("""()=>({doc:document.documentElement.scrollWidth,view:innerWidth,
               visible:!!document.querySelector('#v'),nav:!!document.querySelector('.nav')})""")
            assert result['visible'] and result['nav'] and result['doc'] <= result['view']+4,(width,result)
        return True
    check('Mobile: pagina accessibile a 320 e 390 px senza overflow globale', small_screen)
    check('Browser: nessuna eccezione JavaScript', lambda:len(ERRORS)==0)
    p.close()
    browser.close()

passed=sum(ok for _,ok in RESULTS)
print(f'\n{passed}/{len(RESULTS)} test aggiuntivi superati', flush=True)
raise SystemExit(passed!=len(RESULTS))
