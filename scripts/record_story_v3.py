"""Record an isolated fictional workspace through actual UI actions and live inference."""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'video3'; OUT.mkdir(exist_ok=True)
SHOTS=OUT/'screens';SHOTS.mkdir(exist_ok=True)

def main():
    marks=[]; errors=[]
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True,executable_path='/home/dev/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',args=['--hide-scrollbars'])
        ctx=b.new_context(viewport={'width':1920,'height':1080},record_video_dir=str(OUT/'raw'),record_video_size={'width':1920,'height':1080})
        pg=ctx.new_page();pg.on('pageerror',lambda e:errors.append(str(e)))
        pg.goto('https://basketbrief.mlki.app',wait_until='domcontentloaded')
        pg.evaluate("document.documentElement.style.zoom='1.35'")
        start=time.monotonic()
        def idle():
            pg.wait_for_function('() => typeof workspace !== "undefined" && workspace',timeout=30000)
            for _ in range(180):
                result=pg.evaluate("async () => {const s=await apiAs('coordinator');return {busy:s.busy,report:!!s.report,failed:s.jobs.find(j=>j.status==='failed')};}")
                if not result['busy'] and result['report']:
                    assert not result['failed'],result['failed']
                    pg.evaluate('() => refresh(true)');pg.wait_for_timeout(800);return
                pg.wait_for_timeout(1000)
            raise RuntimeError('Agent review did not finish')
        def role(r):
            pg.select_option('#role',r);pg.wait_for_timeout(1000)
        def shot(name,selector=None,hold=4):
            if selector: pg.locator(selector).first.scroll_into_view_if_needed()
            else: pg.evaluate('window.scrollTo(0,0)')
            pg.wait_for_timeout(600)
            pg.screenshot(path=str(SHOTS/f'{name}.png'))
            if selector:
                pg.locator(selector).first.screenshot(path=str(SHOTS/f'{name}-detail.png'))
            marks.append({'name':name,'time':round(time.monotonic()-start,3),'role':pg.evaluate('role'),'selector':selector,'box':pg.locator(selector).first.bounding_box() if selector else None})
            print(name,flush=True);(OUT/'capture-progress.json').write_text(json.dumps(marks,indent=2));pg.wait_for_timeout(hold*1000)
        idle();shot('overview')
        role('finance');shot('receipt-question','.contributor-question')
        pg.set_input_files('#receipt-image',str(ROOT/'basketbrief/static/sample-receipt.png'))
        shot('receipt-selected','#upload-form',2)
        pg.locator('#upload-form button[type=submit]').click();pg.wait_for_timeout(1200);idle()
        role('coordinator');shot('ready-first','.next-step')
        eid=pg.evaluate("state.evidence.find(e=>e.attachment).id")
        pg.locator(f'[data-source="{eid}"]').click();pg.wait_for_selector('#source-dialog[open]');shot('original-receipt','#source-dialog',5)
        pg.locator('#close-dialog').click()
        original=pg.evaluate('({id:state.report.id,hash:state.report.hash,version:state.report.version})')
        pg.locator('[data-action=approve]').click();pg.wait_for_timeout(1000);idle()
        role('donor_a');shot('first-donor','.inbox-card')
        role('field');pg.locator('[data-sample=correction]').click();shot('correction-typed','#evidence-form',4)
        pg.locator('#evidence-form button[type=submit]').click();pg.wait_for_timeout(1000);idle()
        role('coordinator');shot('gap','.next-step',6)
        refused=pg.evaluate('''async old => {try {await apiAs('coordinator','/approve',{method:'POST',body:JSON.stringify({report_id:old.id,hash:old.hash,acknowledge:true})});return 200;} catch(e){return e.status;}}''',original)
        assert refused==409,refused
        role('field');shot('field-question','.contributor-question',5)
        pg.locator('[data-sample=resolution]').click();shot('answer-typed','#evidence-form',4)
        pg.locator('#evidence-form button[type=submit]').click();pg.wait_for_timeout(1000);idle()
        role('coordinator');shot('amendment-review','.next-step',6)
        assert pg.evaluate('state.summary.delivered===88 && state.summary.returned===12')
        pg.locator('[data-action=approve]').click();pg.wait_for_timeout(1000);idle()
        role('donor_a');shot('amendment-english','.inbox-card',6)
        assert pg.locator('.inbox-card').count()==2
        role('donor_b');shot('amendment-arabic','.inbox-card',6)
        assert pg.locator('.inbox-card').count()==2
        details=pg.evaluate('({summary:state.summary,inbox:state.inbox.filter(i=>i.kind==="report").map(i=>({version:i.body.version,summary:i.body.summary,changes:i.body.changes}))})')
        path=pg.video.path();ctx.close();b.close()
    (OUT/'recording.json').write_text(json.dumps({'video':str(path),'marks':marks,'stale_approval_http_status':refused,'errors':errors,'final':details},indent=2))
    assert not errors,errors
    print('COMPLETE',path,flush=True)
if __name__=='__main__':main()
