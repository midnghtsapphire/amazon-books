# web/

KDP Packaging Studio — the whole pipeline's packaging stage, running entirely
in the browser. Built static bundle (React + TypeScript + Vite); open
`index.html` or serve the folder. Auto-deployed to GitHub Pages by
`.github/workflows/pages.yml`.

| Surface | Purpose |
| --- | --- |
| Live press-sheet preview | Wraparound cover with bleed/spine/barcode rulers, recomputed per keystroke |
| Grok/Imagine handoff | Copies the exact cover prompt for grok.com/imagine; upload the result back |
| One-click package | Print cover PDF (300 DPI), preview PNG, ebook front JPG, `kdp_answers.json`, single ZIP |

Client-side only by design: no keys, no server, nothing leaves the device.
