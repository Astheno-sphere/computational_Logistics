# Classify messages with Open-Jev, without writing code

For example, you might have a spreadsheet of 100 customer messages that you want to sort into “Refund,” “Product issue,” “How-to question,” and “Other.” The Open-Jev workbench lets you upload the spreadsheet, describe your categories, and download a CSV with classification results added. The hosted workbench only requires a browser.

[Classify online](https://huggingface.co/spaces/ZefanCai/Open-Jev-Workbench) · [Project website workbench](https://zefan-cai.github.io/open-jev/workbench/)

Defining your own categories means writing a short explanation for each one:

| Category name | Category description |
| --- | --- |
| Refund | Requests a return or refund, or asks about refund progress |
| Product issue | Reports a damaged product, software error, or a feature that does not work |
| How-to question | Asks about steps, features, or product information |
| Other | None of the categories applies, or there is not enough information to decide |

“I was charged twice. Please refund the extra payment” illustrates a refund case. This is only a workflow example; actual classifications come from the connected model.

## Using the workbench

1. Open the workbench and confirm that the page shows the inference service is ready.
2. Paste messages, one per line, or upload a CSV and choose the text column to classify. Each run accepts up to 200 rows, and CSV files must be no larger than 2 MB. You can save an Excel spreadsheet as UTF-8 CSV first.
3. Enter one category per line in the category box, using `Category name: Category description`. Chinese colons are also accepted. Include an “Other” or “Needs human review” category for messages that do not fit the existing categories.
4. Select “Start classification.” The workbench processes rows in order and shows progress, the selected category, and candidate probabilities. Failed requests show an error and are never replaced with preset answers.
5. Review the results, then select “Download results” to save the CSV. The export retains every original CSV column and adds classification results, ready for further work in Excel.

“Download task settings” saves only the category rules and categories. It does not include uploaded messages or classification results, so you can use it to save and share your rules.

You can enter the example categories directly as:

```text
Refund: Requests a return or refund, or asks about refund progress
Product issue: Reports a damaged product, software error, or a feature that does not work
How-to question: Asks about steps, features, or product information
Other: None of the categories applies, or there is not enough information to decide
```

The first version selects one category per text. It is suited to customer support messages, email routing, and organizing product feedback. You review and use the results after classification.

**Candidate probability is not accuracy.** It describes how the model distributes probability among the categories you provide. Try a few familiar messages to check your category rules before processing a full spreadsheet. Probabilities for new categories still need validation against your own labeled examples.

## Illustrative examples and real inference

The [workbench page](../examples/workbench/index.html) can open without a model. “Show an example” displays preset illustrative content to explain the workflow; it is not a model measurement and does not send your inputs to a model.

You can classify your own content once the page shows that the service is ready. The page reports when it is disconnected, when the model is still loading, or when a request fails.

The workbench does not store your data in browser storage or add analytics tracking. Imported spreadsheets and results are cleared when the page is refreshed. Starting classification sends the selected text and category rules to the current website’s model service.

## Use the hosted app or deploy your own

The public [Open-Jev Workbench](https://huggingface.co/spaces/ZefanCai/Open-Jev-Workbench) is live and has been verified with real classification requests. It uses the released 2B model on CPU. The hosted trial is slower, so start with a few messages and check that your categories work before processing more content.

The public service accepts 2–8 categories and up to 4,000 text characters per row, with a maximum full prompt of 1,024 tokens per candidate. It handles one request at a time and asks you to try later when busy.

The [project website workbench](https://zefan-cai.github.io/open-jev/workbench/) provides the interface and a link to the hosted service. Classification runs in the Hugging Face Space. To use your own machine or process internal business data, follow the deployment steps below.

## For deployers: start the workbench

The [deployment guide](deployment.md) provides the unified platform matrix and exact model pins.

The commands below use the existing **Linux + NVIDIA GPU** inference path and require Python 3.10+, a CUDA environment, and sufficient GPU memory. The deployer handles installation; end users only need a browser. Complete verification of installation in a fresh environment is still being improved.

Install from a Git checkout so the workbench files are included. The `train` dependency group also provides inference dependencies; installing it does not start training.

```bash
git clone https://github.com/Zefan-Cai/Open-Jev.git
cd Open-Jev
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[train]'

hf download ZefanCai/Open-Jev-2B \
  --revision 0c7aa498b1627be8da4acf34c863ff0ee0a92785 \
  --local-dir models/Open-Jev-2B

python -m jev.server \
  --checkpoint models/Open-Jev-2B/package/checkpoint \
  --device cuda:0 --max-length 4096 --batch-size 1 --no-prefix-cache \
  --host 127.0.0.1 --port 8791
```

The download contains the released 2B LoRA adapter, decision head, and configuration, not merged base-model weights. The Open-Jev loader loads `Qwen/Qwen3.5-2B` at the pinned revision `15852e8c16360a2fea060d615a32b45270f8a8fc`. The first run needs to download the base model unless it is already cached.

Once the model has loaded, open these URLs in a browser on the same machine:

- Workbench home: <http://127.0.0.1:8791/>
- Full workbench path: <http://127.0.0.1:8791/examples/workbench/index.html>
- Service status: <http://127.0.0.1:8791/health>

The server listens on `127.0.0.1` by default, with prefix caching disabled. This self-hosted command allows up to 4,096 tokens per candidate. Inputs over the limit cause an error; text is not truncated.

To share a self-hosted service with others, use an HTTPS reverse proxy to serve the workbench, `/health`, and `/v1/systemone` under the same website, and configure authentication. The local server has no account system of its own. See the [deployment guide](../deploy/huggingface-space/README.md) for the CPU Space configuration.

## Add it to your own project

An existing backend can use the [Python Client](../jev/client.py) for the same classification requests. See [request examples in the README](../README.md#try-it) for request examples. The browser workbench can be shared directly with people who need to organize spreadsheets.

The community [Docker deployment PR #1](https://github.com/Zefan-Cai/Open-Jev/pull/1) is merged. See the [deployment matrix](deployment.md) for Docker, NVIDIA, CPU, Apple Silicon MPS and the community 16GB 9B recipe. Future additions could include n8n and Dify connectors and more business templates. The first version focuses on a complete workflow: enter messages → define categories → review results → export a spreadsheet.
