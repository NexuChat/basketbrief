"""Write optional English captions timed to the encoded film's narration beats."""
import textwrap
from build_film import BEATS, V2, WORK, dur


def timestamp(value, separator='.'):
    ms=round(value*1000)
    hours,ms=divmod(ms,3600000);minutes,ms=divmod(ms,60000);seconds,ms=divmod(ms,1000)
    return f'{hours:02}:{minutes:02}:{seconds:02}{separator}{ms:03}'


def main():
    cues=[];offset=0
    for i,beat in enumerate(BEATS,1):
        narration=dur(V2/'vo'/f'{i:02}.mp3')
        chunks=textwrap.wrap(beat['vo'],width=100,break_long_words=False)
        total=sum(len(chunk) for chunk in chunks);at=offset+.45
        for chunk in chunks:
            end=at+narration*len(chunk)/total
            cues.append((at,end,'\n'.join(textwrap.wrap(chunk,width=52))))
            at=end
        offset+=dur(WORK/f'{i:02}.mp4')
    vtt='WEBVTT\n\n'+'\n\n'.join(f'{timestamp(a)} --> {timestamp(b)}\n{text}' for a,b,text in cues)+'\n'
    srt='\n\n'.join(f'{i}\n{timestamp(a,",")} --> {timestamp(b,",")}\n{text}' for i,(a,b,text) in enumerate(cues,1))+'\n'
    (V2/'BasketBrief-demo.en.vtt').write_text(vtt)
    (V2/'BasketBrief-demo.en.srt').write_text(srt)
    print(f'{len(cues)} caption cues; narration ends at {timestamp(cues[-1][1])}')


if __name__=='__main__':main()
