"""HTTP boundaries for signed-in team members. Demo capabilities never grant access."""
from __future__ import annotations

import io
import json
import os
import secrets
import time
import threading
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, File, Request, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from . import vision
from .documents import failure
from .store import Conflict, Forbidden, digest
from .team import TeamStore, CURRENCIES, REVIEWERS, clean, monetary

_pdf_lock=threading.Lock()


class Register(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    email:str=Field(max_length=254)
    password:str=Field(min_length=12,max_length=256)

class Login(BaseModel):
    email:str=Field(max_length=254)
    password:str=Field(max_length=256)

class NewProject(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    base_currency:str='USD'

class Invitation(BaseModel):
    role:str

class Token(BaseModel):
    token:str=Field(max_length=200)

class Expense(BaseModel):
    description:str=Field(min_length=1,max_length=500)
    amount:str
    currency:str

class Review(BaseModel):
    action:str
    amount:str|None=None
    currency:str|None=None
    note:str=Field(min_length=1,max_length=1000)
    confirmed:bool=False
    expected_updated:float|None=None

class Reply(BaseModel):
    text:str=Field(min_length=1,max_length=1000)

class Fx(BaseModel):
    rate:str
    date:str
    source:str=Field(min_length=1,max_length=300)
    confirmed:bool=False

class Approve(BaseModel):
    hash:str=Field(max_length=64)
    acknowledge:bool=False

class Distribution(BaseModel):
    loaded:int|None=Field(default=None,ge=0,le=10000000,strict=True)
    delivered:int|None=Field(default=None,ge=0,le=10000000,strict=True)
    returned:int|None=Field(default=None,ge=0,le=10000000,strict=True)
    households:int|None=Field(default=None,ge=0,le=10000000,strict=True)
    note:str=Field(min_length=1,max_length=1000)


def image_bytes(raw):
    if not raw or len(raw)>2_000_000:raise Conflict('Choose a PNG or JPEG under 2 MB.')
    try:
        img=Image.open(io.BytesIO(raw))
        if img.format not in {'PNG','JPEG'} or img.width*img.height>12_000_000:raise ValueError()
        img.verify();img=Image.open(io.BytesIO(raw)).convert('RGB');img.thumbnail((1600,1600))
        out=io.BytesIO();img.save(out,format='PNG');return out.getvalue()
    except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError):raise Conflict('Choose a valid PNG or JPEG image.')


def preview_bytes(raw):
    if raw.startswith(b'%PDF-'):
        if len(raw)>5_000_000:raise Conflict('Use a PDF under 5 MB.')
        import pypdfium2
        try:
            with _pdf_lock, pypdfium2.PdfDocument(raw) as doc:
                if not 1<=len(doc)<=20:raise ValueError()
                page=doc[0];longest=max(page.get_size())
                if longest<=0:raise ValueError()
                bitmap=page.render(scale=1600/longest);out=io.BytesIO()
                bitmap.to_pil().convert('RGB').save(out,format='PNG')
                bitmap.close();page.close()
                return out.getvalue(),len(doc)
        except Exception:raise Conflict('Use an unlocked PDF with 1–20 readable pages.')
    return image_bytes(raw),1


def mount_team(app,store):
    team=TeamStore(store);app.state.team=team
    router=APIRouter(prefix='/api/team')
    uploads=Path(store.path).parent/'team-uploads'
    from . import team_mail

    @app.middleware('http')
    async def team_origin(request,call_next):
        if request.url.path.startswith('/api/team') and request.method not in {'GET','HEAD','OPTIONS'}:
            origin=request.headers.get('origin')
            allowed={str(request.base_url).rstrip('/')}
            if os.getenv('BASKETBRIEF_PUBLIC_URL'):allowed.add(os.environ['BASKETBRIEF_PUBLIC_URL'].rstrip('/'))
            if (origin and origin not in allowed) or request.headers.get('sec-fetch-site')=='cross-site':
                return JSONResponse({'error':'Cross-site requests are not allowed.'},status_code=403)
        return await call_next(request)

    def user(request):return team.user(request.cookies.get('basketbrief_session'))

    def signed_response(token,request,status=200):
        response=JSONResponse({'signed_in':True},status_code=status)
        response.set_cookie('basketbrief_session',token,max_age=604800,httponly=True,secure=request.url.scheme=='https',samesite='lax',path='/')
        return response

    @app.get('/team',response_class=FileResponse)
    def page():return FileResponse(Path(__file__).parent/'static/team.html',headers={'Cache-Control':'no-store'})

    @router.post('/register',status_code=201)
    def register(body:Register,request:Request):
        team.limit('signup:'+(request.client.host if request.client else 'unknown'),15,3600)
        return signed_response(team.register(body.name,body.email,body.password),request,201)

    @router.post('/login')
    def login(body:Login,request:Request):
        team.limit('signin:'+(request.client.host if request.client else 'unknown'),60,900)
        return signed_response(team.login(body.email,body.password),request)

    @router.post('/logout')
    def logout(request:Request):
        with team.db() as c:c.execute('DELETE FROM team_sessions WHERE hash=?',(digest(request.cookies.get('basketbrief_session','')),))
        response=JSONResponse({'signed_out':True});response.delete_cookie('basketbrief_session');return response

    @router.get('/me')
    def me(request:Request):
        u=user(request)
        with team.db() as c:projects=[dict(p) for p in c.execute('SELECT p.*,m.role FROM team_projects p JOIN team_members m ON p.id=m.project WHERE m.user_id=? ORDER BY p.created DESC',(u['id'],))]
        return {'user':u,'projects':projects,'currencies':CURRENCIES,'mail':team_mail.status(team,u['id'])}

    @router.post('/projects',status_code=201)
    def create(body:NewProject,request:Request):return team.create(user(request)['id'],body.name,body.base_currency)

    @router.get('/projects/{pid}')
    def state(pid:str,request:Request):return team.state(pid,user(request)['id'])

    @router.post('/projects/{pid}/invitations')
    def invite(pid:str,body:Invitation,request:Request):return team.invite(pid,user(request)['id'],body.role)

    @router.post('/join')
    def join(body:Token,request:Request):return team.join(user(request)['id'],body.token)

    @router.delete('/projects/{pid}/members/{uid}')
    def revoke(pid:str,uid:str,request:Request):
        team.revoke(pid,user(request)['id'],uid);return {'removed':True}

    @router.post('/projects/{pid}/expenses',status_code=201)
    def add(pid:str,body:Expense,request:Request):return team.add_expense(pid,user(request)['id'],body.description,body.amount,body.currency)

    def save_image(pid,uid,raw,name,origin='upload',expense_id=None):
        with team.db() as c:
            team.member(c,pid,uid,{'coordinator','finance','contributor'})
            expected=team.expense(c,pid,uid,expense_id)['updated'] if expense_id is not None else None
        team.limit('upload:'+uid,30,3600)
        preview,pages=preview_bytes(raw);is_pdf=raw.startswith(b'%PDF-');original=raw if is_pdf else preview
        fingerprint=digest(original.hex())
        with team.db() as c:
            old=c.execute('SELECT id FROM team_expenses WHERE project=? AND fingerprint=?',(pid,fingerprint)).fetchone()
            if old:
                if expense_id is not None and old[0]!=expense_id:raise Conflict('This receipt is already attached to a different expense.')
                return {'id':old[0],'duplicate':True}
        try:reading=vision.read_receipt(preview)
        except Exception:reading=failure('The image reader is unavailable. A reviewer must inspect the original.')
        reading['original_format']='pdf' if is_pdf else 'image';reading['pages']=pages
        if pages>1:
            reading.update(ok=False,eligible_for_expense=False,status='needs_review',verification=False)
            reading.setdefault('warnings',[]).append('Only the first page was machine-read. A reviewer must inspect every page of the original PDF.')
        # Store JSON-safe typed proposals, never credentials or email bodies.
        reading=json.loads(json.dumps(reading,default=str))
        uploads.mkdir(parents=True,exist_ok=True,mode=0o700)
        filename=secrets.token_hex(24)+('.pdf' if is_pdf else '.png');path=uploads/filename
        path.write_bytes(original);path.chmod(0o600)
        amount=None;currency=reading.get('currency')
        if reading.get('stated_total') is not None and currency in CURRENCIES:
            try:amount=monetary(reading['stated_total'],currency)
            except Conflict:pass
        try:
            result=team.attach(pid,uid,expense_id,filename,reading,fingerprint,expected) if expense_id is not None else team.add_expense(pid,uid,clean(name,500),amount,currency,filename,reading,fingerprint,origin)
            if result.get('duplicate'):path.unlink(missing_ok=True)
            return result
        except Exception:
            path.unlink(missing_ok=True);raise

    app.state.team_save_image=save_image

    @router.post('/projects/{pid}/upload',status_code=201)
    def upload(pid:str,request:Request,file:UploadFile=File(...)):
        uid=user(request)['id']
        return save_image(pid,uid,file.file.read(5_000_001),file.filename or 'Receipt document')

    @router.post('/projects/{pid}/expenses/{eid}/upload')
    def attach(pid:str,eid:int,request:Request,file:UploadFile=File(...)):
        return save_image(pid,user(request)['id'],file.file.read(5_000_001),file.filename or 'Requested receipt',expense_id=eid)

    @router.post('/projects/{pid}/import-eml')
    def import_eml(pid:str,request:Request,file:UploadFile=File(...)):
        uid=user(request)['id']
        with team.db() as c:team.member(c,pid,uid,{'coordinator','finance','contributor'})
        raw=file.file.read(12_000_001)
        if len(raw)>12_000_000:raise Conflict('Use an email file under 12 MB.')
        message=BytesParser(policy=policy.default).parsebytes(raw)
        imported=[];skipped=0
        for part in message.walk():
            if part.get_content_type() in {'image/png','image/jpeg','application/pdf'} and len(imported)<10:
                content=part.get_payload(decode=True) or b''
                if len(content)>5_000_000:skipped+=1;continue
                try:imported.append(save_image(pid,uid,content,(part.get_filename() or 'Email receipt')[:500],'email_file'))
                except Conflict:skipped+=1
            elif part.get_filename():skipped+=1
        if not imported:raise Conflict('No supported PNG, JPEG or PDF receipt attachments were found.')
        return {'imported':imported,'skipped':skipped,'mailbox_access':False}

    @router.get('/projects/{pid}/expenses/{eid}/image')
    def original(pid:str,eid:int,request:Request):
        uid=user(request)['id']
        with team.db() as c:e=team.expense(c,pid,uid,eid)
        if not e['attachment']:raise HTTPException(404,'No attached image.')
        return FileResponse(uploads/Path(e['attachment']).name,media_type='application/pdf' if e['attachment'].endswith('.pdf') else 'image/png',headers={'Cache-Control':'no-store'})

    @router.get('/projects/{pid}/expenses/{eid}/preview')
    def preview(pid:str,eid:int,request:Request):
        from fastapi.responses import Response
        uid=user(request)['id']
        with team.db() as c:e=team.expense(c,pid,uid,eid)
        if not e['attachment']:raise HTTPException(404,'No attached document.')
        raw=(uploads/Path(e['attachment']).name).read_bytes()
        return Response(preview_bytes(raw)[0],media_type='image/png',headers={'Cache-Control':'no-store'})

    @router.post('/projects/{pid}/expenses/{eid}/review')
    def review(pid:str,eid:int,body:Review,request:Request):return team.review(pid,user(request)['id'],eid,body.action,body.amount,body.currency,body.note,body.confirmed,body.expected_updated)

    @router.post('/projects/{pid}/expenses/{eid}/reply')
    def reply(pid:str,eid:int,body:Reply,request:Request):
        team.reply(pid,user(request)['id'],eid,body.text);return {'submitted':True}

    @router.put('/projects/{pid}/expenses/{eid}/fx')
    def fx(pid:str,eid:int,body:Fx,request:Request):
        team.fx(pid,user(request)['id'],eid,body.rate,body.date,body.source,body.confirmed);return {'saved':True}

    @router.put('/projects/{pid}/distribution')
    def distribution(pid:str,body:Distribution,request:Request):
        values=body.model_dump();note=values.pop('note');team.distribution(pid,user(request)['id'],values,note);return {'saved':True}

    @router.post('/projects/{pid}/reports')
    def prepare(pid:str,request:Request):return team.prepare(pid,user(request)['id'])

    @router.post('/projects/{pid}/retry')
    def retry(pid:str,request:Request):
        uid=user(request)['id'];team.limit('retry:'+uid,10,3600)
        with team.db() as c:
            team.member(c,pid,uid,REVIEWERS)
            if not c.execute("SELECT 1 FROM team_jobs WHERE project=? AND status IN ('queued','running')",(pid,)).fetchone():
                c.execute('INSERT INTO team_jobs(project,created) VALUES(?,?)',(pid,time.time()))
        return {'queued':True}

    @router.post('/projects/{pid}/reports/{rid}/approve')
    def approve(pid:str,rid:int,body:Approve,request:Request):return team.approve(pid,user(request)['id'],rid,body.hash,body.acknowledge)

    @router.get('/notifications')
    def notifications(request:Request):
        uid=user(request)['id']
        with team.db() as c:
            notes=[dict(n) for n in c.execute('SELECT n.* FROM team_notifications n JOIN team_members m ON m.project=n.project AND m.user_id=n.user_id WHERE n.user_id=? ORDER BY n.id DESC LIMIT 100',(uid,))]
            unread=c.execute('SELECT count(*) FROM team_notifications n JOIN team_members m ON m.project=n.project AND m.user_id=n.user_id WHERE n.user_id=? AND n.read_at IS NULL',(uid,)).fetchone()[0]
        return {'notifications':notes,'unread':unread}

    @router.post('/notifications/{nid}/read')
    def mark_read(nid:int,request:Request):
        uid=user(request)['id']
        with team.db() as c:
            r=c.execute('UPDATE team_notifications SET read_at=COALESCE(read_at,?) WHERE id=? AND user_id=? AND EXISTS(SELECT 1 FROM team_members m WHERE m.project=team_notifications.project AND m.user_id=?)',(time.time(),nid,uid,uid))
            if not r.rowcount:raise HTTPException(404,'Notification not found.')
        return {'read':True}

    team_mail.mount(router,team,user,save_image)
    app.include_router(router)
