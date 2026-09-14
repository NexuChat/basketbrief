"""Optional verified-address email delivery. An outbox entry is not a delivery receipt."""
import os
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage

from fastapi import Request
from pydantic import BaseModel, Field

from .store import Conflict, digest
from .team import email, password_hash


def configured():return bool(os.getenv('BASKETBRIEF_SMTP_HOST') and os.getenv('BASKETBRIEF_MAIL_FROM') and os.getenv('BASKETBRIEF_PUBLIC_URL'))


def status(team,uid):
    from .team_mailbox import statuses
    with team.db() as c:
        counts={r[0]:r[1] for r in c.execute('SELECT status,count(*) FROM team_mail_outbox WHERE user_id=? GROUP BY status',(uid,))}
    providers=statuses(team,uid)
    return {'configured':configured(),'mailbox_connected':any(p['connected'] for p in providers.values()),'outbox':counts,'providers':providers}


def send_one(team):
    if not configured():return
    with team.db() as c:
        c.execute("UPDATE team_mail_outbox SET status='queued' WHERE status='sending' AND available<?",(time.time()-300,))
        job=c.execute("SELECT o.*,u.email FROM team_mail_outbox o JOIN team_users u ON u.id=o.user_id WHERE o.status='queued' AND o.available<=? ORDER BY o.id LIMIT 1",(time.time(),)).fetchone()
        if not job:return
        if job['notification_id']:
            allowed=c.execute('SELECT 1 FROM team_notifications n JOIN team_members m ON m.project=n.project AND m.user_id=n.user_id JOIN team_users u ON u.id=n.user_id WHERE n.id=? AND u.verified=1 AND u.email_notifications=1',(job['notification_id'],)).fetchone()
            if not allowed:
                c.execute("UPDATE team_mail_outbox SET status='cancelled' WHERE id=?",(job['id'],));return
        c.execute("UPDATE team_mail_outbox SET status='sending',attempts=attempts+1,available=? WHERE id=?",(time.time(),job['id']))
    message=EmailMessage();message['From']=os.environ['BASKETBRIEF_MAIL_FROM'];message['To']=job['email'];message['Subject']=job['subject']
    message['Message-ID']=f'<basketbrief-outbox-{job["id"]}@{os.environ["BASKETBRIEF_MAIL_FROM"].split("@")[-1].strip(">")}>'
    message.set_content(job['body']+'\n\n'+os.environ['BASKETBRIEF_PUBLIC_URL'].rstrip('/')+'/team')
    try:
        port=int(os.getenv('BASKETBRIEF_SMTP_PORT','587'));host=os.environ['BASKETBRIEF_SMTP_HOST']
        if port==465:server=smtplib.SMTP_SSL(host,port,timeout=15,context=ssl.create_default_context())
        else:
            server=smtplib.SMTP(host,port,timeout=15);server.starttls(context=ssl.create_default_context())
        with server:
            if os.getenv('BASKETBRIEF_SMTP_USER'):server.login(os.environ['BASKETBRIEF_SMTP_USER'],os.environ.get('BASKETBRIEF_SMTP_PASSWORD',''))
            server.send_message(message)
    except Exception as exc:
        with team.db() as c:c.execute('UPDATE team_mail_outbox SET status=?,available=?,error=? WHERE id=?',('failed' if job['attempts']>=3 else 'queued',time.time()+min(3600,60*2**job['attempts']),type(exc).__name__,job['id']))
    else:
        with team.db() as c:c.execute("UPDATE team_mail_outbox SET status='sent',error=NULL WHERE id=?",(job['id'],))


class Preferences(BaseModel):
    email_notifications:bool

class Address(BaseModel):
    email:str=Field(max_length=254)

class PasswordReset(BaseModel):
    token:str=Field(max_length=200)
    password:str=Field(min_length=12,max_length=256)


def mount(router,team,user,save_image):
    from .team_mailbox import mount as mount_mailboxes
    mount_mailboxes(router,team,user,save_image)
    def issue(uid,purpose):
        if not configured():raise Conflict('Email delivery is not configured. In-app notifications and invitation links still work.')
        team.limit('mail:'+uid,3,3600);token=secrets.token_urlsafe(32)
        with team.db() as c:
            c.execute('DELETE FROM team_tokens WHERE user_id=? AND purpose=?',(uid,purpose))
            c.execute('INSERT INTO team_tokens VALUES(?,?,?,?)',(digest(token),uid,purpose,time.time()+1800))
            url=os.environ['BASKETBRIEF_PUBLIC_URL'].rstrip('/')+'/team#'+purpose+'='+token
            c.execute('INSERT INTO team_mail_outbox(user_id,subject,body,available) VALUES(?,?,?,?)',(uid,'BasketBrief account '+purpose,'Use this one-time link within 30 minutes:\n'+url,time.time()))
        return {'queued':True,'sent':False}

    @router.post('/email/verify')
    def verify(request:Request):return issue(user(request)['id'],'verify')

    @router.post('/email/confirm')
    def confirm(body:PasswordResetToken,request:Request):
        uid=user(request)['id']
        with team.db() as c:
            row=c.execute("SELECT * FROM team_tokens WHERE hash=? AND user_id=? AND purpose='verify' AND expires>?",(digest(body.token),uid,time.time())).fetchone()
            if not row:raise Conflict('Verification link expired or was already used.')
            c.execute('DELETE FROM team_tokens WHERE hash=?',(digest(body.token),));c.execute('UPDATE team_users SET verified=1 WHERE id=?',(uid,))
        return {'verified':True}

    @router.post('/email/preferences')
    def preferences(body:Preferences,request:Request):
        u=user(request)
        if body.email_notifications and (not u['verified'] or not configured()):raise Conflict('Verify your email and configure email delivery before enabling email notifications.')
        with team.db() as c:c.execute('UPDATE team_users SET email_notifications=? WHERE id=?',(int(body.email_notifications),u['id']))
        return {'saved':True}

    @router.post('/password/reset-request')
    def reset_request(body:Address,request:Request):
        if not configured():raise Conflict('Password reset emails are not configured.')
        address=email(body.email);team.limit('reset:'+address,3,3600)
        with team.db() as c:u=c.execute('SELECT id FROM team_users WHERE email=?',(address,)).fetchone()
        if u:issue(u['id'],'reset')
        return {'message':'If this account exists, a reset message has been queued.'}

    @router.post('/password/reset')
    def reset(body:PasswordReset):
        encoded=password_hash(body.password)
        with team.db() as c:
            row=c.execute("SELECT * FROM team_tokens WHERE hash=? AND purpose='reset' AND expires>?",(digest(body.token),time.time())).fetchone()
            if not row:raise Conflict('Reset link expired or was already used.')
            c.execute('UPDATE team_users SET password=? WHERE id=?',(encoded,row['user_id']))
            c.execute('DELETE FROM team_sessions WHERE user_id=?',(row['user_id'],));c.execute('DELETE FROM team_tokens WHERE user_id=?',(row['user_id'],))
        return {'reset':True}


class PasswordResetToken(BaseModel):
    token:str=Field(max_length=200)
