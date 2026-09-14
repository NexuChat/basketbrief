"""Individual identities, project collaboration and reviewed multicurrency expenses."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from .store import Conflict, Forbidden, Store, digest, pack

CURRENCIES = {'USD':2,'EUR':2,'GBP':2,'YER':2,'SAR':2,'AED':2,'EGP':2,'JPY':0,'KWD':3}
REVIEWERS = {'coordinator','finance'}
ROLES = REVIEWERS | {'contributor','donor'}


def clean(value, maximum=500):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum:
        raise Conflict('A non-empty value of reasonable length is required.')
    return value.strip()


def email(value):
    value=clean(value,254).lower()
    if not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',value):
        raise Conflict('Enter a valid email address.')
    return value


def monetary(value,currency):
    if currency not in CURRENCIES: raise Conflict('Choose a supported currency.')
    if not isinstance(value,(str,int,Decimal)) or isinstance(value,bool): raise Conflict('Enter a decimal amount.')
    raw=str(value)
    if not re.fullmatch(r'\d+(?:\.\d+)?',raw): raise Conflict('Use a decimal point, without thousands separators.')
    try:
        n=Decimal(raw);q=Decimal(1).scaleb(-CURRENCIES[currency])
        if n<0 or n>Decimal('1000000000000') or n!=n.quantize(q): raise InvalidOperation()
        return format(n.quantize(q),'f')
    except InvalidOperation: raise Conflict('Amount precision or size is not supported for this currency.')


def password_hash(password,salt=None):
    if not isinstance(password,str) or not 12<=len(password)<=256: raise Conflict('Use a password of 12–256 characters.')
    salt=salt or secrets.token_hex(16)
    result=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=32768,r=8,p=3,maxmem=64*1024*1024).hex()
    return salt+':'+result


class TeamStore:
    def __init__(self,store:Store):
        self.store=store
        self.db=store.db
        # Each migration file is immutable once deployed. No existing demo rows are rewritten.
        sql=(Path(__file__).parent/'migrations/001_team.sql').read_text()
        with self.db() as c:
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='team_schema'").fetchone():
                if c.execute('SELECT 1 FROM team_schema WHERE version=1').fetchone():return
            c.executescript('BEGIN IMMEDIATE;\n'+sql)
            c.execute('INSERT OR IGNORE INTO team_schema VALUES(1,?)',(time.time(),))

    def limit(self,key,count=20,window=900):
        with self.db() as c:
            c.execute('DELETE FROM team_limits WHERE created<?',(time.time()-86400,))
            n=c.execute('SELECT count(*) FROM team_limits WHERE key=? AND created>?',(key,time.time()-window)).fetchone()[0]
            if n>=count: raise Conflict('Too many attempts. Please try again later.')
            c.execute('INSERT INTO team_limits VALUES(?,?)',(key,time.time()))

    def register(self,name,address,password):
        name=clean(name,100);address=email(address);encoded=password_hash(password)
        uid=secrets.token_urlsafe(18)
        try:
            with self.db() as c:
                c.execute('INSERT INTO team_users(id,name,email,password,created) VALUES(?,?,?,?,?)',(uid,name,address,encoded,time.time()))
        except sqlite3.IntegrityError: raise Conflict('This email cannot be registered. Sign in if you already have an account.')
        return self.session(uid)

    def login(self,address,password):
        address=email(address);self.limit('login:'+address)
        with self.db() as c: user=c.execute('SELECT * FROM team_users WHERE email=?',(address,)).fetchone()
        salt=user['password'].split(':')[0] if user else '0'*32
        encoded=password_hash(password,salt)
        if not user or not hmac.compare_digest(encoded,user['password']): raise Forbidden('Email or password was not recognized.')
        return self.session(user['id'])

    def session(self,uid):
        token=secrets.token_urlsafe(40)
        with self.db() as c:
            c.execute('DELETE FROM team_sessions WHERE expires<?',(time.time(),))
            c.execute('INSERT INTO team_sessions VALUES(?,?,?)',(digest(token),uid,time.time()+86400*7))
        return token

    def user(self,token):
        with self.db() as c:
            u=c.execute('SELECT u.id,u.name,u.email,u.verified,u.email_notifications FROM team_users u JOIN team_sessions s ON s.user_id=u.id WHERE s.hash=? AND s.expires>?',(digest(token or ''),time.time())).fetchone()
            if not u: raise Forbidden('Sign in to your team account.')
            return dict(u)

    @staticmethod
    def member(c,pid,uid,roles=None):
        m=c.execute('SELECT role FROM team_members WHERE project=? AND user_id=?',(pid,uid)).fetchone()
        if not m or (roles and m['role'] not in roles): raise Forbidden('Your account cannot perform this action in this project.')
        return m['role']

    @staticmethod
    def changed(c,pid,uid,action,detail):
        c.execute('UPDATE team_projects SET revision=revision+1 WHERE id=?',(pid,))
        c.execute("UPDATE team_reports SET status='outdated' WHERE project=? AND status='draft'",(pid,))
        c.execute('INSERT INTO team_activity(project,actor,action,detail,created) VALUES(?,?,?,?,?)',(pid,uid,action,pack(detail),time.time()))
        if uid and action in {'expense_added','contributor_reply','distribution_updated','expense_reviewed','exchange_rate_reviewed'}:
            if not c.execute("SELECT 1 FROM team_jobs WHERE project=? AND status='queued'",(pid,)).fetchone():
                c.execute('INSERT INTO team_jobs(project,created) VALUES(?,?)',(pid,time.time()))

    @staticmethod
    def notify(c,pid,users,kind,title,eid=None):
        for uid in set(users):
            if not c.execute('SELECT 1 FROM team_members WHERE project=? AND user_id=?',(pid,uid)).fetchone():continue
            nid=c.execute('INSERT INTO team_notifications(project,user_id,kind,title,expense_id,created) VALUES(?,?,?,?,?,?)',(pid,uid,kind,title,eid,time.time())).lastrowid
            u=c.execute('SELECT verified,email_notifications FROM team_users WHERE id=?',(uid,)).fetchone()
            if u['verified'] and u['email_notifications']:
                c.execute('INSERT INTO team_mail_outbox(user_id,notification_id,subject,body,available) VALUES(?,?,?,?,?)',
                          (uid,nid,'BasketBrief: project update','There is a new update in your BasketBrief project. Sign in to review it. No receipt details are included in this email.',time.time()))

    @staticmethod
    def reviewers(c,pid,exclude=None):
        return [r[0] for r in c.execute("SELECT user_id FROM team_members WHERE project=? AND role IN ('coordinator','finance')",(pid,)) if r[0]!=exclude]

    def create(self,uid,name,base):
        name=clean(name,120)
        if base not in CURRENCIES: raise Conflict('Choose a supported reporting currency.')
        self.limit('project:'+uid,20,3600)
        pid=secrets.token_urlsafe(16)
        with self.db() as c:
            c.execute('INSERT INTO team_projects(id,name,base_currency,created) VALUES(?,?,?,?)',(pid,name,base,time.time()))
            c.execute('INSERT INTO team_members VALUES(?,?,?)',(pid,uid,'coordinator'))
        return {'id':pid}

    def invite(self,pid,uid,role):
        if role not in ROLES: raise Conflict('Choose a project role.')
        token=secrets.token_urlsafe(32)
        with self.db() as c:
            self.member(c,pid,uid,{'coordinator'})
            c.execute('INSERT INTO team_invites VALUES(?,?,?,?,?,NULL)',(digest(token),pid,role,uid,time.time()+86400*2))
        return {'token':token,'expires_in':172800}

    def join(self,uid,token):
        self.limit('join:'+uid)
        with self.db() as c:
            r=c.execute('SELECT * FROM team_invites WHERE hash=?',(digest(token),)).fetchone()
            if not r or r['used'] or r['expires']<time.time(): raise Conflict('This invitation is expired or already used.')
            if not c.execute("SELECT 1 FROM team_members WHERE project=? AND user_id=? AND role='coordinator'",(r['project'],r['creator'])).fetchone():raise Conflict('The inviter can no longer grant access.')
            if c.execute('SELECT 1 FROM team_members WHERE project=? AND user_id=?',(r['project'],uid)).fetchone():raise Conflict('You already belong to this project.')
            c.execute('INSERT INTO team_members VALUES(?,?,?)',(r['project'],uid,r['role']))
            c.execute('UPDATE team_invites SET used=? WHERE hash=?',(time.time(),digest(token)))
            self.notify(c,r['project'],self.reviewers(c,r['project'],uid),'member_joined','A new member joined your project.')
        return {'id':r['project']}

    def revoke(self,pid,uid,target):
        with self.db() as c:
            self.member(c,pid,uid,{'coordinator'})
            role=self.member(c,pid,target)
            if role=='coordinator' and c.execute("SELECT count(*) FROM team_members WHERE project=? AND role='coordinator'",(pid,)).fetchone()[0]<=1:raise Conflict('Keep at least one coordinator.')
            c.execute('DELETE FROM team_members WHERE project=? AND user_id=?',(pid,target))
            c.execute('DELETE FROM team_notifications WHERE project=? AND user_id=? AND id NOT IN (SELECT notification_id FROM team_mail_outbox WHERE notification_id IS NOT NULL)',(pid,target))
            c.execute("UPDATE team_mail_outbox SET status='cancelled' WHERE notification_id IN (SELECT id FROM team_notifications WHERE project=? AND user_id=?) AND status='queued'",(pid,target))
            self.changed(c,pid,uid,'member_revoked',{'user_id':target})

    def add_expense(self,pid,uid,description,amount=None,currency=None,attachment=None,reading=None,fingerprint=None,origin='manual'):
        description=clean(description,500)
        if amount is not None: amount=monetary(amount,currency)
        with self.db() as c:
            self.member(c,pid,uid,ROLES-{'donor'})
            if fingerprint:
                old=c.execute('SELECT id FROM team_expenses WHERE project=? AND fingerprint=?',(pid,fingerprint)).fetchone()
                if old:return {'id':old[0],'duplicate':True}
            if c.execute('SELECT count(*) FROM team_expenses WHERE project=?',(pid,)).fetchone()[0]>=2000:raise Conflict('Project expense limit reached.')
            now=time.time()
            eid=c.execute('INSERT INTO team_expenses(project,owner,description,amount,currency,attachment,reading,fingerprint,origin,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                          (pid,uid,description,amount,currency,attachment,pack(reading) if reading else None,fingerprint,origin,now,now)).lastrowid
            self.changed(c,pid,uid,'expense_added',{'expense_id':eid})
            self.notify(c,pid,self.reviewers(c,pid,uid),'expense_added','A new expense needs review.',eid)
        return {'id':eid,'duplicate':False}

    def expense(self,c,pid,uid,eid,review=False):
        role=self.member(c,pid,uid,REVIEWERS if review else ROLES-{'donor'})
        e=c.execute('SELECT * FROM team_expenses WHERE project=? AND id=?',(pid,eid)).fetchone()
        if not e or (role=='contributor' and e['owner']!=uid):raise Forbidden('This expense is not available to your account.')
        return e

    def attach(self,pid,uid,eid,attachment,reading,fingerprint,expected_updated):
        with self.db() as c:
            e=self.expense(c,pid,uid,eid)
            if e['status']=='rejected':raise Conflict('Submit a new expense for a rejected source.')
            if e['updated']!=expected_updated:raise Conflict('This expense changed during upload. Review it and try again.')
            old=c.execute('SELECT id FROM team_expenses WHERE project=? AND fingerprint=?',(pid,fingerprint)).fetchone()
            if old:
                if old['id']==eid:return {'id':eid,'duplicate':True}
                raise Conflict('This receipt is already attached to a different expense. Review that expense to avoid double counting.')
            c.execute("UPDATE team_expenses SET attachment=?,reading=?,fingerprint=?,status='pending',supported=0,reviewer=NULL,note='',fx_rate=NULL,fx_date=NULL,fx_source=NULL,updated=? WHERE id=?",
                      (attachment,pack(reading),fingerprint,time.time(),eid))
            self.changed(c,pid,uid,'receipt_attached',{'expense_id':eid,'replaces_attachment':bool(e['attachment'])})
            self.notify(c,pid,self.reviewers(c,pid,uid),'receipt_attached','The contributor attached the requested receipt.',eid)
            if not c.execute("SELECT 1 FROM team_jobs WHERE project=? AND status='queued'",(pid,)).fetchone():
                c.execute('INSERT INTO team_jobs(project,created) VALUES(?,?)',(pid,time.time()))
            return {'id':eid,'duplicate':False}

    def review(self,pid,uid,eid,action,amount,currency,note,confirmed,expected_updated=None):
        note=clean(note,1000)
        if action not in {'accept','needs_info','reject'}:raise Conflict('Choose a review action.')
        with self.db() as c:
            e=self.expense(c,pid,uid,eid,True)
            if expected_updated is not None and e['updated']!=expected_updated:
                raise Conflict('This expense changed while you were reviewing it. Reopen the source before saving.')
            supported=False
            if action=='accept':
                if confirmed is not True:raise Conflict('Confirm that you reviewed the original evidence.')
                amount=monetary(amount,currency)
                if e['attachment']:
                    reading=json.loads(e['reading'] or '{}')
                    if reading.get('status')=='unsupported' or reading.get('document_type') in {'bank_statement','transfer_receipt','transfer_batch','invoice','utility_bill'}:
                        raise Conflict('A statement, transfer or unpaid bill cannot be accepted as a purchase receipt. Reject it or request a purchase receipt.')
                    # Human review may correct OCR, but must state the correction explicitly.
                    matches=reading.get('ok') is True and reading.get('verification') is True and reading.get('document_type')=='receipt' and reading.get('currency')==currency and reading.get('stated_total') is not None
                    if matches:
                        try: matches=monetary(reading['stated_total'],currency)==amount
                        except Conflict:matches=False
                    if not matches and len(note)<25:raise Conflict('Explain your correction of the uncertain transcription (at least 25 characters).')
                    supported=True
            else:amount=e['amount'];currency=e['currency']
            status={'accept':'accepted','needs_info':'needs_info','reject':'rejected'}[action]
            changed_amount=e['amount']!=amount or e['currency']!=currency
            c.execute('UPDATE team_expenses SET status=?,amount=?,currency=?,supported=?,note=?,reviewer=?,updated=? WHERE id=?',
                      (status,amount,currency,int(supported),note,uid,time.time(),eid))
            if changed_amount:c.execute('UPDATE team_expenses SET fx_rate=NULL,fx_date=NULL,fx_source=NULL WHERE id=?',(eid,))
            self.changed(c,pid,uid,'expense_reviewed',{'expense_id':eid,'status':status,'amount':amount,'currency':currency,'note':note})
            self.notify(c,pid,[e['owner']]+self.reviewers(c,pid,uid),'expense_reviewed','An expense was reviewed: '+status.replace('_',' ')+'.',eid)
        return {'status':status}

    def reply(self,pid,uid,eid,text):
        text=clean(text,1000)
        with self.db() as c:
            e=self.expense(c,pid,uid,eid)
            if e['owner']!=uid:raise Forbidden('Only the expense contributor can reply here.')
            if e['status']=='rejected':raise Conflict('Submit a new source for a rejected expense.')
            c.execute("UPDATE team_expenses SET status='pending',supported=0,note=?,reviewer=NULL,updated=? WHERE id=?",(text,time.time(),eid))
            self.changed(c,pid,uid,'contributor_reply',{'expense_id':eid,'text':text})
            self.notify(c,pid,self.reviewers(c,pid,uid),'contributor_reply','The contributor answered a review question.',eid)

    def fx(self,pid,uid,eid,rate,stamp,source,confirmed):
        source=clean(source,300)
        try:
            n=Decimal(str(rate));day=date.fromisoformat(stamp)
            if not n.is_finite() or n<=0 or n>10**9 or n.as_tuple().exponent < -10 or day>date.today():raise ValueError()
        except (InvalidOperation,ValueError,TypeError):raise Conflict('Provide a positive exchange rate and a valid past or current date.')
        if confirmed is not True:raise Conflict('Finance must confirm the exchange rate and its source.')
        with self.db() as c:
            e=self.expense(c,pid,uid,eid,True)
            if e['status']!='accepted':raise Conflict('Review the expense before its exchange rate.')
            base=c.execute('SELECT base_currency FROM team_projects WHERE id=?',(pid,)).fetchone()[0]
            if e['currency']==base:raise Conflict('No exchange rate is needed for the reporting currency.')
            c.execute('UPDATE team_expenses SET fx_rate=?,fx_date=?,fx_source=? WHERE id=?',(format(n,'f'),stamp,source,eid))
            self.changed(c,pid,uid,'exchange_rate_reviewed',{'expense_id':eid,'rate':str(n),'date':stamp,'source':source})
            self.notify(c,pid,self.reviewers(c,pid,uid),'exchange_rate_reviewed','An expense exchange rate was reviewed.',eid)

    @staticmethod
    def totals(expenses,base):
        totals={};converted=Decimal(0);missing=0
        for e in expenses:
            if e['status']!='accepted':continue
            code=e['currency'];amount=Decimal(e['amount'])
            t=totals.setdefault(code,{'reported':Decimal(0),'supported':Decimal(0)})
            t['reported']+=amount
            if e['supported']:t['supported']+=amount
            if code==base:converted+=amount
            elif e['fx_rate']:
                converted+=(amount*Decimal(e['fx_rate'])).quantize(Decimal(1).scaleb(-CURRENCIES[base]),rounding=ROUND_HALF_UP)
            else:missing+=1
        for code,t in totals.items():
            t['unsupported']=t['reported']-t['supported']
            for k in t:t[k]=format(t[k],f'.{CURRENCIES[code]}f')
        return totals,None if missing else format(converted,f'.{CURRENCIES[base]}f'),missing

    def distribution(self,pid,uid,values,note):
        note=clean(note,1000)
        for v in values.values():
            if v is not None and (type(v) is not int or not 0<=v<=10**7):raise Conflict('Use non-negative whole counts, or leave unknown.')
        with self.db() as c:
            self.member(c,pid,uid,{'coordinator','contributor'})
            c.execute('INSERT INTO team_distribution VALUES(?,?,?,?,?,?,?) ON CONFLICT(project) DO UPDATE SET loaded=excluded.loaded,delivered=excluded.delivered,returned=excluded.returned,households=excluded.households,note=excluded.note,author=excluded.author',
                      (pid,values.get('loaded'),values.get('delivered'),values.get('returned'),values.get('households'),note,uid))
            self.changed(c,pid,uid,'distribution_updated',values)
            self.notify(c,pid,self.reviewers(c,pid,uid),'distribution_updated','Field distribution counts were updated.')

    def state(self,pid,uid):
        with self.db() as c:
            role=self.member(c,pid,uid)
            p=dict(c.execute('SELECT * FROM team_projects WHERE id=?',(pid,)).fetchone())
            expenses=[]
            if role!='donor':
                expenses=[dict(e) for e in c.execute('SELECT e.*,u.name AS owner_name FROM team_expenses e JOIN team_users u ON e.owner=u.id WHERE e.project=? ORDER BY e.id DESC',(pid,)) if role in REVIEWERS or e['owner']==uid]
            for e in expenses:
                e['reading']=json.loads(e['reading']) if e['reading'] else None
                e['has_attachment']=bool(e.pop('attachment'))
                e.pop('fingerprint',None)
            totals,base_total,missing=self.totals(expenses,p['base_currency'])
            reports=[dict(r) for r in c.execute("SELECT * FROM team_reports WHERE project=? AND (status='approved' OR ?='coordinator') ORDER BY id DESC",(pid,role)) if role!='donor' or c.execute('SELECT 1 FROM team_deliveries WHERE report_id=? AND user_id=?',(r['id'],uid)).fetchone()]
            for r in reports:r['payload']=json.loads(r['payload'])
            members=[dict(m) for m in c.execute('SELECT u.id,u.name,u.email,u.verified,m.role FROM team_members m JOIN team_users u ON u.id=m.user_id WHERE m.project=?',(pid,))] if role=='coordinator' else []
            activity=[{**dict(a),'detail':json.loads(a['detail'])} for a in c.execute("SELECT a.*,COALESCE(u.name,'BasketBrief agent') AS name FROM team_activity a LEFT JOIN team_users u ON a.actor=u.id WHERE a.project=? ORDER BY a.id DESC LIMIT 40",(pid,))] if role in REVIEWERS else []
            d=c.execute('SELECT * FROM team_distribution WHERE project=?',(pid,)).fetchone() if role!='donor' else None
            jobs=[dict(j) for j in c.execute('SELECT id,status,error FROM team_jobs WHERE project=? ORDER BY id DESC LIMIT 3',(pid,))] if role in REVIEWERS else []
            return {'project':p,'role':role,'expenses':expenses,'totals':totals,'base_total':base_total if role!='donor' else None,'missing_rates':missing,'members':members,'reports':reports,'activity':activity,'distribution':dict(d) if d else None,'jobs':jobs}

    def prepare(self,pid,uid):
        with self.db() as c:
            self.member(c,pid,uid,{'coordinator'})
            p=c.execute('SELECT * FROM team_projects WHERE id=?',(pid,)).fetchone()
            expenses=[dict(e) for e in c.execute('SELECT * FROM team_expenses WHERE project=? ORDER BY id',(pid,))]
            if not any(e['status']=='accepted' for e in expenses):raise Conflict('Review at least one expense first.')
            if any(e['status'] in {'pending','needs_info'} for e in expenses):raise Conflict('Resolve pending expense reviews before preparing a report.')
            totals,base,missing=self.totals(expenses,p['base_currency'])
            dist=c.execute('SELECT loaded,delivered,returned,households FROM team_distribution WHERE project=?',(pid,)).fetchone()
            distribution=dict(dist) if dist else dict.fromkeys(['loaded','delivered','returned','households'])
            gap=None
            if all(distribution[k] is not None for k in ('loaded','delivered','returned')):
                gap=distribution['loaded']-distribution['delivered']-distribution['returned']
            payload={'name':p['name'],'base_currency':p['base_currency'],'totals':totals,'base_total':base,'missing_rates':missing,
                     'distribution':distribution,'unreconciled_kits':gap,'expense_count':sum(e['status']=='accepted' for e in expenses),
                     'disclosure':'Contributor-reported counts. Receipts and human review do not independently prove payment or delivery. Currency totals remain separate unless reviewed exchange rates are provided.',
                     'expenses':[{k:e[k] for k in ('id','description','amount','currency','supported','fx_rate','fx_date','fx_source')} for e in expenses if e['status']=='accepted']}
            previous=c.execute("SELECT version,payload FROM team_reports WHERE project=? AND status='approved' ORDER BY id DESC LIMIT 1",(pid,)).fetchone()
            payload['amends']=previous['version'] if previous else None
            before=json.loads(previous['payload']) if previous else {}
            payload['changes']={k:{'before':before.get(k),'after':payload[k]} for k in ('totals','base_total','distribution','expenses') if previous and before.get(k)!=payload[k]}
            existing=c.execute("SELECT * FROM team_reports WHERE project=? AND revision=? AND status IN ('draft','approved') ORDER BY id DESC LIMIT 1",(pid,p['revision'])).fetchone()
            if existing:return {'id':existing['id'],'hash':existing['hash'],'version':existing['version']}
            version=c.execute('SELECT COALESCE(MAX(version),0)+1 FROM team_reports WHERE project=?',(pid,)).fetchone()[0]
            hashed=digest(pack(payload))
            rid=c.execute('INSERT INTO team_reports(project,version,revision,hash,payload,created) VALUES(?,?,?,?,?,?)',(pid,version,p['revision'],hashed,pack(payload),time.time())).lastrowid
            return {'id':rid,'hash':hashed,'version':version}

    def approve(self,pid,uid,rid,hashed,acknowledge):
        with self.db() as c:
            self.member(c,pid,uid,{'coordinator'})
            r=c.execute('SELECT * FROM team_reports WHERE project=? AND id=?',(pid,rid)).fetchone()
            revision=c.execute('SELECT revision FROM team_projects WHERE id=?',(pid,)).fetchone()[0]
            if not r or r['hash']!=hashed or r['revision']!=revision or r['status']=='outdated':raise Conflict('The report changed. Review a fresh draft before approving.')
            payload=json.loads(r['payload'])
            unresolved=payload['missing_rates'] or payload['unreconciled_kits'] or any(Decimal(t['unsupported'])>0 for t in payload['totals'].values())
            if unresolved and acknowledge is not True:raise Conflict('Acknowledge the missing receipts, conversion rates or unreconciled counts.')
            if r['status']=='approved':return {'approved':True}
            c.execute("UPDATE team_reports SET status='approved',approved_by=? WHERE id=?",(uid,rid))
            donors=[m[0] for m in c.execute("SELECT user_id FROM team_members WHERE project=? AND role='donor'",(pid,))]
            for donor in donors:c.execute('INSERT OR IGNORE INTO team_deliveries VALUES(?,?,?)',(rid,donor,time.time()))
            self.notify(c,pid,donors,'report_published',f'Approved report v{r["version"]} is ready.')
            c.execute('INSERT INTO team_activity(project,actor,action,detail,created) VALUES(?,?,?,?,?)',(pid,uid,'report_approved',pack({'report_id':rid,'hash':hashed}),time.time()))
            return {'approved':True,'donor_deliveries':len(donors)}
