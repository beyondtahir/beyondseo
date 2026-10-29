# Paperworks scene sources

Three editable ten-second scenes make up a silent thirty-second master:

- `workshop`: inspect, write and connect inside the paper SEO house.
- `compare`: inspect two equivalent pages before recording a comparison.
- `links`: bring a connection toward the website and outside page.

`assets/stage.png`, `assets/comparison.png` and `assets/poses.png` are original artwork.
The integrated hero still lives one directory above. Do not replace the empty stage
with the populated hero: that would duplicate the characters.

From this directory, with Node.js, Chrome and FFmpeg available:

```sh
npm install --no-save gsap@3.14.2
node -e 'require("fs").copyFileSync("node_modules/gsap/dist/gsap.min.js", "assets/gsap.min.js")'
npx hyperframes@0.8.217 check --json
npx hyperframes@0.8.217 preview --background
npx hyperframes@0.8.217 render --quality looks --output paperworks-master.mp4
```

Review the actual preview and snapshots after editing. Scene positions use a 1920×960
canvas. Pose changes, small movements and contact shadows are separately editable.
The sprite masks deliberately exclude adjacent poses in the original atlas.

The README GIFs are ten-second cuts, exported at 10 fps and 1,000 pixels wide with a
128-colour palette. Phone crops are 1,280 pixels wide: workshop starts at x=0; links
starts at x=480 and excludes the bottom caption before scaling to 640 pixels. Native
README copy identifies the illustrations and supplies accessible descriptions.

The separately installed GSAP 3.14.2 runtime retains its upstream notices and separate licence.
It is an artwork dependency, not part of the SEO engine or a required installation step.

`opening.html` is the separate, static README header composition. Its two sections
keep the artwork left and the text right on desktop, then stack on phones. Capture
the `#desktop` and `#mobile` elements as PNGs to rebuild the responsive header images.
The existing logo and illustration are referenced unchanged; this file does not run
SEO tasks or create a public website.
