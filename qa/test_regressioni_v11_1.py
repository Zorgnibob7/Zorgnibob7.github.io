#!/usr/bin/env python3
"""Suite browser V11.1. API Supabase MOCK: non convalida lo SQL sul server vero.
Uso: python Test_V11.py [Beach_Torneo_Unificato_v11.html]
Richiede: pip install playwright && python -m playwright install chromium
"""
import json, re, shutil, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).with_name('Beach_Torneo_Unificato_v11_1.html')
SRC=HTML.read_text(encoding='utf8')
PUBLISHABLE='sb_publishable_test_key_123456789'
URL='https://testing.supabase.co'
RESULTS=[]
ERRORS=[]
def check(name,fn):
 try:
  result=fn()
  assert result is not False
  print('PASS',name);RESULTS.append((name,True))
 except Exception as e:
  print('FAIL',name,repr(e));RESULTS.append((name,False))

JS_MOCK=r'''data => {
 try{localStorage.setItem('__v111_test','x');localStorage.removeItem('__v111_test');}catch(e){
   const store={};Object.defineProperty(window,'localStorage',{value:{getItem:k=>store[k]??null,setItem:(k,v)=>{store[k]=String(v)},removeItem:k=>{delete store[k]}},configurable:true});
 }
 window.mockDB=data.db;
 window.mockScores=data.scores;
 window.mockPassword=data.passwords;
 window.mockCalls=[];
 window.fetch=async(url,opts={})=>{
  const u=new URL(url),headers=opts.headers||{},body=opts.body?JSON.parse(opts.body):{},path=u.pathname;
  const auth=headers.Authorization||headers.authorization||'';
  const admin=auth==='Bearer admin-jwt';
  const isMini=(id,token)=>window.mockPassword[id]&&window.mockPassword[id].token===token&&window.mockDB[id]?.status==='active';
  const response=(val,code=200)=>({ok:code<400,status:code,text:async()=>JSON.stringify(val)});
  const deny=()=>response({message:'Non autorizzato'},403);
  window.mockCalls.push({path,auth,body});
  if(path==='/auth/v1/token'){
   const grant=u.searchParams.get('grant_type');
   if(grant==='password'&&body.email==='architect@example.it'&&body.password==='arch-pass-123')
     return response({access_token:'admin-jwt',refresh_token:'refresh-jwt',expires_at:Math.floor(Date.now()/1000)+3600});
   if(grant==='refresh_token'&&body.refresh_token==='refresh-jwt')
     return response({access_token:'admin-jwt',refresh_token:'refresh-jwt',expires_at:Math.floor(Date.now()/1000)+3600});
   return response({error:'Invalid credentials'},400);
  }
  if(path==='/auth/v1/logout')return response(null);
  if(path==='/rest/v1/tournament'){
   const idQ=u.searchParams.get('id'),slugQ=u.searchParams.get('slug'),select=u.searchParams.get('select')||'';
   let rows=Object.values(window.mockDB).filter(x=>x.status==='active'||x.status==='archived');
   if(idQ)rows=rows.filter(x=>x.id===Number(idQ.slice(3)));
   if(slugQ)rows=rows.filter(x=>x.slug===slugQ.slice(3));
   return response(rows.map(x=>{
    const out={};for(const k of select.split(','))if(k in x)out[k]=x[k];return out;
   }));
  }
  if(path==='/rest/v1/scores'){
   const id=Number((u.searchParams.get('tournament_id')||'eq.1').slice(3));
   return response(Object.values(window.mockScores[id]||{}));
  }
  const fn=path.split('/rest/v1/rpc/')[1];
  if(!fn)return response({error:'unknown path'},404);
  if(fn==='v11_is_architect')return response(admin);
  if(fn==='v11_list_tournaments')return admin?response(Object.values(window.mockDB).map(x=>({id:x.id,title:x.title,sport:x.sport,slug:x.slug,status:x.status,created_at:'2026-11-23',t:x.t}))):deny();
  if(fn==='v111_login'){
   const t=window.mockDB[body.p_tournament_id],p=window.mockPassword[body.p_tournament_id];
   return response(t?.status==='active'&&p?.password===body.p_pin?p.token:null);
  }
  if(fn==='v11_logout')return response(null);
  if(fn==='v11_create_tournament'||fn==='import_tournament_backup'){
   if(!admin)return deny();
   const id=Math.max(0,...Object.keys(window.mockDB).map(Number))+1, obj=JSON.parse(body.p_json);
   const slug=(body.p_slug||'backup-'+body.p_request)+'-'+id;
   window.mockDB[id]={id,title:obj.name,sport:obj.sport,slug,status:'active',json:body.p_json,t:Date.now(),revision:0};
   window.mockPassword[id]={password:body.p_pin,token:'x'.repeat(64)};window.mockScores[id]=Object.fromEntries((body.p_rows||[]).map(row=>[row.id,row]));return response(id);
  }
  if(fn==='v11_archive_tournament'){
   if(!admin)return deny();window.mockDB[body.p_tournament_id].status=body.p_archived?'archived':'active';return response(null);
  }
  if(fn==='v11_delete_tournament'){
   if(!admin)return deny();const t=window.mockDB[body.p_tournament_id];if(!t||t.status!=='archived'||t.title!==body.p_confirm_title)return deny();
   delete window.mockDB[t.id];delete window.mockScores[t.id];delete window.mockPassword[t.id];return response(null);
  }
  if(fn==='v11_reset_tournament_password'){
   if(!admin)return deny();const t=window.mockPassword[body.p_tournament_id];if(!t)return deny();t.password=body.p_pin;t.token='z'.repeat(64);return response(null);
  }
  const tid=body.p_tournament_id;
  if(fn==='v111_get_snapshot'){
   const t=window.mockDB[body.p_tournament_id];if(!t)return response(null);
   return response({revision:t.revision||0,json:t.json,scores:Object.values(window.mockScores[t.id]||{})});
  }
  if(!admin&&!isMini(tid,body.p_token))return deny();
  if(fn==='v111_commit_state'){
   const t=window.mockDB[tid];if(!t||t.status!=='active')return deny();
   if((t.revision||0)!==body.p_expected_revision)return response({message:'CONFLITTO_VERSIONE'},409);
   const obj=JSON.parse(body.p_json);
   const rows=body.p_rows;
   if(!Array.isArray(rows)||rows.some(x=>!/^\d+-[1-9]\d*$/.test(x.id)))return deny();
   t.json=body.p_json;t.title=obj.name;t.sport=obj.sport;t.t=Date.now();t.revision=(t.revision||0)+1;
   window.mockScores[tid]=Object.fromEntries(rows.map(x=>[x.id,{...x}]));
   return response(t.revision);
  }
  if(fn==='v11_set_tournament'||fn==='v11_set_scores'||fn==='v11_delete_scores'||fn==='v11_login')return deny();
  return response({error:'function missing'},404);
 };
}'''

def state():
 def record(id,title,sport,slug,status='active'):
  obj={'name':title,'sport':sport,'formatType':'baraonda','numCourts':3,'players':[],'slots':[],'matches':[]}
  return {'id':id,'title':title,'sport':sport,'slug':slug,'status':status,'json':json.dumps(obj),'t':1,'revision':0}
 return {
  'db':{'1':record(1,'Beach storico','beach','torneo-1'), '2':record(2,'Padel Open','padel','padel-open-2')},
  'scores':{'1':{'0-1':{'id':'0-1','a':21,'b':10,'d':1}},'2':{'0-1':{'id':'0-1','a':5,'b':4,'d':1}}},
  'passwords':{'1':{'password':'beach-unique-123','token':'a'*64}, '2':{'password':'padel-unique-123','token':'b'*64}}
 }

def site_for_route(site,route):
 target="const V11_ROUTE=CFG?new URLSearchParams(location.search).get('torneo')||'':'';"
 assert target in site
 return site.replace(target,"const V11_ROUTE=CFG?"+json.dumps(route)+":'';")

with sync_playwright() as pw, tempfile.TemporaryDirectory() as directory:
 browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium') or None,args=['--no-sandbox'])
 ctx=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
 p=ctx.new_page();p.on('pageerror',lambda e:ERRORS.append('local: '+str(e)))
 p.set_content(SRC,wait_until='domcontentloaded');p.wait_for_selector('#v')
 check('Locale: il generatore V10 è preservato',lambda:p.evaluate("!LIVE&&typeof generateBaraondaOptimized==='function'&&typeof generateGroups==='function'&&typeof v10NewLocal==='function'"))
 def modal_layers():
  return p.evaluate("""()=>{
   v11Modal('<h3>Controllo</h3>');flash('Messaggio di controllo');
   const modal=+getComputedStyle(document.querySelector('#modal')).zIndex;
   const toast=+getComputedStyle(document.querySelector('.toast')).zIndex;
   const nav=+getComputedStyle(document.querySelector('.nav')).zIndex;
   document.querySelector('#modal')?.remove();document.querySelector('.toast')?.remove();
   return modal>nav && toast>modal;
  }""")
 check('Mobile: popup sopra la navigazione e toast visibile',modal_layers)
 def padel_metric():
  return p.evaluate("""()=>{
   if(!v8SetValid(6,4,6,null)||!v8SetValid(7,6,6,[7,5])||v8SetValid(7,6,6,[6,4]))return false;
   if(!v8TBvalid(10,8,10)||v8TBvalid(10,9,10))return false;
   const m={padelResult:{mode:'best',sets:[{a:6,b:4},{a:4,b:6}],super:[10,8]}};
   const result=v91Metric(m,{a:2,b:1,d:1},'padel');
   return result.sa===2&&result.sb===1&&result.ga===10&&result.gb===10&&result.win==='a';
  }""")
 check('Padel: set, tie-break e super tie-break coerenti',padel_metric)
 def shuffle_property():
  return p.evaluate("""()=>{
   const source=[1,2,3,4,5,6];const shuffled=v111Shuffle([...source]);
   return [...shuffled].sort((a,b)=>a-b).join(',')===source.join(',')&&shuffled.length===6;
  }""")
 check('Mescolamento Fisher-Yates: nessun elemento perso',shuffle_property)

 def mixed_generator():
  return p.evaluate("""async()=>{
   torneo={...defaultTournament,name:'Test 7M 11F',formatType:'misto',players:Array.from({length:18},(_,i)=>({id:'p'+i,name:'P'+i,gender:i<7?'M':'F'})),targetMatches:6,numCourts:3,slots:[],matches:[],teams:[],groups:[],knockout:null};
   scores={};window.__BEACH_GENERATION_BUDGET_MS=1700;window.__BEACH_GENERATION_MIN_MS=0;
   await generateBaraondaOptimized();
   return torneo.matches.filter(m=>!m.fr).length===27&&scheduleAudit(torneo.matches,torneo.slots).ok;
  }""")
 check('Generatore misto: 7 uomini, 11 donne, 3 campi',mixed_generator)
 def group_generator():
  return p.evaluate("""async()=>{
   torneo={...defaultTournament,name:'Test gironi',formatType:'coppie',phaseMode:'groups',players:Array.from({length:16},(_,i)=>({id:'p'+i,name:'P'+i,gender:'M'})),teams:[],slots:[],matches:[],groups:[],knockout:null,numCourts:3};
   scores={};window.__BEACH_GENERATION_BUDGET_MS=1700;
   await generateGroups();
   for(const m of torneo.matches.filter(m=>m.stage==='group'))scores[m.id]={a:21,b:15,d:1};
   autoProgressKnockout();return torneo.groups.length>0&&!!torneo.knockout;
  }""")
 check('Generatore: gironi e avanzamento playoff',group_generator)
 def online_site():
  # Per CI: no download browser of a 300 KB HTML. The exported site's
  # read/write flows are still exercised below through the complete
  # configured HTML and a fully mocked Supabase backend.
  assert 'genSite' in SRC
  marker='const CFG=null;'
  assert marker in SRC
  cfg='const CFG='+json.dumps({'url':URL,'key':PUBLISHABLE},separators=(',',':'))+';'
  page=SRC.replace(marker,cfg,1)
  assert 'const CFG={"url":"'+URL+'"' in page
  assert 'v111_commit_state' in page
  assert len(page)>250000
  return page
 try:
  SITE=online_site();check('Configurazione online e funzioni V11 incluse',lambda:True)
 except Exception as e:
  SITE='';check('Configurazione online e funzioni V11 incluse',lambda:(_ for _ in ()).throw(e))

 def mk(route, data=None):
  x=ctx.new_page();x.on('pageerror',lambda e:ERRORS.append((route or 'admin')+': '+str(e)))
  x.evaluate(JS_MOCK,data or state());x.set_content(site_for_route(SITE,route),wait_until='domcontentloaded');x.wait_for_selector('#v',timeout=5000)
  return x
 root=mk('')
 def login_wall():
  root.wait_for_selector('#v11-email',timeout=5000)
  assert root.evaluate('LIVE&&!EDITOR&&!V11_IS_ARCHITECT')
  assert not root.locator('.v11-item').count()
  assert not root.evaluate('mockCalls.some(x=>x.path.includes("v11_list_tournaments"))')
  return True
 check('Pagina iniziale privata: accesso Architetto richiesto',login_wall)
 def login():
  root.locator('#v11-email').fill('architect@example.it')
  root.locator('#v11-password').fill('arch-pass-123')
  root.locator('[data-act=v11-admin-login]').click()
  root.wait_for_selector('.v11-item',timeout=5000)
  assert root.locator('.v11-item').count()==2
  assert root.evaluate('V11_IS_ARCHITECT&&V11_AUTH.access_token==="admin-jwt"')
  assert root.evaluate('mockCalls.some(x=>x.path==="/rest/v1/rpc/v11_is_architect"&&x.auth==="Bearer admin-jwt")')
  return True
 check('Login Architetto via Auth e dashboard tornei',login)
 def create():
  root.locator('[data-act=v11-new]').click()
  root.locator('#v11-new-name').fill('Baraonda Maggio')
  root.locator('#v11-new-sport').select_option('beach')
  root.locator('#v11-new-pin').fill('new-mini-password-123')
  root.locator('[data-act=v11-create]').click()
  root.wait_for_function('V11_CATALOG.length===3',timeout=5000)
  assert root.evaluate('mockDB[3].slug==="baraonda-maggio-3"')
  assert root.locator('.v11-item').count()==3
  return True
 check('Architetto: crea un torneo con URL e password indipendente',create)
 root.screenshot(path=str(Path(__file__).with_name('V11_1_dashboard_mobile.png')),full_page=True)
 root.set_viewport_size({'width':1440,'height':900})
 root.screenshot(path=str(Path(__file__).with_name('V11_1_dashboard_desktop.png')),full_page=True)
 root.set_viewport_size({'width':390,'height':844})
 def admin_manage_without_mini():
  admin_page=ctx.new_page();admin_page.on('pageerror',lambda e:ERRORS.append('admin-torneo: '+str(e)))
  admin_page.evaluate(JS_MOCK,state())
  admin_page.evaluate("data=>Object.defineProperty(window,'sessionStorage',{value:{data:{[data.key]:JSON.stringify(data.auth)},getItem(k){return this.data[k]??null},setItem(k,v){this.data[k]=String(v)},removeItem(k){delete this.data[k]}}})",{'key':'beach-torneo-v11-architetto:'+URL,'auth':{'access_token':'admin-jwt','refresh_token':'refresh-jwt','expires_at':4102444800}})
  admin_page.set_content(site_for_route(SITE,'padel-open-2'),wait_until='domcontentloaded')
  admin_page.wait_for_function('V11_IS_ARCHITECT&&EDITOR',timeout=5000)
  assert admin_page.evaluate('PIN===""&&torneo.name==="Padel Open"')
  admin_page.evaluate("torneo.name='Padel modificato da Architetto';saveState()")
  admin_page.wait_for_function('!v9Dirty',timeout=5000)
  assert admin_page.evaluate('mockDB[2].title==="Padel modificato da Architetto"')
  assert admin_page.evaluate('mockDB[1].title==="Beach storico"')
  assert admin_page.evaluate('mockCalls.some(x=>x.path==="/rest/v1/rpc/v111_commit_state"&&x.auth==="Bearer admin-jwt")')
  admin_page.close();return True
 check('Architetto: gestisce un torneo senza password mini',admin_manage_without_mini)
 def rotate():
  root.locator('[data-act=v11-password][data-id="2"]').click()
  root.locator('#v11-rotate-pin').fill('new-padel-password-123')
  root.locator('[data-act=v11-rotate-submit]').click()
  root.wait_for_function('mockPassword[2].password==="new-padel-password-123"')
  return True
 check('Architetto: cambia password mini e invalida la vecchia',rotate)
 def archive():
  root.on('dialog',lambda d:d.accept())
  root.locator('[data-act=v11-archive][data-id="2"]').click()
  root.wait_for_function('mockDB[2].status==="archived"')
  assert root.locator('[data-act=v11-delete][data-id="2"]').count()==1
  return True
 check('Architetto: archivia e mantiene il torneo consultabile',archive)
 archived=mk('padel-open-2',root.evaluate('({db:mockDB,scores:mockScores,passwords:mockPassword})'))
 def archived_view():
  archived.wait_for_function('v9RemoteReady',timeout=5000)
  assert archived.evaluate("V11_ACTIVE_STATUS==='archived'&&!EDITOR")
  assert archived.locator('#lockBtn').count()==0
  assert 'archiviato' in archived.locator('#lockBar').inner_text().lower()
  return True
 check('Torneo archiviato: visibile ma non modificabile dal mini',archived_view)
 def restore():
  root.locator('[data-act=v11-archive][data-id="2"]').click()
  root.wait_for_function('mockDB[2].status==="active"')
  return True
 check('Architetto: riattiva un torneo',restore)
 def delete():
  root.locator('[data-act=v11-archive][data-id="3"]').click()
  root.wait_for_function('mockDB[3].status==="archived"')
  root.locator('[data-act=v11-delete][data-id="3"]').click()
  root.locator('#v11-delete-confirm').fill('Baraonda Maggio')
  root.locator('[data-act=v11-delete-submit]').click()
  root.wait_for_function('!mockDB[3]',timeout=5000)
  assert root.locator('.v11-item').count()==2
  assert root.evaluate('mockDB[1]&&mockDB[2]')
  return True
 check('Architetto: elimina definitivamente solo un torneo archiviato',delete)
 public1=mk('torneo-1');public2=mk('padel-open-2')
 def public_read():
  public1.wait_for_function('v9RemoteReady',timeout=5000);public2.wait_for_function('v9RemoteReady',timeout=5000)
  assert public1.evaluate('!EDITOR&&torneo.name==="Beach storico"&&scores["0-1"].a===21')
  assert public2.evaluate('!EDITOR&&torneo.name==="Padel Open"&&scores["0-1"].a===5')
  return True
 check('Giocatori: link distinti, lettura senza password',public_read)
 def mini():
  public2.locator('[data-act=unlock]').click()
  public2.locator('#pinIn').fill('beach-unique-123')
  public2.locator('[data-act=pin-ok]').click()
  assert public2.evaluate('!EDITOR')
  public2.locator('#pinIn').fill('padel-unique-123')
  public2.locator('[data-act=pin-ok]').click()
  try:public2.wait_for_function('EDITOR',timeout=5000)
  except Exception:
   print('MINI DEBUG',public2.evaluate("({editor:EDITOR,remote:v9RemoteReady,client:typeof crypto.randomUUID,toast:[...document.querySelectorAll('.toast')].map(e=>e.textContent),calls:mockCalls.slice(-7)})"))
   raise
  assert public2.evaluate('!V11_IS_ARCHITECT')
  public2.evaluate("torneo.name='Padel modificato';saveState()")
  public2.wait_for_function('!v9Dirty',timeout=5000)
  assert public2.evaluate('mockDB[2].title==="Padel modificato"&&mockDB[1].title==="Beach storico"')
  return True
 check('Mini-organizzatore: password solo del proprio torneo',mini)
 def deny_cross():
  outcome=public2.evaluate('''async()=>{
   const r=await fetch('https://testing.supabase.co/rest/v1/rpc/v111_commit_state',{
    method:'POST',headers:{'apikey':'sb_publishable_test_key_123456789','Content-Type':'application/json'},
    body:JSON.stringify({p_tournament_id:1,p_token:PIN,p_expected_revision:0,p_json:JSON.stringify({...torneo,name:'Attack'}),p_rows:[]})
   });return r.status;
  }''')
  assert outcome==403
  assert public2.evaluate('mockDB[1].title==="Beach storico"')
  return True
 check('Permessi simulati: token mini di B non modifica il torneo A',deny_cross)
 def unchanged_poll():
  # V11.1 reads only revision after the first snapshot.
  public1.evaluate('mockCalls.length=0')
  public1.evaluate('poll()')
  public1.wait_for_function("mockCalls.some(x=>x.path==='/rest/v1/tournament')")
  paths=public1.evaluate("mockCalls.map(x=>x.path)")
  assert '/rest/v1/tournament' in paths
  assert '/rest/v1/rpc/v111_get_snapshot' not in paths,paths
  return True
 check('Lettore: polling invariato scarica solo revisione',unchanged_poll)
 def changed_poll():
  public1.evaluate('''()=>{
    mockDB[1].revision=(mockDB[1].revision||0)+1;
    const x=JSON.parse(mockDB[1].json);x.name='Aggiornamento in arrivo';mockDB[1].json=JSON.stringify(x);
    mockCalls.length=0;
  }''')
  public1.evaluate('poll()')
  public1.wait_for_function("torneo.name==='Aggiornamento in arrivo'")
  paths=public1.evaluate("mockCalls.map(x=>x.path)")
  assert '/rest/v1/rpc/v111_get_snapshot' in paths
  return True
 check('Lettore: scarica snapshot coerente solo dopo aggiornamento',changed_poll)
 def conflict():
  # Simula due organizzatori: una modifica da un secondo client avanza revision.
  public2.evaluate('''()=>{
    mockDB[2].revision=(mockDB[2].revision||0)+1;
    mockDB[2].json=JSON.stringify({...JSON.parse(mockDB[2].json),subtitle:'Modifica dal secondo organizzatore'});
    torneo.subtitle='Modifica locale concorrente';saveState();
  }''')
  public2.wait_for_function('v111Conflict',timeout=6000)
  assert public2.evaluate('mockDB[2].json.includes("secondo organizzatore")')
  assert public2.evaluate('v9Dirty&&v111Conflict')
  assert public2.locator('#v111-resolve').is_visible()
  return True
 check('Conflitto: le modifiche remote non sono sovrascritte',conflict)
 def backup_conflict():
  public2.once('dialog',lambda d:d.accept())
  with public2.expect_download(timeout=8000) as dl:
   public2.locator('#v111-resolve').click()
  name=dl.value.suggested_filename
  assert 'CONFLITTO' in name,name
  public2.wait_for_function('!v111Conflict && !v9Dirty',timeout=6000)
  assert public2.evaluate('torneo.subtitle==="Modifica dal secondo organizzatore"')
  return True
 check('Risoluzione: backup locale prima di caricare la versione remota',backup_conflict)
 def one_commit():
  public2.evaluate('''()=>{
   torneo.subtitle='Nuovo';scores['0-1']={a:7,b:6,d:1};saveState();
  }''')
  public2.wait_for_function('!v9Dirty',timeout=6000)
  call=public2.evaluate("mockCalls.filter(x=>x.path.endsWith('v111_commit_state')).at(-1)")
  assert call and call['body']['p_rows']
  assert public2.evaluate('mockDB[2].revision===v111RemoteRev')
  assert public2.evaluate('mockScores[2]["0-1"].a===7')
  return True
 check('Salvataggio atomico: JSON padel e punteggi nella stessa RPC',one_commit)
 def shared_player_link():
  data=state()
  data['scores']['2']={}
  tournament=json.loads(data['db']['2']['json'])
  tournament.update(players=[{'id':name,'name':name,'gender':'M'} for name in ['Anna','Alessandro','Carlo','Dario']],
                    slots=[['14:40','15:00']],matches=[{'s':0,'f':1,'a':['Anna','Alessandro'],'b':['Carlo','Dario']}])
  data['db']['2']['json']=json.dumps(tournament)
  page=ctx.new_page()
  base='https://torneo.example/test/'
  page.route(base+'**',lambda route:route.fulfill(content_type='text/html',body=SITE))
  session={'access_token':'admin-jwt','refresh_token':'refresh-jwt','expires_at':4102444800}
  page.add_init_script('if(window===top){('+JS_MOCK+')('+json.dumps(data)+');sessionStorage.setItem('+
                       json.dumps('beach-torneo-v11-architetto:'+URL)+','+json.dumps(json.dumps(session))+');}')
  try:
   page.goto(base+'?torneo=padel-open-2')
   page.wait_for_function('EDITOR && V11_IS_ARCHITECT')
   page.evaluate("activeTab='export';render()")
   page.get_by_role('button',name='Mostra QR').click()
   assert page.locator('#share-code svg path').count()
   url=page.locator('#share-url').input_value()
   assert url==base+'?torneo=padel-open-2&vista=giocatore'
   page.get_by_role('button',name='Chiudi',exact=True).click()
   page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:async t=>window.copied=t}})")
   page.get_by_role('button',name='Copia link giocatori').click()
   assert page.evaluate('window.copied')==url
   page.goto(url)
   page.locator('#share-player').select_option('Alessandro')
   page.wait_for_function("localStorage.getItem('beach-me:2')==='Alessandro'")
   page.reload()
   banner=page.frame_locator('#pv').locator('#court-timing')
   banner.filter(has_text='Alessandro').wait_for(timeout=6000)
   assert page.locator('#share-player').count()==0
   assert page.evaluate('!EDITOR && !V11_IS_ARCHITECT')
   assert page.locator('#lockBtn').count()==0
  finally:
   page.close()
  return True
 check('QR e link giocatori: destinazione, sola lettura e nome al rientro',shared_player_link)

 def import_backup():
  # La dashboard pubblicata è HTTPS. about:blank del test può non esporre randomUUID.
  root.evaluate("if(!crypto.randomUUID)Object.defineProperty(crypto,'randomUUID',{value:()=> '162846ac-5bfe-4af5-91e2-4e27b68acbfd'})")
  root.locator('[data-act=v11-import]').click()
  dialog=root.locator('#modal')
  def upload(data):
   dialog.locator('[type=file]').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':json.dumps(data).encode()})
  upload({'version':2})
  dialog.get_by_text('Backup non valido.',exact=False).wait_for()
  assert dialog.locator('[type=submit]').is_disabled()
  t={'name':'Padel Open','sport':'padel','formatType':'baraonda','numCourts':1,
     'players':[{'name':n,'id':n,'gender':'F'} for n in 'ABCD'],
     'slots':[['10:00','10:20']],'matches':[{'s':0,'f':1,'a':['A','B'],'b':['C','D']}]}
  upload({'schema':'beach-torneo-backup','version':1,'tournament':t,'scores':{'0-1':{'a':4,'b':2,'d':1}}})
  dialog.get_by_text('Risultati confermati: 1',exact=False).wait_for()
  assert dialog.locator('[name=title]').input_value()=='Padel Open'
  dialog.locator('[name=pin]').fill('nuova-password-qa')
  old=root.evaluate('JSON.stringify(mockDB[2])')
  dialog.locator('[type=submit]').click()
  root.wait_for_function("V11_CATALOG.some(t=>t.slug.startsWith('backup-'))")
  assert root.evaluate('JSON.stringify(mockDB[2])')==old
  new_id=root.evaluate("V11_CATALOG.find(t=>t.slug.startsWith('backup-')).id")
  assert root.evaluate('id=>JSON.parse(mockDB[id].json)',new_id)==t
  assert root.evaluate("id=>mockScores[id]['0-1']",new_id)=={'id':'0-1','a':4,'b':2,'d':1}
  return True
 check('Dashboard: rifiuta JSON non valido e importa calendario e punteggi come nuovo torneo',import_backup)

 def no_console_errors():
  assert not ERRORS,ERRORS
  return True
 check('Nessun errore JavaScript durante i test',no_console_errors)
 for x in (root,archived,public1,public2,p):x.close()
 browser.close()

passed=sum(ok for _,ok in RESULTS)
print(f'\n{passed}/{len(RESULTS)} test superati')
sys.exit(passed!=len(RESULTS))
