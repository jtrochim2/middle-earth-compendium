#!/usr/bin/env python3
"""Import reviewed profile photographs without altering their pixels.

Usage: python scripts/import-profile-images.py [--refresh]
Source matches, crop coordinates and manual approvals live in
assets/profile-images.json. Existing files are reused by default.
The browser renders square portraits from reviewed pixel rectangles.
"""
import argparse,hashlib,json,struct,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def png_size(blob):
    if blob[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Expected a PNG photograph')
    return struct.unpack('>II',blob[16:24])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
    manifest=json.loads((ROOT/'assets/profile-images.json').read_text())
    data=json.loads((ROOT/'dist/data.json').read_text());updates=[]
    for item in manifest['images']:
        if item['reviewStatus']!='approved':continue
        profiles=[p for p in data['profiles'] if p['name']==item['profileName']]
        if not profiles:raise ValueError('No exact profile match: '+item['profileName'])
        dest=ROOT/'dist'/item['asset'];dest.parent.mkdir(parents=True,exist_ok=True)
        blob=urllib.request.urlopen(item['imageUrl'],timeout=40).read() if args.refresh or not dest.exists() else dest.read_bytes()
        if hashlib.sha256(blob).hexdigest()!=item['sha256']:raise ValueError('Source changed; review it before replacing '+item['profileName'])
        width,height=png_size(blob);x,y,w,h=item['portraitCrop']
        if min(x,y)<0 or min(w,h)<=0 or x+w>width or y+h>height or w!=h:raise ValueError('Invalid portrait crop: '+item['profileName'])
        dest.write_bytes(blob)
        for p in profiles:
            p.update(photo=item['asset'],portrait=item['asset'],portraitCrop={'x':x,'y':y,'width':w,'height':h,'sourceWidth':width,'sourceHeight':height},photoAlt=item['alt'],photoWidth=width,photoHeight=height,photoSource=item['sourcePage'],photoCredit=item['credit'],photoVariant=item['variant'])
        updates.append(item['profileName'])
    (ROOT/'dist/data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    print('Imported '+str(len(updates))+' reviewed images; exact profile matches, source hashes and crop bounds verified.')
if __name__=='__main__':main()
