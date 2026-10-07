# LLM2Jev Web Demo

The web demo builds mixed `Choice`, `Score`, and `Noul` requests and visualizes
the response probabilities. It connects to the `/v1/systemone` endpoint exposed
by `llm2jev-serve`.

Start the model server:

```bash
llm2jev-serve \
  --model-path /path/to/model \
  --served-model-name local-model \
  --host 127.0.0.1 \
  --port 30000
```

In another terminal, start the demo server from the repository root:

```bash
python demos/web/server.py
```

Open <http://127.0.0.1:8000>. The demo server proxies browser requests to
`http://127.0.0.1:30000` by default. To use another endpoint or port:

```bash
python demos/web/server.py \
  --api-base http://127.0.0.1:31000 \
  --port 8080
```
