FROM python:3.14-slim

# MCP Registry ownership proof: must equal the server.json "name" exactly.
LABEL io.modelcontextprotocol.server.name="io.github.mapsmith-ai/mapsmith"

# Geospatial wheels (pyogrio/shapely/pyproj) bundle their native libs; no system GDAL needed.
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
# raster + whitebox extras ship manylinux x86_64 wheels; the image is amd64-only.
RUN pip install --no-cache-dir ".[raster,whitebox]"

# Unprivileged by default (#19). uid 1000 on purpose rather than a high system
# uid: the supported way to run this is a bind mount of your own data directory,
# which on Linux is usually owned by the first human user — 1000. If yours is
# not, pass `--user $(id -u):$(id -g)`.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin mapsmith \
    && mkdir -p /data \
    && chown mapsmith:mapsmith /data

# The catalogue's embedding engine is the default, and its weights are a
# first-use download. Under a workspace MapSmith refuses that download -- this
# image sets MAPSMITH_WORKSPACE below, and SECURITY.md promises no egress in
# that mode -- so without the weights baked in every container would silently
# fall back to BM25. Fetched here, at the pinned revision the source names, and
# owned by the user that will read it.
ENV HF_HUB_DISABLE_TELEMETRY=1
ENV HF_HOME=/home/mapsmith/.cache/huggingface
RUN python -c "from mapsmith import retrieval; retrieval.warm_cache()"
RUN chown -R mapsmith:mapsmith /home/mapsmith/.cache

# The DuckDB `spatial` extension is a first-use download too, and the argument
# above applies to it word for word — it was simply missed. Without it baked in,
# the first `run_sql` in a container fetches about 15 MB, in the mode SECURITY.md
# describes as having no network egress; the install is excused there, but a
# confined deployment that needs the network to answer its first query is not
# what the promise leads a reader to expect. It also lands in `$HOME/.duckdb`,
# outside the declared workspace, on an ephemeral filesystem — so every container
# start paid for it again.
#
# `HOME` inline rather than as `ENV`: the extension directory is derived from it
# and there is no environment variable for it (checked — `extension_directory` is
# a SQL setting and defaults to `$HOME/.duckdb`), and moving the `ENV` up here
# would change what every later build step sees.
RUN HOME=/home/mapsmith python -c "\
import duckdb; c = duckdb.connect(); c.install_extension('spatial'); \
c.load_extension('spatial'); print('spatial baked in')" \
    && chown -R mapsmith:mapsmith /home/mapsmith/.duckdb

# Workspace for datasets: mount your data here. Confined BY DEFAULT — the
# supported path used to start unconfined unless the operator remembered `-e`,
# which is the wrong way round for a default.
VOLUME ["/data"]
WORKDIR /data
ENV MAPSMITH_WORKSPACE=/data \
    HOME=/home/mapsmith \
    MPLCONFIGDIR=/home/mapsmith/.config/matplotlib

USER mapsmith

ENTRYPOINT ["mapsmith"]
