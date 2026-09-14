"""Produce a narrated, chaptered film from verified product captures.

All UI assets are real captures. Intro diagrams are labelled scenario illustrations.
No private documents, customer endorsements or third-party video/audio are included.
"""
from pathlib import Path
import json,subprocess,hashlib,html,math,wave,os
import numpy as np
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'video3';OUT.mkdir(exist_ok=True)
W,H,FPS=1920,1080,30

def run(*args):return subprocess.run(args,check=True,capture_output=True,text=True)
def duration(p):return float(run('ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)).stdout)

# One question, a demonstrated loop, a late correction, and the same evidence reaching both donors.
SCENES=[
 dict(id='cold-open',kind='motion',chapter='THE MOMENT',title='The report is sent.',sub='Then this arrives.',voice='You have sent the report to both donors. Then a message arrives.',hold=6.5),
 dict(id='correction-hook',kind='screen',asset='correction-typed-detail',chapter='THE MOMENT',title='“88 delivered.\nNot 92.”',sub='Who checks the change?\nWho tells both donors?',voice='Eighty-eight delivered. Not ninety-two. Who checks that correction? And who makes sure both donors hear about it?',hold=10),
 dict(id='people',kind='motion',chapter='THE PEOPLE',title='The coordinator\nbecomes the messenger.',sub='Receipts with Rana. Counts with Sami.\nTwo donors waiting for one consistent account.',voice='For a small relief team, the evidence lives with different volunteers. The coordinator ends up chasing the answers and keeping every report consistent.',hold=10),
 dict(id='promise',kind='motion',chapter='BASKETBRIEF',title='Follow up.\nFollow through.',sub='An agent for the work between the receipt and the report.',voice='BasketBrief takes on that follow-up. Let me show you one complete week, with fictional people and a live Strands agent.',hold=9),
 dict(id='start',kind='screen',asset='overview',chapter='01 / FIND THE GAP',title='Three sources.\nOne missing receipt.',sub='USD 1,260 reported\nUSD 60 still needs evidence',voice='The team reports twelve hundred and sixty dollars spent. Sixty dollars has no receipt. BasketBrief reads the sources and finds that gap.',hold=10),
 dict(id='ask-rana',kind='screen',asset='receipt-question-detail',chapter='01 / FIND THE GAP',title='Ask Rana.',sub='The question reaches the contributor\nwho can answer it.',voice='Here is Rana’s inbox. The agent has asked her for the transport receipt. Amal does not have to relay the question, and the same answer will support both reports.',hold=12),
 dict(id='receipt',kind='screen',asset='original-receipt-detail',chapter='02 / REVIEW THE EVIDENCE',title='The source\nstays in view.',sub='Photograph → transcription → review',voice='Rana uploads the photograph. Nova Pro reads it through AgentCore Runtime. The original and the transcription stay together so the coordinator can check what the machine read.',hold=12),
 dict(id='approve',kind='screen',asset='ready-first-detail',chapter='02 / REVIEW THE EVIDENCE',title='Amal decides\nwhat gets shared.',sub='An approval belongs to this exact version.',voice='The evidence is ready. Amal reviews the report and approves this version. The agent can prepare and follow up; approval stays with the coordinator.',hold=11),
 dict(id='first-send',kind='screen',asset='first-donor-detail',chapter='02 / REVIEW THE EVIDENCE',title='Now the donor\nhas a copy.',sub='An approved snapshot,\ndelivered inside BasketBrief.',voice='The first report is now in the donor’s inbox. It records ninety-two delivered and eight returned. That copy will stay intact.',hold=10),
 dict(id='turn',kind='motion',chapter='LATER THAT WEEK',title='Then the count\nchanges.',sub='92 → 88',voice='Now we return to that late correction.',hold=4),
 dict(id='gap',kind='screen',asset='gap-detail',chapter='03 / FOLLOW THE CORRECTION',title='Four kits\nneed an answer.',sub='100 loaded − 88 delivered − 8 returned = 4',voice='Sami reports eighty-eight delivered. Four kits no longer reconcile. BasketBrief stops the earlier approval from authorizing this changed report, and opens a follow-up.',hold=12),
 dict(id='ask-sami',kind='screen',asset='field-question-detail',chapter='03 / FOLLOW THE CORRECTION',title='Ask Sami\nto check the records.',sub='A discrepancy is a question to resolve.',voice='This is the question in Sami’s inbox. The system keeps households unknown. A difference in kit counts cannot tell us how many people received help.',hold=11),
 dict(id='reply',kind='screen',asset='answer-typed-detail',chapter='03 / FOLLOW THE CORRECTION',title='“Returned kits: 12.”',sub='The contributor supplies the missing fact.',voice='Sami checks storage and confirms twelve returned. The answer closes the gap. BasketBrief prepares the amendment from the updated evidence.',hold=10),
 dict(id='compare',kind='screen',asset='amendment-review-detail',chapter='03 / FOLLOW THE CORRECTION',title='See both changes.\nThen approve.',sub='Delivered: 92 → 88\nReturned: 8 → 12',voice='Amal sees both changes before approving: delivered falls to eighty-eight, returned rises to twelve. The amendment needs its own approval.',hold=10),
 dict(id='donor-en',kind='screen',asset='amendment-english-detail',chapter='04 / CLOSE THE LOOP',title='The correction\nreaches the donor.',sub='New version, with the changes visible.',voice='Northstar receives the approved amendment. The exact changes are visible, and the original report is still there.',hold=9),
 dict(id='donor-ar',kind='screen',asset='amendment-arabic-detail',chapter='04 / CLOSE THE LOOP',title='The same evidence.\nIn Arabic, too.',sub='Both donors receive the approved version.',voice='The Arabic donor receives the same facts and amendment. One evidence trail, carried through to both recipients.',hold=8),
 dict(id='team',kind='screen',asset='team-notifications',chapter='YOUR OWN TEAM',title='Separate accounts.\nConnected work.',sub='Contributor → reviewer → donor',voice='For your own team, each person signs in separately. New evidence creates a notification for the responsible reviewer. Donors see approved reports only.',hold=11),
 dict(id='team-review',kind='screen',asset='team-source',chapter='YOUR OWN TEAM',title='Attach it once.\nCount it once.',sub='The receipt completes the existing expense.',voice='A requested receipt attaches to the original expense, avoiding a second charge. Multiple currencies stay separate until a reviewer supplies an exchange rate.',hold=10),
 dict(id='architecture',kind='motion',chapter='WHY AN AGENT',title='Interpretation needs judgment.\nApproval needs a boundary.',sub='Strands + Nova Pro · AgentCore Runtime + Memory',voice='Strands and Nova interpret messages and choose tools. AgentCore Runtime reads images; Memory provides advisory vendor history. Code enforces arithmetic, permissions and versioned approval.',hold=13),
 dict(id='evidence',kind='motion',chapter='WHAT WE VERIFIED',title='A working loop.\nVisible boundaries.',sub='Live guided run · Separate-account handoff\n121 automated tests · Selected Gmail PDF import',voice='We tested the complete live loop, separate team accounts, and a private Gmail attachment import. Our automated tests cover the boundaries. Field impact and time saved have not yet been measured.',hold=14),
 dict(id='close',kind='motion',chapter='BASKETBRIEF',title='Every correction\ndeserves follow-through.',sub='basketbrief.mlki.app',voice='When the facts change, the follow-up should not depend on one person remembering everyone. BasketBrief. Every correction deserves follow-through.',hold=11),
]

CSS='''@font-face{font-family:Plex;src:url("file:///home/dev/competitions/agents-for-humans/basketbrief/basketbrief/static/fonts/IBMPlexSans-normal-400-latin.woff2")}@font-face{font-family:Plex;src:url("file:///home/dev/competitions/agents-for-humans/basketbrief/basketbrief/static/fonts/IBMPlexSans-normal-600-latin.woff2");font-weight:600}@font-face{font-family:Display;src:url("file:///home/dev/competitions/agents-for-humans/basketbrief/basketbrief/static/fonts/BricolageGrotesque-600-latin.woff2");font-weight:600}*{box-sizing:border-box}body{margin:0;width:1920px;height:1080px;overflow:hidden;background:#111610;color:#f5f2e8;font-family:Plex,sans-serif}.scene{position:absolute;inset:0;padding:76px 86px;background:radial-gradient(ellipse at 100% 0,#26302066,transparent 65%),#111610}.light{background:#f3efe3;color:#18211b}.brand{position:absolute;top:58px;left:86px;display:flex;align-items:center;gap:14px;font-family:Display;font-size:29px}.brand img{width:35px}.chapter{position:absolute;top:69px;right:86px;font-size:20px;letter-spacing:.14em;color:#b1bda3}.light .chapter{color:#586853}.copy{position:absolute;left:86px;top:265px;width:510px}.copy h1{font-family:Display;font-size:70px;letter-spacing:-.045em;line-height:1.04;font-weight:600;margin:0 0 36px;white-space:pre-line}.copy p{font-size:26px;line-height:1.5;white-space:pre-line;color:#bdc7b1;margin:0}.light .copy p{color:#596b53}.screen-wrap{position:absolute;left:660px;top:172px;width:1180px;height:735px;display:flex;align-items:center;justify-content:center;overflow:hidden;border-radius:20px;background:#0d100b;border:1px solid #46523b;box-shadow:0 24px 70px #0005}.screen-wrap img{width:100%;height:100%;object-fit:contain}.foot{position:absolute;left:86px;bottom:60px;color:#b1bda3;font-size:20px;letter-spacing:.02em}.light .foot{color:#596b53}.page{position:absolute;right:86px;bottom:59px;font-size:22px;color:#b1bda3}.bar{position:absolute;bottom:0;left:0;height:5px;background:#c9ef89}.motion .copy{top:220px;width:1650px}.motion .copy h1{font-size:96px;max-width:1620px;line-height:1.04}.motion .copy p{font-size:33px}.diagram{position:absolute;left:86px;right:86px;top:560px;display:flex;align-items:center;gap:32px}.node{background:#edf1dd;color:#192116;padding:30px;border-radius:18px;min-height:155px;flex:1;border:1px solid #c8d2b8}.node b{display:block;font:600 36px Display;margin-bottom:12px}.node span{font-size:24px}.node.dark{background:#263320;color:#e8f6cf;border-color:#64724e}.arrow{font-size:56px;color:#a7bb8d}.message{position:absolute;left:780px;top:530px;width:900px;padding:40px;border-radius:20px;border-left:7px solid #e88d5d;background:#22301d;box-shadow:0 28px 80px #0006;transform:rotate(-2deg)}.message small{font-size:23px;color:#c6d4b8}.message b{display:block;margin-top:20px;font:600 46px Display}.cold .copy{top:245px}.cold .copy h1{font-size:127px}.sent{display:inline-block;margin-top:35px;padding:16px 24px;border:1px solid #72915b;border-radius:14px;color:#c9ef89;font-size:25px}.wordmark{position:absolute;left:86px;top:160px;font:600 42px Display;color:#bddb95}.numbers{display:flex;gap:50px;align-items:center;position:absolute;left:1050px;top:495px;font:600 190px Display}.numbers .old{color:#8c9b80;text-decoration:line-through;text-decoration-thickness:4px}.numbers .new{color:#cbef8d}.evidence{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;position:absolute;left:86px;right:86px;top:600px}.evidence div{border-top:2px solid #748962;padding-top:22px}.evidence b{font:600 65px Display;display:block;color:#c9ef89}.evidence span{font-size:24px;color:#bdc7b1}.end .copy{top:260px}.end .copy h1{font-size:123px}.end .copy p{font-size:44px;color:#cbef8d;margin-top:60px}.source{position:absolute;bottom:111px;left:86px;font-size:20px;color:#bdc7b1}'''

def escape(s):return html.escape(s)
def page_for(s,i):
    light=s['id']=='people'; cls='scene '+('motion ' if s['kind']=='motion' else '')+('light ' if light else '')+('cold ' if s['id']=='cold-open' else '')+('end ' if s['id']=='close' else '')
    extra='';sub=s['sub']
    if s['kind']=='screen':
        path=OUT/'screens'/f"{s['asset']}.png"
        if s['asset'].startswith('team-'):path=ROOT/'video2/stills'/f"{s['asset']}.png"
        extra=f'<div class="screen-wrap enter"><img src="{path.as_uri()}"></div>'
    elif s['id']=='cold-open':
        extra='<div class="message reveal"><small>SAMI · DELIVERY TEAM</small><b>Correction: 88 kits delivered, not 92.</b></div>';sub='✓ Shared with both donors'
    elif s['id']=='people':
        extra='<div class="diagram"><div class="node enter"><b>Rana</b><span>The receipt</span></div><span class="arrow">→</span><div class="node dark enter"><b>Amal</b><span>The coordinator</span></div><span class="arrow">→</span><div class="node enter"><b>Two donors</b><span>One consistent account</span></div></div>'
    elif s['id']=='promise':
        extra='<div class="diagram"><div class="node dark enter"><b>Find the gap</b><span>Read the incoming evidence</span></div><span class="arrow">→</span><div class="node dark enter"><b>Ask & reconcile</b><span>Follow up with the contributor</span></div><span class="arrow">→</span><div class="node dark enter"><b>Review & deliver</b><span>Human approval, saved history</span></div></div>'
    elif s['id']=='turn':sub='';extra='<div class="numbers"><span class="old">92</span><span class="new reveal">88</span></div>'
    elif s['id']=='architecture':
        extra='<div class="diagram"><div class="node dark enter"><b>Strands + Nova</b><span>Interpret · choose tools</span></div><span class="arrow">→</span><div class="node dark enter"><b>AgentCore</b><span>Runtime: image reader<br>Memory: vendor hints</span></div><span class="arrow">→</span><div class="node enter"><b>Application code</b><span>Facts · roles · approval<br>Report history · delivery</span></div></div>'
    elif s['id']=='evidence':
        sub='';extra='<div class="evidence"><div class="enter"><b>1 loop</b><span>Missing receipt → amendment</span></div><div class="enter"><b>3 roles</b><span>Separate-account handoff</span></div><div class="enter"><b>121</b><span>Automated boundary & workflow tests</span></div><div class="enter"><b>1 import</b><span>Private Gmail PDF test</span></div></div>'
    foot='Fictional scenario · Recorded live application'
    if s['id'] in ('cold-open','people','promise','turn'):foot='Fictional scenario · Story illustration'
    if s['id'].startswith('team'):foot='Synthetic data · Separate-account staging test'
    if s['id']=='architecture':foot='Architecture illustration · Implemented responsibilities'
    if s['id']=='evidence':foot='Verified system tests · No field impact measured'
    if s['id']=='close':foot='Hackathon prototype · No field pilot or measured time savings'
    script='''window.seek=(t,d)=>{document.querySelectorAll('.enter').forEach((e,i)=>{let x=Math.max(0,Math.min(1,(t-.25-i*.18)/.7));let q=1-Math.pow(1-x,3);e.style.opacity=x;e.style.transform='translateY('+((1-q)*28)+'px)'});document.querySelectorAll('.reveal').forEach(e=>{let x=Math.max(0,Math.min(1,(t-2.6)/.6));e.style.opacity=x;e.style.transform='translateY('+((1-x)*35)+'px)'});document.querySelector('.bar').style.width=(INDEX+t/d)/COUNT*100+'%';};'''.replace('INDEX',str(i)).replace('COUNT',str(len(SCENES)))
    return f'<!doctype html><meta charset="utf-8"><style>{CSS}</style><div class="{cls}"><div class="brand"><img src="{(ROOT/"basketbrief/static/mark.svg").as_uri()}">BasketBrief</div><div class="chapter">{escape(s["chapter"])}</div><div class="copy"><h1>{escape(s["title"])}</h1><p>{escape(sub)}</p></div>{extra}<div class="foot">{foot}</div><div class="page">{i+1:02d} / {len(SCENES):02d}</div><div class="bar"></div></div><script>{script}</script>'

def narrate():
    (OUT/'voice').mkdir(exist_ok=True)
    for s in SCENES:
        file=OUT/'voice'/f"{s['id']}.mp3";key=hashlib.sha256(('AndrewNeural:0:'+s['voice']).encode()).hexdigest();cache=file.with_suffix('.sha256')
        if not file.exists() or not cache.exists() or cache.read_text()!=key:
            run('edge-tts','--voice','en-US-AndrewNeural','--rate=+0%','--text',s['voice'],'--write-media',str(file));cache.write_text(key)
        s['voice_file']=str(file);s['voice_seconds']=duration(file);s['seconds']=math.ceil(max(s['hold'],s['voice_seconds']+1.1)*FPS)/FPS
        print('voice',s['id'],round(s['seconds'],2),flush=True)
    assert sum(s['seconds'] for s in SCENES)<295,'Film exceeds contest limit'


def render():
    (OUT/'scenes').mkdir(exist_ok=True);(OUT/'frames').mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/home/dev/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',args=['--allow-file-access-from-files','--hide-scrollbars'])
        page=browser.new_page(viewport={'width':W,'height':H},device_scale_factor=1)
        for i,s in enumerate(SCENES):
            if os.environ.get('FILM_SCENES') and s['id'] not in os.environ['FILM_SCENES'].split(','):
                assert Path(s['clip']).exists()
                continue
            file=OUT/'frames'/f"{s['id']}.html";file.write_text(page_for(s,i));page.goto(file.as_uri());page.evaluate('() => document.fonts.ready');page.wait_for_timeout(150)
            image=OUT/'frames'/f"{s['id']}.png";page.evaluate('(v)=>seek(v[0],v[1])',[4,s['seconds']]);page.screenshot(path=str(image))
            output=OUT/'scenes'/f'{i:02d}.mp4'
            if s['kind']=='motion':
                # Frame-addressable motion: no recording-clock or narration drift.
                proc=subprocess.Popen(['ffmpeg','-y','-v','error','-f','image2pipe','-framerate','15','-i','-','-vf','fps=30,format=yuv420p','-c:v','libopenh264','-b:v','5500k','-an',str(output)],stdin=subprocess.PIPE)
                for f in range(math.ceil(s['seconds']*15)):
                    page.evaluate('(v)=>seek(v[0],v[1])',[f/15,s['seconds']]);proc.stdin.write(page.screenshot())
                proc.stdin.close();assert proc.wait()==0
            else:
                # Preserve the full composition and safe margins in the encoded frame.
                run('ffmpeg','-y','-v','error','-loop','1','-i',str(image),'-t',str(s['seconds']),'-vf',"fps=30,format=yuv420p",'-c:v','libopenh264','-b:v','5500k','-an',str(output))
            # Include source video for the upload and reply, not just still UI states.
            motion_sources={'receipt':'receipt-selected','reply':'answer-typed','start':'overview'}
            if s['id'] in motion_sources:
                recording=json.loads((OUT/'recording.json').read_text())
                mark=next(m for m in recording['marks'] if m['name']==motion_sources[s['id']])
                box=mark['box'] or {'x':350,'y':150,'width':1520,'height':900}
                if s['id']=='reply':box={'x':350,'y':150,'width':1520,'height':900}
                x,y,w,h=[int(box[k])//2*2 for k in ('x','y','width','height')]
                h=min(h,1080-y);w=min(w,1920-x)
                live=OUT/'scenes'/f'{i:02d}-live.mp4'
                seconds=4 if s['id'] in ('receipt','reply') else 5
                source_start=94.0 if s['id']=='reply' else mark['video_time']
                vf=f'[1:v]crop={w}:{h}:{x}:{y},scale=1180:735:force_original_aspect_ratio=decrease,pad=1180:735:(ow-iw)/2:(oh-ih)/2:0x0d100b,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration={s["seconds"]}[ui];[0:v][ui]overlay=660:172'
                if s['id'] in ('receipt','reply'):vf+=":enable='lt(t,4)'"
                run('ffmpeg','-y','-v','error','-i',str(output),'-ss',str(source_start),'-t',str(seconds),'-i',recording['video'],'-filter_complex',vf,'-t',str(s['seconds']),'-c:v','libopenh264','-b:v','6500k','-an',str(live));output=live
            s['clip']=str(output);s['seconds']=duration(output);print('rendered',s['id'],flush=True)
        browser.close()


def music(total):
    # Original procedural underscore: soft harmonic pulses, no borrowed recording.
    rate=24000;t=np.arange(int((total+2)*rate))/rate;y=np.zeros_like(t)
    chords=[(130.81,196,261.63),(110,164.81,220),(146.83,220,293.66),(98,146.83,196)]
    for at in np.arange(0,total,4):
        a=int(at*rate);n=min(len(y)-a,int(5*rate));q=np.arange(n)/rate
        env=(1-np.exp(-q*2))*np.exp(-q*.85)
        sig=sum(np.sin(2*np.pi*freq*q+.2*j)/(j+2) for j,freq in enumerate(chords[int(at//4)%4]))
        y[a:a+n]+=env*sig*.021
    y*=np.clip(t/3,0,1)*np.clip((total-t)/5,0,1)
    path=OUT/'original-score.wav'
    with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes((np.clip(y,-1,1)*32767).astype('<i2').tobytes())
    return path


def caption_and_mix():
    at=0; cues=[];chapters=[];ins=[];filters=[]
    def ts(t,sep='.'):
        n=round(t*1000);return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02}{sep}{n%1000:03}'
    for i,s in enumerate(SCENES):
        s['start']=round(at,3);chapters.append({'title':s['chapter'],'start':s['start']})
        ins+=['-i',s['voice_file']];filters.append(f'[{i}:a]adelay={int((at+.4)*1000)}:all=1[a{i}]')
        words=s['voice'].split();chunks=[' '.join(words[j:j+12]) for j in range(0,len(words),12)];nwords=sum(len(c.split()) for c in chunks);cursor=at+.4
        for c in chunks:
            end=cursor+s['voice_seconds']*len(c.split())/nwords;cues.append((cursor,end,c));cursor=end
        at+=s['seconds']
    score=music(at);ins+=['-i',str(score)];filters.append(f'[{len(SCENES)}:a]volume=0.8[music]')
    streams=''.join(f'[a{i}]' for i in range(len(SCENES)))+'[music]'
    filters.append(streams+f'amix=inputs={len(SCENES)+1}:normalize=0:duration=longest,loudnorm=I=-16:TP=-1.5:LRA=9,atrim=0:{at}[out]')
    track=OUT/'soundtrack.m4a';run('ffmpeg','-y','-v','error',*ins,'-filter_complex',';'.join(filters),'-map','[out]','-c:a','aac','-ar','48000','-b:a','192k',str(track))
    listing=OUT/'scenes.txt';listing.write_text(''.join(f"file '{s['clip']}'\n" for s in SCENES))
    silent=OUT/'picture.mp4';run('ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(silent))
    final=OUT/'BasketBrief-final-20260914.mp4';run('ffmpeg','-y','-v','error','-i',str(silent),'-i',str(track),'-map','0:v','-map','1:a','-c','copy','-movflags','+faststart','-shortest',str(final))
    (OUT/'BasketBrief-final-20260914.en.vtt').write_text('WEBVTT\n\n'+''.join(f'{ts(a)} --> {ts(b)}\n{c}\n\n' for a,b,c in cues))
    (OUT/'BasketBrief-final-20260914.en.srt').write_text(''.join(f'{i}\n{ts(a,",")} --> {ts(b,",")}\n{c}\n\n' for i,(a,b,c) in enumerate(cues,1)))
    (OUT/'timeline.json').write_text(json.dumps(SCENES,indent=2))
    print('FINAL',duration(final),final,flush=True)

if __name__=='__main__':
    import sys
    mode=sys.argv[1] if len(sys.argv)>1 else 'all'
    if mode=='all':narrate();render();caption_and_mix()
    elif mode=='voice':narrate();(OUT/'voice-plan.json').write_text(json.dumps(SCENES,indent=2))
    elif mode=='rerender':SCENES=json.loads((OUT/'timeline.json').read_text());render();caption_and_mix()
    elif mode=='render':SCENES=json.loads((OUT/'voice-plan.json').read_text());render();caption_and_mix()
