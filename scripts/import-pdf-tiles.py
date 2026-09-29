#!/usr/bin/env python3
"""Extract reviewed square photo regions from the user-supplied PDF.

Requires pymupdf and Pillow. Run after import-profile-images.py:
  python3 scripts/import-pdf-tiles.py [--manifest assets/lotr-pdf-profile-tiles.json]
                                     [--pdf /path/to/source.pdf]
The PDF stays outside dist; only miniature photo crops are exported.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'assets/pdf-profile-tiles.json')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    source = args.pdf or ROOT / manifest['sourceFile']
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['sourceSha256']:
        raise ValueError('PDF differs from the reviewed source; recheck crop coordinates.')
    document = pymupdf.open(source)
    data_path = ROOT / 'dist/data.json'
    data = json.loads(data_path.read_text())
    size = manifest['tileSize']
    output = ROOT / 'dist/images/pdf-tiles'
    output.mkdir(parents=True, exist_ok=True)
    updated = set()
    for tile in manifest['tiles']:
        matches = [p for p in data['profiles'] if p['name'] in tile['profileNames']]
        if set(tile['profileNames']) - {p['name'] for p in matches}:
            raise ValueError('Unknown profile in tile: ' + str(tile['profileNames']))
        page = document[tile['page'] - 1]
        rect = pymupdf.Rect(tile['rect'])
        if not page.rect.contains(rect) or abs(rect.width - rect.height) > .01:
            raise ValueError('Crop must be square and inside its page')
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=rect, alpha=False)
        image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        filename = matches[0]['id'] + '.jpg'
        image.save(output / filename, quality=92, optimize=True)
        portrait = filename
        if 'portraitRect' in tile:
            face = pymupdf.Rect(tile['portraitRect'])
            if not rect.contains(face) or abs(face.width - face.height) > .01:
                raise ValueError('Portrait crop must be square and inside its tile')
            pix = page.get_pixmap(matrix=pymupdf.Matrix(4, 4), clip=face, alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            psize = manifest.get('portraitSize', 160)
            image = image.resize((psize, psize), Image.Resampling.LANCZOS)
            portrait = matches[0]['id'] + '-face.jpg'
            image.save(output / portrait, quality=90, optimize=True)
        for p in matches:
            if p['id'] in updated:
                raise ValueError('Duplicate tile for ' + p['name'])
            updated.add(p['id'])
            p.update(photo='images/pdf-tiles/' + filename, portrait='images/pdf-tiles/' + portrait,
                     photoAlt=p['name'] + ' miniature', photoWidth=size, photoHeight=size,
                     photoCredit=manifest['sourceTitle'] + ', p. ' + str(tile.get('printedPage', tile['page'])),
                     photoSource='', photoVariant='', photoBook=manifest['sourceTitle'],
                     photoPage=tile.get('printedPage', tile['page']))
            p.pop('portraitCrop', None)
            p.pop('photoCrop', None)
    data_path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    remaining = [{'id': p['id'], 'name': p['name']} for p in data['profiles']
                 if not p.get('photoBook') and not p['name'].startswith('No Hero (')]
    books = {}
    for p in data['profiles']:
        if p.get('photoBook'):
            books.setdefault(p['photoBook'], {'profiles': 0, 'assets': set()})
            books[p['photoBook']]['profiles'] += 1
            books[p['photoBook']]['assets'].add(p['photo'])
    sources = [{'book': name, 'profiles': book['profiles'], 'squareTiles': len(book['assets'])}
               for name, book in sorted(books.items())]
    report = {'sources': sources, 'squareTiles': sum(s['squareTiles'] for s in sources),
              'updatedProfiles': sum(s['profiles'] for s in sources), 'profilesNeedingOtherSources': remaining}
    (ROOT / 'assets/pdf-tile-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Exported {len(manifest["tiles"])} square tiles for {len(updated)} profiles; {len(remaining)} need other sources.')


if __name__ == '__main__':
    main()
