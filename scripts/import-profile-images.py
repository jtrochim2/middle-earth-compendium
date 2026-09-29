#!/usr/bin/env python3
"""Import reviewed or identity-matched photographs without altering their pixels.

Usage: python scripts/import-profile-images.py [--refresh]
Source matches, crop coordinates and manual approvals live in
assets/profile-images.json. Existing files are reused by default.
The browser renders square portraits from reviewed pixel rectangles.
"""
import argparse,hashlib,io,json,struct,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def png_size(blob):
    if blob[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Expected a PNG photograph')
    return struct.unpack('>II',blob[16:24])

def image_size(blob):
    if blob.startswith(b'\x89PNG\r\n\x1a\n'):return png_size(blob)
    if not blob.startswith(b'\xff\xd8'):raise ValueError('Expected PNG or JPEG photograph')
    stream=io.BytesIO(blob);stream.read(2)
    while True:
        marker=stream.read(1)
        if not marker:raise ValueError('JPEG dimensions missing')
        if marker!=b'\xff':continue
        code=stream.read(1)
        while code==b'\xff':code=stream.read(1)
        if code in (b'\xd8',b'\xd9'):continue
        size=struct.unpack('>H',stream.read(2))[0]
        if code in (b'\xc0',b'\xc1',b'\xc2'):
            _,height,width=struct.unpack('>BHH',stream.read(5));return width,height
        stream.seek(size-2,1)

def crop_data(rect,width,height,name):
    x,y,w,h=rect
    if min(x,y)<0 or min(w,h)<=0 or x+w>width or y+h>height or w!=h:raise ValueError('Invalid crop: '+name)
    return {'x':x,'y':y,'width':w,'height':h,'sourceWidth':width,'sourceHeight':height}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
    manifest=json.loads((ROOT/'assets/profile-images.json').read_text())
    data=json.loads((ROOT/'dist/data.json').read_text());updates=[]
    for item in manifest['images']:
        if item['reviewStatus'] not in ('approved','identity-matched'):continue
        profiles=[p for p in data['profiles'] if p['name']==item['profileName']]
        if not profiles:raise ValueError('No exact profile match: '+item['profileName'])
        dest=ROOT/'dist'/item['asset'];dest.parent.mkdir(parents=True,exist_ok=True)
        blob=urllib.request.urlopen(item['imageUrl'],timeout=40).read() if args.refresh or not dest.exists() else dest.read_bytes()
        if hashlib.sha256(blob).hexdigest()!=item['sha256']:raise ValueError('Source changed; review it before replacing '+item['profileName'])
        width,height=image_size(blob)
        crops={key:crop_data(item[key],width,height,item['profileName']) for key in ('portraitCrop','photoCrop') if key in item}
        dest.write_bytes(blob)
        for p in profiles:
            # A reviewed PDF tile takes precedence over the community portrait.
            if p.get('photoBook'):continue
            p.update(photo=item['asset'],portrait=item['asset'],photoAlt=item['alt'],photoWidth=width,photoHeight=height,photoSource=item['sourcePage'],photoCredit=item['credit'],photoVariant=item['variant'])
            for key in ('portraitCrop','photoCrop'):
                p.pop(key,None)
            p.update(crops)
        updates.append(item['profileName'])
    (ROOT/'dist/data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    print('Imported '+str(len(updates))+' named images; exact profile matches, source hashes and crop bounds verified.')
if __name__=='__main__':main()
