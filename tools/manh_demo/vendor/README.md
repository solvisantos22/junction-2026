# Vendored third-party code

- `SVGLoader.js`: three.js's SVG loader (`examples/jsm/loaders/SVGLoader.js`), release r187, the same release as
  `viewer/mars/vendor/three.module.js`. MIT licence, in `LICENSE-three.txt`. Used by `icons.js` to cut the labs'
  marks out of their SVG paths (`pages.svg_loader` makes it a function of the page's own THREE).
  To refresh it: `curl -LO https://cdn.jsdelivr.net/npm/three@0.187.0/examples/jsm/loaders/SVGLoader.js`.
