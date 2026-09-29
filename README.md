# Middle Earth Compendium

A browsable MESBG army and profile reference with a draft warband roster builder.

## GitHub Pages

The complete static site lives in `dist/`. The workflow in `.github/workflows/pages.yml` publishes this folder when commits reach `main`. There is no build step or package installation.

After pushing the repository, open **Settings → Pages** and set **Build and deployment → Source** to **GitHub Actions**. The deployment will then be available at `https://<owner>.github.io/<repository>/` (or at the repository's Pages URL shown in Settings). You can run **Publish GitHub Pages** manually from the Actions tab if the first push preceded the Pages setting.

The site's HTML, CSS, JavaScript, profile data, and images are under `dist/`. The roster draft is stored in browser session storage.

## Miniature photos

All 548 miniature profiles have local photos, including shared photos for repeated character profiles. The two `No Hero` entries are roster placeholders and have no photo. New photos come from the [MESBG List Builder community repository](https://github.com/avcordaro/mesbg-list-builder-v2024); each expanded profile retains its source link. Most source images are small portraits, so they are displayed at thumbnail size rather than enlarged into banners.

`assets/profile-images.json` records sources, SHA-256 hashes, explicit identity matches, and any display crops. `assets/profile-image-aliases.json` maps differing character names, while `assets/profile-image-coverage.json` records missing images and intentional exclusions. Existing manually reviewed crops are preserved; bulk matches are labeled `identity-matched`, not manually approved. Source attribution does not establish reuse permission.

Run `python3 scripts/import-profile-images.py` to validate and reapply the manifest. Existing local files are reused; missing files are downloaded and checked against the recorded hashes. `--refresh` downloads every source again. To extend the catalog using an upstream GitHub ZIP and its matching recursive tree JSON, run `python3 scripts/catalog-profile-images.py SOURCE.zip TREE.json` first. The catalog checks Git blob hashes and refuses ambiguous matches. Image pixels are retained; Beorn's bear photo is displayed through a CSS crop of its source card.

This is an unofficial fan reference and is not affiliated with Games Workshop or Middle-earth Enterprises.

## Square tiles from the supplied PDF

`assets/pdf-profile-tiles.json` records the reviewed page regions in `MESBG-Armies-Of-Middle-Earth-2025.pdf`. It exports 128 square, 384 × 384 photo tiles for 137 profiles. The 411 profiles not illustrated in this supplemental book retain their previous photos; their names are listed in `assets/pdf-tile-coverage.json` for completion from other books. No missing background is invented for the older circular images.

With `pymupdf` and `Pillow` installed, run `python3 scripts/import-pdf-tiles.py` (or pass `--pdf /path/to/file.pdf`). The importer checks the PDF hash and exact profile names, exports only the selected miniature photos into `dist/images/pdf-tiles/`, and adds book/page credits. The source PDF is not copied into the published site. Re-running the community importer preserves the PDF tiles. Each tile also has a `portraitRect` head-and-shoulders crop, exported as a 160 × 160 `-face.jpg` and used for the list thumbnail, while the full tile stays as the profile photo.

`assets/lotr-pdf-profile-tiles.json` does the same for `MESBG Armies of The Lord of the Rings 2024.pdf`: 139 tiles for 168 profiles. Run `python3 scripts/import-pdf-tiles.py --manifest assets/lotr-pdf-profile-tiles.json`. Théoden keeps his existing white-background photo and face crop. Several profiles in this book (Beechbone, Helm Hammerhand, Héra, Olwyn, Lief, Fréaláf, the Uruk-hai Demolition Team, the Mûmaks and the Corsair Ballista) have no miniature photo in the book, so they keep their previous images. `Arnor & Angmar 2024.pdf` adds no new profiles: every profile it illustrates already has a 2025 tile.

The same importer also crops single photos: `assets/supplied-photo-tiles.json` (`"sourceType": "image"`, pixel rectangles) splits `assets/supplied-photos/mauhur-vrasku.png` into separate Mauhúr and Vraskû tiles. Run `python3 scripts/import-pdf-tiles.py --manifest assets/supplied-photo-tiles.json`.
