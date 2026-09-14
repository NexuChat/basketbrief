"""Align recorder marks to actual encoded frames, rather than guessing pre-roll."""
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent.parent
V2=ROOT/'video2'


def main():
    path=V2/'marks.json';recording=json.loads(path.read_text())
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',recording['video'],'-vf','fps=5,scale=160:90','-pix_fmt','rgb24','-f','rawvideo','-'])
    frames=np.frombuffer(raw,dtype=np.uint8).reshape((-1,90,160,3))
    predicted_offset=len(frames)/5-recording['marks'][-1]['t']
    aligned={}
    for mark in recording['marks']:
        target=np.asarray(Image.open(V2/'mark-frames'/f'{mark["name"]}.png').convert('RGB').resize((160,90)),dtype=np.int16)
        expected=mark['t']+predicted_offset
        start=max(0,int((expected-18)*5));end=min(len(frames),int((expected+12)*5))
        scores=np.abs(frames[start:end].astype(np.int16)-target).mean(axis=(1,2,3))
        index=start+int(scores.argmin());aligned[mark['name']]=index/5
        print(mark['name'],aligned[mark['name']],round(float(scores.min()),2))
    recording['video_marks']=aligned
    path.write_text(json.dumps(recording,indent=2))


if __name__=='__main__':main()
