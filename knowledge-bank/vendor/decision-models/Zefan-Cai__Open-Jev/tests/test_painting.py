import copy
from pathlib import Path
import shutil
import subprocess
import unittest

from jev.api import candidate_prompts, compile_request
from jev.data import validate_records
from jev.painting import (MODES, PALETTE, build_requests, geometry_answers,
                          geometry_records, geometry_scene, render_rgb)
from jev.serving import Predictor


class PaintingTest(unittest.TestCase):
    def test_coordinates_survive_id_removal_and_batching(self):
        batches = build_requests("A red square", "hsl", 8, batch_questions=5)
        self.assertTrue(all(len(batch["questions"]) <= 5 for batch in batches))
        records = [record for batch in batches for record in compile_request(batch["state"], batch["questions"])]
        self.assertEqual(len(records), 8 * 8 * 3)
        self.assertEqual(len({r["id"] for r in records}), len(records))
        item = records[-1]
        original = candidate_prompts(item)
        item["id"] = "not_a_coordinate"
        self.assertEqual(candidate_prompts(item), original)
        self.assertIn("pixel x=7, y=7", original[0])

    def test_procedural_targets_reconstruct_exact_images_in_all_modes(self):
        for index in range(12):
            scene = geometry_scene(index)
            for mode in MODES:
                with self.subTest(index=index, mode=mode):
                    actual = render_rgb(geometry_answers(scene, mode), mode, scene["size"])
                    expected = ([[0, 0, 0] if value else [255, 255, 255] for value in scene["mask"]]
                                if mode == "silhouette" else [PALETTE[color] for color in scene["colors"]])
                    self.assertEqual(actual, expected)

    def test_probabilities_are_rendered_as_a_mean_not_argmax(self):
        scene = geometry_scene(1)
        answers = geometry_answers(scene, "palette")
        answers["x0_y0"]["probabilities"] = {name: 0.5 if name in ("red", "blue") else 0 for name in PALETTE}
        self.assertEqual(render_rgb(answers, "palette", scene["size"])[0], [128, 0, 128])

    def test_bad_model_outputs_are_rejected(self):
        scene = geometry_scene(1)
        good = geometry_answers(scene, "palette")
        for replacement in ({"type": "choice", "probabilities": {"red": 1}},
                            {"type": "noul", "noul": 0.2},
                            {"type": "choice", "probabilities": {name: 1 for name in PALETTE}},
                            {"type": "choice", "probabilities": {name: float("nan") for name in PALETTE}}):
            answers = copy.deepcopy(good)
            answers["x0_y0"] = replacement
            with self.assertRaises(ValueError):
                render_rgb(answers, "palette", scene["size"])
        good.pop("x0_y0")
        with self.assertRaises(ValueError):
            render_rgb(good, "palette", scene["size"])

    def test_data_have_valid_targets_and_scene_splits(self):
        rows = list(geometry_records(12))
        validate_records(rows)
        grouped = {}
        for row in rows:
            grouped.setdefault(row["group_id"], set()).add(row["split"])
        self.assertTrue(all(len(splits) == 1 for splits in grouped.values()))
        self.assertIn("ood", {row["split"] for row in rows})
        self.assertEqual(rows, list(geometry_records(12)))

    def test_invalid_limits_fail_before_allocation(self):
        for args in (("a", "video", 8), ("a", "rgb", 10000), ("", "rgb", 8), ("a", "rgb", True)):
            with self.assertRaises(ValueError):
                build_requests(*args)
        with self.assertRaises(ValueError):
            build_requests("a", batch_questions=0)

    def test_all_painting_modes_pass_bounded_server_predictor(self):
        class ExplicitUniformTestScorer:
            def __init__(self):
                self.largest = 0

            def score(self, records):
                count = sum(1 if r["kind"] == "noul" else len(r["options"]) for r in records)
                self.largest = max(self.largest, count)
                return [[0.0] * (2 if r["kind"] == "noul" else len(r["options"])) for r in records], count

        scorer = ExplicitUniformTestScorer()
        predictor = Predictor(scorer, model_name="explicit_test_scorer", batch_size=3)
        for mode in MODES:
            answers = {}
            for request in build_requests("A circle", mode, size=2, batch_questions=5):
                answers.update(predictor.predict(request)["answers"])
            pixels = render_rgb(answers, mode, 2)
            self.assertEqual(len(pixels), 4)
            self.assertTrue(all(pixel == pixels[0] for pixel in pixels))
        self.assertLessEqual(scorer.largest, 3)

    @unittest.skipUnless(shutil.which("node"), "requires Node for browser-script regression")
    def test_ui_keeps_one_endpoint_per_run(self):
        script = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const fixture = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const elements = new Map();
const document = {getElementById(id) {
  if (!elements.has(id)) elements.set(id, {value: '', disabled: false, textContent: ''});
  return elements.get(id);
}};
const $ = id => document.getElementById(id);
$('canvas').getContext = () => ({
  createImageData: (width, height) => ({data: new Uint8ClampedArray(width * height * 4)}),
  putImageData: () => {},
});
const posts = [];
let releaseFirst;
const response = request => ({ok: true, json: async () => ({
  model: 'protocol-fixture-no-model',
  answers: Object.fromEntries(Object.keys(request.questions).map(key => [key, fixture.answers.rgb[key]])),
})});
const fetch = async (url, options) => {
  if (!options) return {ok: true, json: async () => fixture};
  const request = JSON.parse(options.body);
  posts.push({url, request});
  if (posts.length === 1) return new Promise(resolve => { releaseFirst = () => resolve(response(request)); });
  return response(request);
};
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
await new AsyncFunction('document', 'fetch', 'location', await fs.readFile(process.argv[1], 'utf8'))(
  document, fetch, {origin: 'http://protocol-fixture.invalid'});
$('mode').value = 'rgb';
$('size').value = '8';
$('prompt').value = 'Protocol fixture; no model quality claim';
$('model').value = 'open-jev';
const original = $('endpoint').value;
const changed = 'http://different-fixture.invalid/v1/systemone';
const run = $('run').onclick();
assert.equal(posts.length, 1);
$('endpoint').value = changed;
releaseFirst();
await run;
assert.equal(posts.length, 3);
assert.deepEqual(posts.map(post => post.url), [original, original, original]);
assert.equal($('source').textContent, 'MODEL PREDICTION');
assert.equal($('run').disabled, false);
await $('run').onclick();
assert.deepEqual(posts.slice(3).map(post => post.url), [changed, changed, changed]);
assert.equal($('source').textContent, 'MODEL PREDICTION');
"""
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which("node"), "--input-type=module", "-e", script,
             str(root / "examples/painting/app.mjs"), str(root / "examples/painting/reference.json")],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
