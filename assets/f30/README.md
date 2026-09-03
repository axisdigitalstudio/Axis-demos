# Photographs — 2012 BMW 3 Series (F30)

`bmw-f30-showcase.html` reads every frame it shows from this directory. Until a
file lands here the matching beat renders a slot on screen naming the exact path
it is waiting for, so the page never invents a car it does not have a photo of.

## Files the page asks for

| File | Beat | What the frame wants to show |
|---|---|---|
| `01-reveal.jpg` | 00 · Reveal | Front three-quarter, whole car, room around it — the title sits over the left third |
| `02-engine-bay.jpg` | 01 · Engine | Bonnet open, looking down into the bay |
| `03-interior.jpg` | 02 · Interior | Across the dashboard, freestanding display in frame |
| `04-chassis.jpg` | 03 · Chassis | Front wheel and brake, strut visible if possible |
| `05-load-bay.jpg` | 04 · Load bay | Boot open from behind |
| `06-lineup.jpg` | 05 · Line-up | Clean profile or three-quarter |
| `07-exit.jpg` | 06 · Archive | Rear three-quarter, the closing frame |

Landscape, and large — these are shown full-bleed, so 2400px on the long edge or
more. JPEG or WebP both work; change the extension in the manifest to match.

## Optional extras

- `02-engine-bay-n55.jpg` — swapped in when the 335i's straight-six is selected.
- `06-lineup-320i.jpg`, `06-lineup-328i.jpg`, `06-lineup-335i.jpg` — one per car,
  swapped by the line-up selector. Without them all three fall back to `06-lineup.jpg`.
- `turntable/` — a numbered sequence shot on one axis. List the files in the
  `lineup.frames` array in the manifest and scroll scrubs the sequence frame by
  frame instead of running the push-in. 24–36 frames is plenty.

## Tuning a frame

Everything lives in the `PHOTOS` manifest at the foot of `bmw-f30-showcase.html`:

- `focus [x,y]` — percent; the point the crop holds on and the push-in aims at.
  Set this to the car, not the centre of the file, or a tall viewport will crop
  it off.
- `zoom [a,b]` — scale at the start and end of the beat.
- `pan [x,y]` — percent of the viewport the frame drifts across the beat.
- `pins` — callouts. `u` and `v` are 0–1 **across the photograph itself**, not
  the screen, so a pin stays on the part it labels at any crop or viewport. The
  defaults in the file are placeholders positioned for a generic shot — move them
  once the real photographs are in.

Set `CREDIT` in the same block to whoever took the photographs and it appears
bottom-right over the stage.
