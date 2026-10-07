Steps:
- clone rhino3dm
- git submodule update --init --recursive for this repo
- Install Rhino 8 C++ SDK (https://developer.rhino3d.com/guides/cpp/installing-tools-windows/#install-the-rhino-cc-sdk)
- Make python 3.9 your "active" python
- Install CMake tools extension in Visual Studio Code. Adjust extension settings so it is visible in status bar
- Make sure installed cmake is at least version 3.24
- In VS Code, open rhino3dm/src/rhinocore_bindings directory
- In the status bar, change CMake to a release build
- In the status bar, click on the build button

If you're lucky and everything builds, you can open Rhino 8 and try running a script that looks like this
```
#! python 3
import sys
import os
import time
import Rhino

module_dir = os.path.abspath('C:\\dev\\github\\mcneel\\rhino3dm\\src\\rhinocore_bindings\\build\\Release\\')
sys.path.insert(0, module_dir)

import rhinocore_py_bindings as rb

start_time = time.time()

for i in range(1000000):
  pt = rb.Point3d(1,2,3)

end_time = time.time()

# Calculate the elapsed time
elapsed_time = end_time - start_time

print(f"The loop took {elapsed_time:.4f} seconds to complete.")
```
