from __future__ import annotations

import hashlib
import io
import json
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError

from .agent import process_project
from .store import numeric_values as store_numbers, Store, Conflict, Forbidden, ROLES

STATIC = Path(__file__).parent / 'static'


class EvidenceIn(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    kind: Literal['message', 'receipt', 'expense_claim', 'correction'] = 'message'
    question_id: int | None = None


class ApprovalIn(BaseModel):
    report_id: int
    hash: str = Field(min_length=1, max_length=64)
    acknowledge: bool = False


def export_report(payload, version, content_hash, language='en'):
    s=payload['summary']; ar=language=='ar'
    rows=[('الطرود المسلّمة حسب الفريق' if ar else 'Kits delivered · team-reported',s['delivered']),
          ('الطرود المرتجعة' if ar else 'Kits returned',s['returned']),
          ('الأسر الفريدة' if ar else 'Unique households',s['households']),
          ('الإنفاق المبلّغ عنه' if ar else 'Reported spending',f"USD {float(s['reported']):,.2f}"),
          ('الإنفاق المدعوم بإيصالات' if ar else 'Receipt-supported spending',f"USD {float(s['supported']):,.2f}"),
          ('إنفاق بلا إيصال' if ar else 'Spending without a receipt',f"USD {float(s['unsupported']):,.2f}")]
    body=''.join(f'<tr><th>{escape(k)}</th><td>{escape(str(v)) if v is not None else ("غير معروف" if ar else "Not established")}</td></tr>' for k,v in rows)
    issues=''.join(f'<li>{escape(i if isinstance(i,str) else i["note"])}</li>' for i in payload.get('issues',[]))
    return f'''<!doctype html><html lang="{'ar' if ar else 'en'}" dir="{'rtl' if ar else 'ltr'}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BasketBrief · Report v{version}</title>
    <style>body{{max-width:760px;margin:70px auto;padding:0 24px;color:#19372e;background:#faf9f4;font:17px/1.65 Georgia,serif}}small{{font:12px sans-serif;letter-spacing:1px}}h1{{font-size:42px;line-height:1.15}}table{{width:100%;border-collapse:collapse;margin:35px 0}}th,td{{padding:15px 0;border-bottom:1px solid #d4ded5;text-align:start}}td{{text-align:end}}th{{font-weight:normal}}footer{{font:12px/1.7 sans-serif;color:#55645b;overflow-wrap:anywhere}}.tag{{background:#e3ece0;padding:7px 12px;border-radius:20px}}</style>
    <small>BASKETBRIEF / DELIVERY REPORT</small><h1>{'تقرير إغاثة الفيضان — الأسبوع الأول' if ar else 'Flood relief distribution — week one'}</h1><span class="tag">{'نسخة معتمدة' if ar else 'Approved snapshot'} · v{version}</span><table>{body}</table><ul>{issues}</ul>
    <footer><p>{escape(payload['disclosure'])}</p><p>Version {version} · SHA-256 {escape(content_hash)}</p><p>Delivered inside BasketBrief. This is not an external delivery or read receipt.</p></footer></html>'''


def create_app(db_path=None, engine=None, background=True):
    db_path=Path(db_path or os.environ.get('BASKETBRIEF_DB','data/basketbrief.db'))
    engine=engine or os.environ.get('BASKETBRIEF_ENGINE','local')
    store=Store(db_path)
    stop=threading.Event()

    def worker():
        while not stop.is_set():
            job=store.claim_job()
            if not job:
                stop.wait(.4)
                continue
            try:
                process_project(store,job['project'],job['engine'],db_path.parent/'uploads')
                store.deliver(job['project'])
                store.finish_job(job['id'])
            except Exception as exc:
                # Provider errors can include sensitive request details. Never expose them.
                reason=f"Review paused ({type(exc).__name__}). Your evidence is saved. The coordinator can retry."
                store.log(job['project'],'error','The review paused safely',{'reason':reason})
                store.finish_job(job['id'],reason)

    @asynccontextmanager
    async def lifespan(app):
        thread=None
        if background:
            thread=threading.Thread(target=worker,name='basketbrief-worker',daemon=True)
            thread.start()
        yield
        stop.set()
        if thread: thread.join(timeout=2)

    app=FastAPI(title='BasketBrief',lifespan=lifespan,docs_url=None,redoc_url=None)
    app.state.store=store
    app.mount('/static',StaticFiles(directory=STATIC),name='static')

    @app.middleware('http')
    async def security_headers(request,call_next):
        response=await call_next(request)
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api') else 'no-cache'
        return response

    @app.exception_handler(Conflict)
    async def conflict(request,exc):return JSONResponse({'error':str(exc)},status_code=409)

    @app.exception_handler(Forbidden)
    async def forbidden(request,exc):return JSONResponse({'error':str(exc)},status_code=403)

    def role(request,pid):
        header=request.headers.get('authorization','')
        token=header[7:] if header.startswith('Bearer ') else ''
        return store.authenticate(pid,token)

    @app.get('/healthz')
    def health():return {'ok':True,'engine':engine,'name':'BasketBrief'}

    def asset_version():
        # One build stamp from the asset bytes: a returning visitor (or a judge who
        # looked yesterday) never gets yesterday's stylesheet out of their cache.
        h=hashlib.sha256()
        for name in ('style.css','app.js','fonts.css'):
            f=STATIC/name
            if f.exists():h.update(f.read_bytes())
        return h.hexdigest()[:10]

    @app.get('/')
    def index():
        html=(STATIC/'index.html').read_text()
        v=asset_version()
        html=html.replace('/static/style.css','/static/style.css?v='+v).replace('/static/app.js','/static/app.js?v='+v)
        return HTMLResponse(html,headers={'Cache-Control':'no-store, must-revalidate'})

    @app.post('/api/projects',status_code=201)
    def create():return store.create_project(engine)

    @app.get('/api/projects/{pid}')
    def state(pid:str,request:Request):return store.state(pid,role(request,pid))

    @app.post('/api/projects/{pid}/evidence',status_code=201)
    def evidence(pid:str,body:EvidenceIn,request:Request):
        return store.submit(pid,role(request,pid),body.text,body.kind,body.question_id)

    @app.post('/api/projects/{pid}/approve')
    def approve(pid:str,body:ApprovalIn,request:Request):
        result=store.approve(pid,role(request,pid),body.report_id,body.hash,body.acknowledge)
        store.deliver(pid)
        return result

    @app.post('/api/projects/{pid}/retry')
    def retry(pid:str,request:Request):
        store.retry(pid,role(request,pid))
        return {'queued':True}

    @app.get('/api/projects/{pid}/reports/{report_id}',response_class=HTMLResponse)
    def report(pid:str,report_id:int,request:Request):
        actor=role(request,pid)
        with store.db() as c:
            if actor=='coordinator':
                r=c.execute('SELECT * FROM reports WHERE project=? AND id=?',(pid,report_id)).fetchone()
                if not r or r['status'] not in ('approved','delivered'):raise Forbidden('Only approved snapshots can be exported.')
                return HTMLResponse(export_report(json.loads(r['payload']),r['version'],r['hash']))
            if not actor.startswith('donor'):raise Forbidden('This report is only for its approved recipients.')
            message=c.execute('SELECT body FROM inbox WHERE project=? AND recipient=? AND delivery_key=?',(pid,actor,f'report:{report_id}:{actor}')).fetchone()
            if not message:raise Forbidden('No report has been delivered to this inbox.')
            p=json.loads(message['body'])
            return HTMLResponse(export_report(p,p['version'],p['hash'],p['language']))

    @app.post('/api/read-receipt')
    async def read_any_receipt(request:Request,file:UploadFile=File(...)):
        """Read a receipt the visitor brought, and show what the guards do with it.

        Nothing is stored and nothing enters a workspace. This exists so the first
        thing a visitor sees is a guard refusing something on their own piece of
        paper, rather than a story about strangers.
        """
        raw=await file.read(2_000_001)
        if len(raw)>2_000_000:return JSONResponse({'error':'Use an image smaller than 2 MB.'},status_code=422)
        try:
            picture=Image.open(io.BytesIO(raw))
            if picture.width*picture.height>12_000_000:raise ValueError('too large')
            picture.verify()
            picture=Image.open(io.BytesIO(raw)).convert('RGB')
            picture.thumbnail((1600,1600))
        except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):
            return JSONResponse({'error':'Upload a valid PNG or JPEG.'},status_code=422)
        buffer=io.BytesIO();picture.save(buffer,format='PNG')
        from . import vendors, vision
        started=time.monotonic()
        reading=vision.read_receipt(buffer.getvalue())
        ledger=vendors.check(reading.get('vendor') or '') if reading.get('ok') else {'known':None}
        text=vision.as_source_text(reading)
        numbers=sorted(str(n) for n in store_numbers(text))
        return {'ok':bool(reading.get('ok')),
                'seconds':round(time.monotonic()-started,1),
                'read_on':reading.get('where','in-process'),
                'model':reading.get('model'),
                'vendor':reading.get('vendor'),'invoice_no':reading.get('invoice_no'),
                'date':reading.get('date'),'currency':reading.get('currency'),
                'items':[{k:(str(v) if v is not None else None) for k,v in i.items()} for i in reading.get('items',[])],
                'stated_total':str(reading['stated_total']) if reading.get('stated_total') is not None else None,
                'summed_total':str(reading['summed_total']) if reading.get('summed_total') is not None else None,
                'mismatch':reading.get('mismatch'),
                'confidence':reading.get('confidence'),
                'vendor_known':ledger.get('known'),'vendor_note':ledger.get('note'),
                'recordable':numbers[:24],
                'source_text':text}

    @app.post('/api/projects/{pid}/upload',status_code=201)
    async def upload(pid:str,request:Request,file:UploadFile=File(...),question_id:int|None=Form(None)):
        actor=role(request,pid)
        if actor!='finance':raise Forbidden('Receipt images belong to the finance contributor.')
        raw=await file.read(2_000_001)
        if len(raw)>2_000_000:return JSONResponse({'error':'Use an image smaller than 2 MB.'},status_code=422)
        try:
            picture=Image.open(io.BytesIO(raw))
            if picture.width*picture.height>12_000_000:raise ValueError('Image too large')
            picture.verify()
            picture=Image.open(io.BytesIO(raw)).convert('RGB')
            picture.thumbnail((1600,1600))
        except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):
            return JSONResponse({'error':'Upload a valid, reasonably sized PNG or JPEG receipt.'},status_code=422)
        name=secrets.token_hex(20)+'.png'
        folder=db_path.parent/'uploads';folder.mkdir(parents=True,exist_ok=True)
        path=folder/name;picture.save(path,format='PNG')
        try:
            result=store.submit(pid,actor,'Receipt image attached. Transcription pending.','receipt',question_id,name)
        except BaseException:
            path.unlink(missing_ok=True);raise
        return result

    @app.get('/api/projects/{pid}/evidence/{eid}/image')
    def evidence_image(pid:str,eid:int,request:Request):
        actor=role(request,pid)
        with store.db() as c:
            e=store.get_evidence(c,pid,eid)
            if actor not in ('coordinator',e['actor']):raise Forbidden('This source image is private to its contributor and coordinator.')
            if not e['attachment']:raise Conflict('This source has no image.')
            return FileResponse(db_path.parent/'uploads'/Path(e['attachment']).name,media_type='image/png')

    return app


app=create_app()
