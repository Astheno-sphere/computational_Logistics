# Fresh base-package installation and API validation

A new macOS venv built and installed a wheel without optional model dependencies. Tests ran outside the source checkout. Nine API tests, both declared console help entrypoints and loopback HTTP with an explicitly named synthetic scorer passed. No base weights or model inference were loaded. The jev.predict module requires the optional Torch runtime even for help; it is not a base-package console entrypoint. This is not Linux CUDA or full-size MPS validation. See report.json and individual logs.
