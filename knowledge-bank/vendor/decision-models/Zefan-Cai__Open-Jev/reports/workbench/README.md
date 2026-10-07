# Open-Jev workbench deployment checks

The [online workbench](https://zefan-cai.github.io/open-jev/workbench/) lets users paste text or upload CSV, define categories, and download the original table with predictions. It calls the released Open-Jev-2B model in a [CPU Space](https://huggingface.co/spaces/ZefanCai/Open-Jev-Workbench).

[Validation evidence](validation.json) separates fixture-based UI/API checks from one real CPU deployment request, its rejected-input check, and a two-row CSV batch completed through the live browser UI. The CSV download preserved the original columns and actual probabilities; the live browser passed 12 checks. The real request completed in 17.21 seconds from the verification client; this is a single observation, not a latency benchmark or an accuracy estimate. Startup succeeded within CPU Basic, and CPU/GPU output parity remains untested. Existing published benchmark results are unchanged.

The public trial handles one request at a time. Start with a few short rows. For setup, limits and model pins, see the [user guide](../../docs/get-started.md) and [deployment files](../../deploy/huggingface-space/README.md).
