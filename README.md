# Middle Earth Compendium

A browsable MESBG army and profile reference with a draft warband roster builder.

## GitHub Pages

The complete static site lives in `dist/`. The workflow in `.github/workflows/pages.yml` publishes this folder when commits reach `main`. There is no build step or package installation.

After pushing the repository, open **Settings → Pages** and set **Build and deployment → Source** to **GitHub Actions**. The deployment will then be available at `https://<owner>.github.io/<repository>/` (or at the repository's Pages URL shown in Settings). You can run **Publish GitHub Pages** manually from the Actions tab if the first push preceded the Pages setting.

The site's HTML, CSS, JavaScript, profile data, and images are under `dist/`. The roster draft is stored in browser session storage.

This is an unofficial fan reference and is not affiliated with Games Workshop or Middle-earth Enterprises.
