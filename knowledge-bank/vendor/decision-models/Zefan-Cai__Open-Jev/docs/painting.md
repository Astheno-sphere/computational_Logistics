# Probability painting

[jev-paint](https://github.com/achimala/jev-paint) (formerly `achimala/jevinci`)
turns pixel decisions into artwork. This project implements the four decision
representations independently. Our renderer displays the mean color of each
pixel. It does not reproduce the upstream impasto/stroke renderer.

| Mode | Questions at each pixel | Rendering |
| --- | --- | --- |
| Palette | One Choice over 16 named colors | Probability-weighted RGB |
| Silhouette | One Noul for foreground membership | Black foreground, white background |
| RGB | Three Noul questions, one per binary channel | 255 × channel probability |
| HSL | Hue Choice, saturation Score, lightness Score | Mean RGB under the product of the three marginals |

HSL channels are assumed independent by rendering code. The returned marginals
are not a learned joint distribution. A pleasing image is not evidence that the
probabilities are calibrated.

## Run

Open `examples/painting/index.html` from the local server's `/examples/painting/index.html` route,
or serve the repository with `python -m http.server 8789 --bind 127.0.0.1` and
visit `http://127.0.0.1:8789/examples/painting/` for the offline renderer only.
Loading the procedural reference works offline after the files are served. It
displays **reference data**, not a model prediction. For model inference, use
the inference server's own `/examples/painting/index.html` route and its
same-origin endpoint. The default inference server rejects cross-origin calls.

```python
from jev.painting import build_requests, render_rgb

requests = build_requests("A small red sailboat on blue water", mode="palette", size=8)
# Send each request to POST /v1/systemone; merge the returned answers.
# pixels = render_rgb(answers, "palette", 8)
```

The prompt and global coordinates are shared across batches. Pixel coordinates
appear in each question's instructions, since question IDs do not enter the
model. At 8×8, palette and silhouette require 64 questions; RGB and HSL need 192.
Each Choice/Score candidate uses a separate backbone input in the current
backend. Begin with a small silhouette; no interactive latency is promised.

## Data and validation

```sh
python -m jev.painting --groups 60 --seed 42 --output-dir data/painting-geometry-v1
python -m jev.data validate data/painting-geometry-v1
python -m unittest discover -s tests -p 'test_painting.py'
```

The recorded release corpus uses the 60-group request and seed 42 above; other
settings produce a different dataset. Its [manifest](../reports/data-manifests/painting.json)
records the actual retained scene/row counts and split hashes.
A local [CPU rebuild](../reports/runtime-checks/painting-release-rebuild-20260920.json)
reproduced all five split hashes and the native manifest without changing the
original corpus.
The generator creates exactly labelled, solid-color rectangles and circles.
Every pixel and representation from an identical scene stays in the same split.
Circles on a larger grid are held out as OOD; rectangles use group-hash splits.
Targets are programmatically computed from integer coordinates, with no model
teacher or copied Jev outputs. Generated records are CC0-1.0.

Tests reconstruct exact scene RGB through all four representations, reject
malformed probability distributions, and validate grouped data. These checks
establish the adapter/data contract. They do **not** establish that an Open-Jev
checkpoint can paint coherent free-form prompts; that requires model evaluation.

## Attribution

Concept reference: Anshu Chimala's MIT-licensed `jev-paint`, inspected at commit
`ecf9c48d290e086bde790d6e24b93324667155e9`, especially
[`web/jev.mjs`](https://github.com/achimala/jev-paint/blob/ecf9c48d290e086bde790d6e24b93324667155e9/web/jev.mjs).
No upstream source, recorded model probabilities, or paint textures are included
in this implementation. The four modes follow the public task formulation;
the palette values, prompts, procedural scenes, browser, and renderer are ours.
