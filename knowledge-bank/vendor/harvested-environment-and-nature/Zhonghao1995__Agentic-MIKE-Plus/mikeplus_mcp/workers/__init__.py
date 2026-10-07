"""Worker scripts — run as standalone subprocesses, never imported by the server.

Hard rule: each worker imports EITHER mikeplus OR mikeio*/matplotlib, never both
in the same file. run/model/params/scenario/import workers use mikeplus (need a
MIKE+ license); results/plot/rain workers use mikeio1d/mikeio (no license needed).
"""
