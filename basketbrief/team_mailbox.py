"""Per-user mailbox connections. Read-only providers; imports require an explicit selection."""
import base64
import hashlib
import imaplib
import json
import os
import re
import secrets
import ssl
import threading
import time
from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import urlencode,quote

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from .store import Conflict,digest,pack
from .team import email

MIME={'image/png','image/jpeg','application/pdf'}
PROVIDERS={
 'gmail':{'authorize':'https://accounts.google.com/o/oauth2/v2/auth','token':'https://oauth2.googleapis.com/token','scope':'https://www.googleapis.com/auth/gmail.readonly'},
 'outlook':{'authorize':'https://login.microsoftonline.com/common/oauth2/v2.0/authorize','token':'https://login.microsoftonline.com/common/oauth2/v2.0/token','scope':'offline_access https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/User.Read'},
}
_key_lock=threading.Lock()


def configuration(provider):
    if provider not in PROVIDERS:raise Conflict('Choose Gmail or Outlook.')
    prefix='BASKETBRIEF_'+provider.upper()
    return {**PROVIDERS[provider],'client_id':os.getenv(prefix+'_CLIENT_ID',''),'client_secret':os.getenv(prefix+'_CLIENT_SECRET',''),
            'redirect_uri':os.getenv('BASKETBRIEF_PUBLIC_URL','').rstrip('/')+'/api/team/mail/'+provider+'/callback'}


def ready(provider):
    c=configuration(provider)
    return bool(c['client_id'] and c['client_secret'] and c['redirect_uri'].startswith('https://'))


def cipher(team):
    if os.getenv('BASKETBRIEF_TOKEN_KEY'):return Fernet(os.environ['BASKETBRIEF_TOKEN_KEY'].encode())
    keyfile=Path(team.store.path).parent/'.team-token-key'
    with _key_lock:
        if not keyfile.exists():
            fd=os.open(keyfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(Fernet.generate_key())
        return Fernet(keyfile.read_bytes())


def statuses(team,uid):
    with team.db() as c:connections={r['provider']:r['address'] for r in c.execute('SELECT provider,address FROM team_mailboxes WHERE user_id=?',(uid,))}
    return {p:{'configured':ready(p),'connected':p in connections,'address':connections.get(p),'app_password_available':p=='gmail'} for p in PROVIDERS}


def save(team,uid,provider,address,credentials):
    encrypted=cipher(team).encrypt(pack(credentials).encode()).decode()
    with team.db() as c:
        c.execute('INSERT INTO team_mailboxes VALUES(?,?,?,?,?) ON CONFLICT(user_id,provider) DO UPDATE SET address=excluded.address,credential=excluded.credential,connected=excluded.connected',
                  (uid,provider,address,encrypted,time.time()))
        # Only mark the account's contact address verified when the provider proved that same address.
        c.execute('UPDATE team_users SET verified=1 WHERE id=? AND email=?',(uid,address.lower()))


def load(team,uid,provider):
    configuration(provider)
    with team.db() as c:r=c.execute('SELECT * FROM team_mailboxes WHERE user_id=? AND provider=?',(uid,provider)).fetchone()
    if not r:raise Conflict('Connect your own mailbox first.')
    try:credentials=json.loads(cipher(team).decrypt(r['credential'].encode()))
    except (InvalidToken,ValueError):raise Conflict('Reconnect your mailbox; the stored credential could not be opened.')
    return r['address'],credentials


@contextmanager
def imap_connection(address,password):
    m=None
    try:
        m=imaplib.IMAP4_SSL('imap.gmail.com',993,ssl_context=ssl.create_default_context(),timeout=25)
        m.login(address,password);result,_=m.select('INBOX',readonly=True)
        if result!='OK':raise Conflict('The inbox could not be opened read-only.')
        yield m
    except (imaplib.IMAP4.error,OSError,TimeoutError):raise Conflict('Gmail could not connect. Check the app password and your account settings.')
    finally:
        if m:
            try:m.logout()
            except Exception:pass


def connect_password(team,uid,address,password):
    address=email(address)
    if not isinstance(password,str) or not 12<=len(password.replace(' ',''))<=128:raise Conflict('Use a Google app password, not your main account password.')
    password=password.replace(' ','')
    with imap_connection(address,password):pass
    save(team,uid,'gmail',address,{'method':'app_password','password':password})
    return {'connected':True,'address':address,'method':'app_password'}


def oauth_start(team,uid,provider):
    if not ready(provider):raise Conflict('The administrator has not configured this mailbox connection yet.')
    cfg=configuration(provider);state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
    with team.db() as c:
        c.execute('DELETE FROM team_oauth_states WHERE expires<? OR (user_id=? AND provider=?)',(time.time(),uid,provider))
        c.execute('INSERT INTO team_oauth_states VALUES(?,?,?,?,?)',(digest(state),uid,provider,verifier,time.time()+600))
    args={'client_id':cfg['client_id'],'redirect_uri':cfg['redirect_uri'],'response_type':'code','scope':cfg['scope'],'state':state,
          'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),'code_challenge_method':'S256'}
    if provider=='gmail':args.update(access_type='offline',prompt='consent')
    else:args['prompt']='select_account'
    return cfg['authorize']+'?'+urlencode(args)


def provider_json(method,url,**kwargs):
    try:
        response=httpx.request(method,url,timeout=25,follow_redirects=False,**kwargs)
        response.raise_for_status();return response.json()
    except (httpx.HTTPError,ValueError):raise Conflict('The mailbox provider could not complete this request. Reconnect or try again.')


def oauth_finish(team,uid,provider,state,code):
    cfg=configuration(provider)
    with team.db() as c:
        row=c.execute('SELECT * FROM team_oauth_states WHERE hash=? AND user_id=? AND provider=? AND expires>?',(digest(state),uid,provider,time.time())).fetchone()
        if not row:raise Conflict('Mailbox connection expired or did not belong to this signed-in account.')
        c.execute('DELETE FROM team_oauth_states WHERE hash=?',(digest(state),))
    token=provider_json('POST',cfg['token'],data={'client_id':cfg['client_id'],'client_secret':cfg['client_secret'],'redirect_uri':cfg['redirect_uri'],
                        'grant_type':'authorization_code','code':code,'code_verifier':row['verifier']})
    if not token.get('access_token') or not token.get('refresh_token'):raise Conflict('Offline mailbox access was not granted. Reconnect and consent to the requested read-only access.')
    headers={'Authorization':'Bearer '+token['access_token']}
    profile=provider_json('GET','https://gmail.googleapis.com/gmail/v1/users/me/profile' if provider=='gmail' else 'https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName',headers=headers)
    address=profile.get('emailAddress') if provider=='gmail' else profile.get('mail') or profile.get('userPrincipalName')
    address=email(address)
    save(team,uid,provider,address,{'method':'oauth','access_token':token['access_token'],'refresh_token':token['refresh_token'],'expires':time.time()+int(token.get('expires_in',3600))-60})


def access(team,uid,provider):
    address,c=load(team,uid,provider)
    if c.get('method')=='app_password':return address,c
    if c.get('expires',0)<time.time():
        cfg=configuration(provider)
        token=provider_json('POST',cfg['token'],data={'client_id':cfg['client_id'],'client_secret':cfg['client_secret'],'grant_type':'refresh_token','refresh_token':c['refresh_token']})
        if not token.get('access_token'):raise Conflict('Mailbox access expired. Reconnect your account.')
        c.update(access_token=token['access_token'],refresh_token=token.get('refresh_token',c['refresh_token']),expires=time.time()+int(token.get('expires_in',3600))-60)
        # A disconnect while refreshing must not resurrect the connection.
        with team.db() as db:
            if not db.execute('SELECT 1 FROM team_mailboxes WHERE user_id=? AND provider=?',(uid,provider)).fetchone():raise Conflict('Mailbox disconnected.')
            db.execute('UPDATE team_mailboxes SET credential=? WHERE user_id=? AND provider=?',(cipher(team).encrypt(pack(c).encode()).decode(),uid,provider))
    return address,c


def message_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_+=.-]{1,400}',value):raise Conflict('Invalid mailbox message identifier.')
    return quote(value,safe='')


def imap_message(m,mid):
    if not re.fullmatch(r'\d{1,20}',mid):raise Conflict('Invalid Gmail message identifier.')
    status,data=m.uid('fetch',mid,'(RFC822.SIZE)')
    raw=b' '.join(x for x in data if isinstance(x,bytes));size=re.search(rb'RFC822.SIZE (\d+)',raw)
    if status!='OK' or not size or int(size[1])>12_000_000:raise Conflict('The selected email is missing or exceeds 12 MB.')
    status,data=m.uid('fetch',mid,'(BODY.PEEK[])')
    if status!='OK':raise Conflict('The selected email could not be read.')
    raw=next((x[1] for x in data if isinstance(x,tuple)),b'')
    return BytesParser(policy=policy.default).parsebytes(raw)


def gmail_parts(payload):
    result=[]
    def visit(part):
        body=part.get('body',{})
        if part.get('mimeType') in MIME and part.get('filename') and body.get('attachmentId'):
            result.append({'id':body['attachmentId'],'name':part['filename'],'type':part['mimeType'],'size':body.get('size',0)})
        for child in part.get('parts',[]):visit(child)
    visit(payload);return result


def messages(team,uid,provider):
    address,c=access(team,uid,provider)
    if c['method']=='app_password':
        result=[]
        with imap_connection(address,c['password']) as m:
            status,data=m.uid('search',None,'X-GM-RAW','"has:attachment newer_than:90d"')
            if status!='OK':raise Conflict('Gmail attachment search failed.')
            for mid in reversed(data[0].split()[-20:]):
                status,parts=m.uid('fetch',mid,'(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])')
                raw=next((p[1] for p in parts if isinstance(p,tuple)),b'')
                msg=BytesParser(policy=policy.default).parsebytes(raw)
                result.append({'id':mid.decode(),'subject':str(msg.get('Subject','')),'from':str(msg.get('From',''))})
        return result
    headers={'Authorization':'Bearer '+c['access_token']}
    if provider=='gmail':
        result=[]
        rows=provider_json('GET','https://gmail.googleapis.com/gmail/v1/users/me/messages',headers=headers,params={'q':'has:attachment newer_than:90d','maxResults':20}).get('messages',[])
        for row in rows:
            msg=provider_json('GET','https://gmail.googleapis.com/gmail/v1/users/me/messages/'+message_id(row['id']),headers=headers,params={'format':'metadata','metadataHeaders':['Subject','From']})
            h={h['name'].lower():h['value'] for h in msg.get('payload',{}).get('headers',[])}
            result.append({'id':row['id'],'subject':h.get('subject',''),'from':h.get('from','')})
        return result
    rows=provider_json('GET','https://graph.microsoft.com/v1.0/me/messages',headers=headers,params={'$filter':'hasAttachments eq true','$top':20,'$select':'id,subject,from'}).get('value',[])
    return [{'id':r['id'],'subject':r.get('subject',''),'from':r.get('from',{}).get('emailAddress',{}).get('address','')} for r in rows]


def attachments(team,uid,provider,mid,selected=None):
    mid_encoded=message_id(mid);address,c=access(team,uid,provider)
    if c['method']=='app_password':
        with imap_connection(address,c['password']) as m:msg=imap_message(m,mid)
        parts=[p for p in msg.walk() if p.get_content_type() in MIME and p.get_filename()]
        rows=[{'id':str(i),'name':p.get_filename(),'type':p.get_content_type(),'size':len(p.get_payload(decode=True) or b'')} for i,p in enumerate(parts)]
        if selected is None:return rows
        for i,p in enumerate(parts):
            if str(i)==selected:return p.get_payload(decode=True),p.get_filename()
    else:
        headers={'Authorization':'Bearer '+c['access_token']}
        if provider=='gmail':
            msg=provider_json('GET','https://gmail.googleapis.com/gmail/v1/users/me/messages/'+mid_encoded,headers=headers,params={'format':'full'})
            rows=gmail_parts(msg.get('payload',{}))
        else:
            raw=provider_json('GET','https://graph.microsoft.com/v1.0/me/messages/'+mid_encoded+'/attachments',headers=headers,params={'$select':'id,name,contentType,size,isInline'}).get('value',[])
            rows=[{'id':r['id'],'name':r['name'],'type':r['contentType'],'size':r['size']} for r in raw if r.get('contentType') in MIME and not r.get('isInline')]
        if selected is None:return rows
        row=next((r for r in rows if r['id']==selected),None)
        if not row or row['size']>5_000_000:raise Conflict('Choose an attached PNG, JPEG or PDF under 5 MB.')
        aid=message_id(selected)
        if provider=='gmail':
            raw=provider_json('GET','https://gmail.googleapis.com/gmail/v1/users/me/messages/'+mid_encoded+'/attachments/'+aid,headers=headers)
            encoded=raw.get('data','');blob=base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4))
        else:
            raw=provider_json('GET','https://graph.microsoft.com/v1.0/me/messages/'+mid_encoded+'/attachments/'+aid,headers=headers)
            blob=base64.b64decode(raw.get('contentBytes',''),validate=True)
        return blob,row['name']
    raise Conflict('This attachment does not belong to the selected message.')


class AppPassword(BaseModel):
    email:str=Field(max_length=254)
    password:str=Field(min_length=12,max_length=128)

class Import(BaseModel):
    project:str=Field(max_length=100)
    message_id:str=Field(max_length=400)
    attachment_id:str=Field(max_length=400)
    expense_id:int|None=None


def mount(router,team,user,save_image):
    @router.post('/mail/gmail/app-password')
    def password(body:AppPassword,request:Request):
        uid=user(request)['id'];team.limit('mail-connect:'+uid,5,3600)
        return connect_password(team,uid,body.email,body.password)

    @router.get('/mail/{provider}/connect')
    def connect(provider:str,request:Request):
        uid=user(request)['id'];team.limit('mail-connect:'+uid,5,3600)
        return RedirectResponse(oauth_start(team,uid,provider),status_code=303)

    @router.get('/mail/{provider}/callback')
    def callback(provider:str,request:Request,state:str='',code:str='',error:str=''):
        uid=user(request)['id']
        if error or not code:raise Conflict('Mailbox permission was not granted.')
        oauth_finish(team,uid,provider,state,code)
        return RedirectResponse('/team',status_code=303)

    @router.delete('/mail/{provider}')
    def disconnect(provider:str,request:Request):
        uid=user(request)['id'];configuration(provider)
        with team.db() as c:
            c.execute('DELETE FROM team_mailboxes WHERE user_id=? AND provider=?',(uid,provider))
            c.execute('DELETE FROM team_oauth_states WHERE user_id=? AND provider=?',(uid,provider))
        return {'disconnected':True,'provider_access_revoked':False,'note':'Stored credentials deleted. You may also revoke consent in your Google or Microsoft account settings.'}

    @router.get('/mail/{provider}/messages')
    def list_messages(provider:str,request:Request):
        uid=user(request)['id'];team.limit('mail-list:'+uid,30,3600)
        return {'messages':messages(team,uid,provider)}

    @router.get('/mail/{provider}/messages/{mid}/attachments')
    def list_attachments(provider:str,mid:str,request:Request):
        uid=user(request)['id'];team.limit('mail-list:'+uid,30,3600)
        return {'attachments':attachments(team,uid,provider,mid)}

    @router.post('/mail/{provider}/import')
    def import_receipt(provider:str,body:Import,request:Request):
        uid=user(request)['id']
        with team.db() as c:
            team.member(c,body.project,uid,{'coordinator','finance','contributor'})
            if body.expense_id is not None:team.expense(c,body.project,uid,body.expense_id)
        team.limit('mail-import:'+uid,20,3600)
        raw,name=attachments(team,uid,provider,body.message_id,body.attachment_id)
        if len(raw)>5_000_000:raise Conflict('Use a receipt attachment under 5 MB.')
        return save_image(body.project,uid,raw,name[:500],'mailbox_'+provider,expense_id=body.expense_id)
