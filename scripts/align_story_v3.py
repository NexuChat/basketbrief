"""Find captured UI states in the encoded video before cutting source footage."""
import json,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'video3'
r=json.loads((OUT/'recording.json').read_text())
raw=subprocess.check_output(['ffmpeg','-v','error','-i',r['video'],'-vf','fps=5,scale=160:90','-pix_fmt','rgb24','-f','rawvideo','-'])
f=np.frombuffer(raw,dtype=np.uint8).reshape((-1,90,160,3));offset=len(f)/5-r['marks'][-1]['time']-6
for m in r['marks']:
 target=np.asarray(Image.open(OUT/'screens'/f"{m['name']}.png").convert('RGB').resize((160,90)),dtype=np.int16)
 expected=m['time']+offset;a=max(0,int((expected-6)*5));b=min(len(f),int((expected+6)*5));scores=np.abs(f[a:b].astype(np.int16)-target).mean(axis=(1,2,3));best=a+int(scores.argmin());m['video_time']=best/5;m['matching_error']=round(float(scores.min()),3)
 print(m['name'],m['video_time'],m['matching_error'])
(OUT/'recording.json').write_text(json.dumps(r,indent=2))
