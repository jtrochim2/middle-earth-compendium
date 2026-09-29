#!/usr/bin/env python3
"""Catalog identity-matched photos from a GitHub ZIP and recursive tree response.

Usage: python3 scripts/catalog-profile-images.py SOURCE.zip TREE.json
Keeps existing profile photos and records exact matches or explicit aliases.
Source bytes are verified against the tree's Git blob hashes before copying.
Run import-profile-images.py afterwards to apply the catalog to data.json.
"""
import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def normalize(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', value.lower())


def main():
    archive = zipfile.ZipFile(sys.argv[1])
    prefix = archive.namelist()[0].split('/')[0] + '/'
    tree = json.loads(Path(sys.argv[2]).read_text())
    entries = {e['path']: e for e in tree['tree'] if e['type'] == 'blob'}
    lookup = {}
    for path in entries:
        if '/pictures/' in path and path.endswith('.png'):
            lookup.setdefault(normalize(Path(path).stem), []).append(path)
    aliases = json.loads((ROOT / 'assets/profile-image-aliases.json').read_text())
    data = json.loads((ROOT / 'dist/data.json').read_text())
    manifest_path = ROOT / 'assets/profile-images.json'
    manifest = json.loads(manifest_path.read_text())
    covered = {i['profileName'] for i in manifest['images']}
    covered.update(p['name'] for p in data['profiles'] if p.get('photo'))
    missing = []
    excluded = []
    # Different costumes/forms have separate pictures with the same filename.
    preferred = {
        'Hobbit Archer': 'The Free Peoples',
        'Gandalf the Grey': 'The Free Peoples',
        "Gandalf the Grey (Thorin's Company)": 'Dwarven Holds',
        'Troll Brute': 'Gundabad & Dol Guldur',
        'Khamul the Easterling': 'Evil Legacy',
        'Orc Commander': 'Evil Legacy',
        'Peregrin Took, Guard of the Citadel': 'Gondor',
        'Peregrin Took': 'The Free Peoples',
        'Meriadoc Brandybuck': 'The Free Peoples',
        'Meriadoc Brandybuck, Esquire of Rohan': 'Rohan',
        'Saruman': 'Isengard',
        'The Witch-King of Angmar': 'Mordor',
        'The Witch-King of Angmar B': 'Mordor',
        'The Witch-King of Angmar C': 'Mordor',
    }
    preferred = {normalize(name): group for name, group in preferred.items()}
    for p in data['profiles']:
        name = p['name']
        if name.startswith('No Hero ('):
            excluded.append({'id': p['id'], 'name': name, 'reason': 'Roster placeholder, not a miniature'})
            continue
        if name in covered:
            continue
        source_name = aliases.get(name, name)
        paths = lookup.get(normalize(source_name), [])
        if name == 'Beorn the Bear':
            paths = ['static-resources/images/profiles/The Free Peoples/cards/Beorn the Bear.jpg']
        if not paths:
            missing.append({'id': p['id'], 'name': name})
            continue
        if len(paths) > 1:
            group = 'Gundabad & Dol Guldur' if name.startswith('Nazgul of Dol Guldur') else preferred.get(normalize(name))
            paths = [path for path in paths if path.split('/')[-3] == group]
            if len(paths) != 1:
                raise ValueError('Resolve ambiguous source: ' + name)
        path = paths[0]
        blob = archive.read(prefix + path)
        git_hash = hashlib.sha1(b'blob ' + str(len(blob)).encode() + b'\0' + blob).hexdigest()
        if git_hash != entries[path]['sha']:
            raise ValueError('ZIP does not match pinned tree: ' + path)
        asset = 'images/profiles/' + p['id'] + Path(path).suffix
        dest = ROOT / 'dist' / asset
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        source = 'https://github.com/avcordaro/mesbg-list-builder-v2024/blob/' + tree['sha'] + '/' + quote(path)
        item = {
            'profileName': name, 'asset': asset,
            'imageUrl': 'https://raw.githubusercontent.com/avcordaro/mesbg-list-builder-v2024/' + tree['sha'] + '/' + quote(path),
            'sourcePage': source,
            'credit': 'Image via MESBG List Builder community repository',
            'rights': 'Reuse permission not independently verified; source attribution retained.',
            'alt': name + ' miniature',
            'variant': '',
            'reviewStatus': 'identity-matched',
            'matchMethod': 'explicit-alias' if name in aliases else 'normalized-exact-name',
            'sourceName': Path(path).stem,
            'sha256': hashlib.sha256(blob).hexdigest(),
        }
        if name == 'Beorn the Bear':
            item.update(portraitCrop=[2125, 175, 230, 230], photoCrop=[1915, 185, 470, 470],
                        matchMethod='named-card-photo-region', reviewStatus='approved')
        manifest['images'].append(item)
        covered.add(name)
    manifest['schemaVersion'] = 2
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    report = {'sourceRevision': tree['sha'], 'missing': missing, 'excluded': excluded}
    (ROOT / 'assets/profile-image-coverage.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Catalog contains {len(manifest["images"])} named images; {len(missing)} missing; {len(excluded)} non-miniature entries.')


if __name__ == '__main__':
    main()
