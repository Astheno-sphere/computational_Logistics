# Computational Design Tools Ecosystem

This reference provides comprehensive descriptions of every major tool in the computational design ecosystem for AEC, including capabilities, licensing, typical workflows, integration points, and community resources.

---

## 1. Rhino + Grasshopper Ecosystem

### McNeel Rhinoceros 3D

**Overview:** Rhinoceros (Rhino) is the de facto standard 3D modeling platform for computational design in architecture. Its mathematical precision (NURBS-based), open architecture, and the Grasshopper visual programming environment make it the central hub of most computational design workflows.

**Current Version:** Rhino 8 (released 2023)
**Licensing:** Commercial ($995 one-time), Educational ($195). No subscription required.
**Platforms:** Windows, macOS (Rhino 8), partial Linux support via Rhino.Inside

**Core Capabilities:**
- NURBS curve and surface modeling with full mathematical precision
- SubD (subdivision surface) modeling for organic forms (Rhino 7+)
- Mesh modeling and editing
- Rendering (built-in Cycles-based renderer in Rhino 7+)
- 2D drafting and layout (Layouts feature)
- Section cutting and make2D for documentation
- VisualARQ plugin for BIM capabilities within Rhino
- Built-in Python and C# scripting (RhinoScript, RhinoCommon API)
- Grasshopper fully integrated (Rhino 6+)

**Integration Points:**
- Rhino.Inside: Embeds Rhino/Grasshopper inside Revit, AutoCAD, Unity, Unreal, and other host applications
- Direct import/export: DWG, DXF, 3DM, OBJ, STL, FBX, IGES, STEP, 3DS, SKP, IFC (with plugins)
- Speckle connector for live data exchange
- RhinoCommon API for deep programmatic access

**Community Resources:**
- McNeel Forum (discourse.mcneel.com): Extremely active, direct developer engagement
- Food4Rhino (food4rhino.com): Plugin repository with 1000+ plugins
- Rhino Developer documentation and SDK
- Worldwide user groups and workshops

### Grasshopper

**Overview:** Grasshopper is the visual programming environment embedded in Rhino that has become the primary computational design tool in architecture worldwide. It enables parametric modeling, algorithmic design, optimization, analysis, and fabrication planning through a node-based interface where components are connected by wires to define data flow.

**Current Version:** Grasshopper 1 (integrated in Rhino 7/8); Grasshopper 2 in development
**Licensing:** Included with Rhino license
**Platform:** Windows (full support), macOS (Rhino 8)

**Core Capabilities:**
- Visual programming with 500+ built-in components
- Parametric geometry creation and manipulation
- Data tree management for complex hierarchical data
- GhPython and C# scripting components for custom logic
- Timer component for iterative/animated processes
- Cluster/User Object system for encapsulation and reuse
- Hops component for remote computation and function calls
- Native data types: points, vectors, planes, curves, surfaces, meshes, breps, numbers, text, colors, domains

**Key Built-in Components:**
- Params: Number Slider, Panel, Value List, Gene Pool
- Maths: Expressions, Functions, Trigonometry, Domains
- Sets: List operations, Tree operations, Dispatch, Sort
- Vector: Point, Vector, Plane, Field
- Curve: Line, Arc, Circle, Polyline, NURBS, Interpolate, Divide, Offset
- Surface: Extrude, Loft, Sweep, Boundary, Isotrim, Evaluate
- Mesh: Mesh from curves/surfaces, Deconstruct, Weld, Smooth
- Transform: Move, Rotate, Scale, Mirror, Orient, Morph
- Intersect: Curve-Curve, Curve-Surface, Brep-Brep, Region
- Display: Custom Preview, Color, Gradient

**Data Tree Architecture:** Grasshopper's data tree system is its most powerful and most challenging feature. Data is organized in branched hierarchical structures where each branch has a path address (e.g., {0;1;3}) and contains a list of items. Understanding grafting, flattening, simplifying, and path mapping is essential for effective use.

### Top Food4Rhino Plugins by Category

#### Geometry & Modeling
| Plugin | Description | Downloads |
|--------|-------------|-----------|
| **Weaverbird** | Mesh topology editing (subdivision, thickening, face operations) | Very High |
| **Pufferfish** | Tweens, blends, morphs between geometry types | High |
| **Lunchbox** | Paneling, space truss, surface patterns, data management | Very High |
| **Dendro** | Volume modeling using OpenVDB; organic forms, lattices | High |
| **Cocoon** | Isosurface modeling for organic structures | Medium |
| **Heteroptera** | Mesh operations, remeshing, relaxation | Medium |
| **MeshEdit** | Advanced mesh editing and repair | Medium |
| **Anemone** | Looping/iteration inside Grasshopper (workaround for recursive definitions) | High |
| **Parakeet** | Pattern generation, fractal geometry, tiling systems | High |
| **Peacock** | Jewelry-focused but excellent boolean and modeling operations | Medium |

#### Environmental Analysis
| Plugin | Description | Downloads |
|--------|-------------|-----------|
| **Ladybug Tools** | Weather data viz, sun path, radiation analysis, outdoor comfort | Very High |
| **Honeybee** | Energy modeling (E+), daylight (Radiance), HVAC | Very High |
| **Butterfly** | CFD (OpenFOAM wrapper) for wind analysis | High |
| **Dragonfly** | Urban-scale energy and microclimate modeling | Medium |
| **Eddy3D** | Real-time wind simulation and CFD | Medium |
| **ClimateStudio** | Commercial daylight/energy simulation (high quality) | Medium |

#### Structural Analysis
| Plugin | Description | Downloads |
|--------|-------------|-----------|
| **Karamba3D** | Interactive FEA for parametric structural design | High |
| **Kangaroo** | Physics engine: form-finding, dynamic relaxation, constraints | Very High (built-in Rhino 7+) |
| **Millipede** | Topology optimization, structural analysis | Medium |
| **Ameba** | Topology optimization for architecture | Medium |
| **Galapagos** | Evolutionary solver (built into Grasshopper) | Built-in |
| **Octopus** | Multi-objective evolutionary optimization | Medium |
| **Opossum** | RBF surrogate-model based optimization | Small |
| **Colibri** | Design space exploration and data export to Design Explorer | Medium |
| **Goat** | Optimization algorithms (BFGS, Nelder-Mead) | Small |

#### Fabrication & Robotics
| Plugin | Description | Downloads |
|--------|-------------|-----------|
| **HAL Robotics** | Industrial robot programming (ABB, KUKA, UR, Staubli) | Medium |
| **KUKA\|prc** | KUKA robot programming and simulation | Medium |
| **Robots** | Open-source multi-brand robot programming | Medium |
| **Silkworm** | Custom G-code generation for 3D printing | Small |
| **Elefront** | Baking management, attributes, block handling | High |
| **Human** | UI elements, attribute management, conditional display | High |

#### Data & Interoperability
| Plugin | Description | Downloads |
|--------|-------------|-----------|
| **Speckle** | Open-source data exchange to Revit, Unity, web, etc. | High (growing) |
| **Heron** | GIS data import (shapefiles, rasters, web maps) | Medium |
| **Elk** | OpenStreetMap data import and visualization | Medium |
| **TT Toolbox** | Data management, surface analysis, geometry utilities | High |
| **jSwan** | JSON serialization/deserialization | Medium |
| **Telepathy** | Live data exchange between Grasshopper instances | Small |
| **gHowl** | UDP/TCP communication, data streaming | Medium |
| **Taco** | IFC import/export for BIM interoperability | Small |

#### Visualization
| Plugin | Description | Downloads |
|--------|-------------|-----------|
| **Human UI** | Custom UI windows and dashboards in Grasshopper | High |
| **Design Explorer** | Web-based design space exploration (pairs with Colibri) | Medium |
| **Firefly** | Arduino/sensor integration, real-time data | Medium |
| **GH_CPython** | CPython integration for advanced ML/data libraries | Small |

---

## 2. Revit + Dynamo Ecosystem

### Autodesk Revit

**Overview:** Revit is the dominant BIM (Building Information Modeling) platform in architecture and structural engineering. While not natively a computational design tool, its integration with Dynamo and Rhino.Inside makes it an essential part of computational workflows — particularly for translating parametric designs into constructable, documented BIM models.

**Current Version:** Revit 2025
**Licensing:** Subscription ($2,975/year individual, $4,250/year with AEC Collection)
**Platform:** Windows only

**Core Capabilities:**
- Parametric family-based BIM modeling
- Multi-discipline coordination (architecture, structure, MEP)
- Construction documentation with automated schedules, sections, details
- Analytical energy modeling (Insight integration)
- Cloud rendering and collaboration (BIM 360 / Autodesk Construction Cloud)
- C# and Python API for automation
- Dynamo visual programming integration

**Integration with Computational Design:**
- Dynamo: Built-in visual programming for parametric BIM manipulation
- Rhino.Inside.Revit: Run Rhino and Grasshopper inside Revit for complex geometry creation directly in BIM
- Speckle connector: Live data exchange with Grasshopper, Blender, web
- IFC import/export for open BIM workflows
- gbXML export for energy analysis

### Dynamo

**Overview:** Dynamo is the visual programming environment for the Autodesk ecosystem, primarily used with Revit for BIM automation and parametric BIM element creation. While less extensive than Grasshopper for pure computational design, it excels at BIM manipulation, data management, and workflow automation within Revit.

**Current Version:** Dynamo 2.x (integrated in Revit), Dynamo Sandbox (standalone)
**Licensing:** Free (included with Revit, or standalone Sandbox version)
**Platform:** Windows

**Core Capabilities:**
- Visual programming with node-based interface
- Direct Revit element creation and modification
- Python scripting (IronPython 2.7, CPython 3)
- Excel and CSV data import/export
- List management and data manipulation
- Geometry creation and transformation (ProtoGeometry)
- Custom node packages via Package Manager

**Key Dynamo Packages:**
| Package | Description |
|---------|-------------|
| **archi-lab** | Revit API access, element manipulation, selection tools |
| **Clockwork** | Extensive utility nodes for Revit and general use |
| **Spring Nodes** | Geometry, dictionary, and UI utilities |
| **Rhythm** | Revit productivity tools, view management, annotations |
| **BimorphNodes** | CAD link interrogation, room/space data |
| **Data-Shapes** | Custom UI forms and input dialogs |
| **Lunchbox for Dynamo** | Paneling, math surfaces, data utilities |
| **DynaShape** | Physics-based form-finding (Kangaroo equivalent for Dynamo) |
| **Refinery** | Generative design optimization (Autodesk) |
| **Generative Design** | Multi-objective optimization within Revit |

---

## 3. Blender + Geometry Nodes / Sverchok

### Blender

**Overview:** Blender is a free, open-source 3D creation suite that has rapidly expanded into AEC visualization and increasingly into computational design. Its Geometry Nodes system (Blender 3.0+) provides procedural geometry capabilities comparable to Houdini, while Sverchok offers a Grasshopper-like parametric modeling experience.

**Current Version:** Blender 4.x (as of 2025)
**Licensing:** Free and open-source (GPL)
**Platform:** Windows, macOS, Linux

**Core Capabilities:**
- Polygon, NURBS, and curve modeling
- Sculpting and retopology
- Physically-based rendering (Cycles, EEVEE)
- Geometry Nodes (native procedural geometry system)
- Grease Pencil (2D animation in 3D space)
- Video editing and compositing
- Python API for complete automation
- Add-on ecosystem

**Geometry Nodes:** Blender's native procedural geometry system, introduced in Blender 3.0, provides a node-based interface for procedural modeling, scattering, instancing, and data processing. While designed for general 3D, it is increasingly used for architectural computational design due to Blender's free licensing and powerful rendering.

**Sverchok:** A Blender add-on that provides a visual programming environment specifically for parametric and generative design, similar in concept to Grasshopper. It offers nodes for NURBS, mesh, data management, and integration with external solvers. While less mature than Grasshopper's plugin ecosystem, it provides a viable free alternative.

**AEC-Relevant Add-ons:**
| Add-on | Description |
|--------|-------------|
| **BlenderBIM** | Full IFC authoring and viewing in Blender (IfcOpenShell-based) |
| **Sverchok** | Visual programming for parametric design |
| **Tissue** | Tessellation and generative modeling |
| **Archipack** | Parametric architectural elements (walls, floors, stairs) |
| **MeasureIt-ARCH** | Architectural dimensioning and annotation |
| **Sun Position** | Solar analysis and sun path simulation |
| **Speckle for Blender** | Live data exchange with other AEC platforms |

---

## 4. Houdini (SideFX)

### Overview

Houdini is the gold standard for procedural content creation, originally developed for VFX and now increasingly adopted in AEC for complex procedural modeling, large-scale urban generation, and simulation. Its node-based, non-destructive workflow and SOPs (Surface Operators) offer capabilities that exceed Grasshopper for certain procedural tasks.

**Current Version:** Houdini 20.x
**Licensing:** Houdini FX ($4,495/year), Houdini Core ($1,995/year), Houdini Indie ($269/year for < $100K revenue), Houdini Apprentice (free, non-commercial, watermarked)
**Platform:** Windows, macOS, Linux

**Core Capabilities:**
- Procedural geometry via SOPs (Surface Operators)
- VEX scripting language for per-element computation (extremely fast)
- Volume modeling and simulation (smoke, fire, fluid)
- Particle and dynamics simulation
- Terrain generation and erosion simulation
- Procedural urban modeling (buildings, streets, infrastructure)
- PDG (Procedural Dependency Graph) for pipeline automation
- USD (Universal Scene Description) support for large-scale scenes
- Python and VEX scripting

**AEC Relevance:**
- Large-scale procedural urban modeling (city generation, massing studies)
- Terrain and landscape generation with physically-based erosion
- Complex facade and structure generation with VEX
- Simulation (wind, water, pedestrian flow) at urban scale
- Pipeline automation for multi-tool workflows
- Game engine integration for real-time visualization (Unreal, Unity)

**Integration Points:**
- Houdini Engine: Embed Houdini procedural assets in Unity, Unreal, Maya, 3ds Max
- USD/GLTF/FBX export for downstream tools
- Python API for custom tool development
- SideFX Labs: Free tools including AEC-specific SOPs

---

## 5. Processing / p5.js

### Processing

**Overview:** Processing is an open-source creative coding environment and language (based on Java) designed for visual arts, computational design exploration, and teaching programming to designers. It excels at rapid prototyping of algorithmic design ideas, data visualization, and interactive simulations.

**Current Version:** Processing 4.x
**Licensing:** Free and open-source
**Platform:** Windows, macOS, Linux

**Core Capabilities:**
- 2D and 3D graphics rendering
- Interaction handling (mouse, keyboard, touch)
- Image and video processing
- Data loading and parsing (CSV, JSON, XML)
- PDF and SVG export for fabrication
- Extensive library ecosystem (physics, network, sound, etc.)
- Ideal for rapid prototyping and teaching

### p5.js

**Overview:** p5.js is the JavaScript port of Processing, running natively in web browsers. It enables computational design exploration, visualization, and interactive web-based design tools without any installation.

**Current Version:** p5.js 1.x
**Licensing:** Free and open-source
**Platform:** Any web browser

**AEC Relevance:**
- Rapid prototyping of algorithmic design ideas before implementing in Grasshopper/Dynamo
- Client-facing interactive design visualizations
- Teaching computational design thinking
- Data visualization dashboards for design analysis
- Generative art and pattern exploration

---

## 6. Unity / Unreal Engine for AEC Visualization

### Unity

**Overview:** Unity is a real-time 3D engine increasingly used in AEC for interactive visualization, VR/AR experiences, and real-time design review. Its C# scripting environment enables parametric, interactive architectural visualization and design exploration.

**Current Version:** Unity 6 / 2023.x LTS
**Licensing:** Free (Personal, < $100K revenue), Plus ($399/year), Pro ($1,800/year)
**Platform:** Windows, macOS, Linux (editor); deploys to 20+ platforms

**AEC Applications:**
- Real-time architectural visualization and walkthroughs
- VR design review (Meta Quest, HTC Vive, Apple Vision Pro)
- AR on-site construction visualization
- Interactive client presentations
- Digital twin visualization with IoT data
- Speckle connector for live Grasshopper/Revit data

### Unreal Engine

**Overview:** Unreal Engine offers the highest visual fidelity of any real-time engine and has made significant investments in AEC through Twinmotion integration and dedicated AEC features.

**Current Version:** Unreal Engine 5.x
**Licensing:** Free (5% royalty after $1M revenue; no royalty for non-game applications)
**Platform:** Windows, macOS (limited), Linux

**AEC Applications:**
- Photorealistic real-time visualization (Lumen, Nanite)
- Twinmotion integration for rapid viz from Revit/Rhino/SketchUp
- Virtual production and film-quality walkthroughs
- Large-scale urban visualization (city-scale real-time)
- Datasmith for BIM data import (Revit, Rhino, IFC)

---

## 7. OpenSCAD

**Overview:** OpenSCAD is a programmer's 3D CAD modeler — all geometry is defined through code (a domain-specific language based on CSG operations), making it ideal for precision mechanical parts, mathematical geometry, and users who prefer coding over GUI modeling.

**Current Version:** OpenSCAD 2021.01 (stable), development snapshots ongoing
**Licensing:** Free and open-source (GPL)
**Platform:** Windows, macOS, Linux

**Core Capabilities:**
- CSG (Constructive Solid Geometry) modeling through code
- Parametric design through variables and functions
- Module system for reusable components
- STL/DXF/SVG export for fabrication
- Animation and customizer interface for parameter exploration
- Fast preview rendering

**AEC Relevance:** Limited to small-scale components, connectors, and fabrication jigs. Not suitable for building-scale design. Useful for 3D printing custom architectural hardware, parametric joinery, and teaching CSG concepts.

---

## 8. FreeCAD

**Overview:** FreeCAD is an open-source parametric 3D modeler with growing BIM capabilities through its BIM Workbench (formerly Arch Workbench). It provides an open alternative to commercial BIM tools with Python scripting and IFC support.

**Current Version:** FreeCAD 0.21+ (1.0 in development)
**Licensing:** Free and open-source (LGPL)
**Platform:** Windows, macOS, Linux

**Core Capabilities:**
- Parametric solid modeling (Part, PartDesign workbenches)
- BIM Workbench for architectural modeling and IFC export
- FEM Workbench for structural finite element analysis
- Path Workbench for CNC toolpath generation
- Python scripting and macro system
- IFC import/export via IfcOpenShell

**AEC Relevance:** Viable open-source alternative for firms seeking to avoid commercial BIM licensing costs. IFC support makes it interoperable with Revit and ArchiCAD projects. Python scripting enables computational design workflows, though the plugin ecosystem is far smaller than Rhino/Grasshopper.

---

## 9. Emerging Tools

### Speckle

**Overview:** Speckle is an open-source platform for AEC data exchange, collaboration, and automation. It provides connectors for Grasshopper, Rhino, Revit, Dynamo, Blender, Unity, Unreal, AutoCAD, Excel, and Power BI, enabling live, versioned, and filtered data exchange between any combination of tools.

**Key Capabilities:**
- Live data streaming between platforms (Grasshopper definition updates → Revit model updates in real time)
- Version control for 3D data (commit, branch, diff)
- Granular data filtering (send only specific element types)
- Web viewer for model review without any software installation
- Automation pipelines (triggers, actions) for CI/CD-like workflows for design
- GraphQL API for custom integrations
- Self-hosting option for data sovereignty

**Why It Matters:** Speckle solves the interoperability problem that has plagued AEC for decades. Rather than exporting/importing files (with data loss at every step), Speckle streams structured data objects directly between tools, preserving semantic information. For computational designers, this means a Grasshopper parametric model can drive a Revit BIM model with live, automated updates.

**Licensing:** Free and open-source (server and connectors); Speckle offers managed hosting plans for teams
**Platform:** Cross-platform (web-based server, native connectors for each tool)

### Hypar

**Overview:** Hypar is a cloud-based generative design platform that enables architects and engineers to create parametric building design functions that run in the browser. It emphasizes open standards (IFC), version-controlled logic, and collaborative design.

**Key Capabilities:**
- Cloud-based parametric functions (no local software required)
- C# function authoring with Hypar SDK
- IFC and glTF output
- Composable design workflows (chain multiple functions)
- Real-time 3D visualization in browser

**AEC Relevance:** Represents a potential future where computational design runs in the cloud, is composable, and is accessible without installing Rhino or Revit. Early stage but conceptually significant.

### TestFit

**Overview:** TestFit (acquired by Autodesk) is a real-time feasibility study tool for multifamily and mixed-use real estate development. It uses algorithmic design to instantly generate and evaluate building configurations based on site constraints, unit mix, parking requirements, and financial metrics.

**Key Capabilities:**
- Real-time building configuration from site outline and program
- Instant unit count, parking, financial pro forma
- Multiple massing and layout options in seconds
- Integration with Revit for downstream BIM development
- AI-assisted layout optimization

**AEC Relevance:** Demonstrates the commercial viability of computational design for real estate feasibility — a use case where speed (minutes, not weeks) creates direct financial value.

### Autodesk Forma (formerly Spacemaker)

**Overview:** Forma is Autodesk's cloud-based conceptual design platform for early-stage architecture and urban design. It provides real-time analysis of sun, wind, daylight, noise, and microclimate, enabling performance-driven massing design without specialized simulation expertise.

**Key Capabilities:**
- Real-time solar, wind, daylight, and noise analysis
- AI-predicted wind comfort (trained on CFD simulations)
- Terrain and context modeling from GIS data
- Massing design with instant performance feedback
- Collaboration features for stakeholder engagement
- API for integration with custom tools

**AEC Relevance:** Represents the industrialization of performance-driven design — making environmental analysis accessible to non-specialists in the earliest design stages. Competes with Ladybug Tools for mindshare but targets a different user (generalist architect vs. computational specialist).

---

## 10. Scripting Languages and Frameworks

### Python for AEC

**Key Libraries:**
| Library | Use in AEC |
|---------|------------|
| **rhinoscriptsyntax** | Rhino scripting within GhPython |
| **RhinoCommon** | Full Rhino geometry API (.NET, accessed via Python) |
| **compas** | Computational framework for AEC (ETHZ BRG) |
| **compas_fea** | Finite element analysis within COMPAS |
| **compas_fab** | Robotic fabrication planning within COMPAS |
| **IfcOpenShell** | IFC file reading, writing, and manipulation |
| **topologicpy** | Topological modeling library |
| **shapely** | 2D computational geometry |
| **trimesh** | 3D mesh processing |
| **numpy / scipy** | Numerical computation, optimization, linear algebra |
| **pandas** | Data manipulation and analysis |
| **matplotlib** | Plotting and visualization |
| **scikit-learn** | Machine learning (classification, regression, clustering) |
| **tensorflow / pytorch** | Deep learning for generative design, image recognition |
| **ladybug / honeybee** | Environmental simulation (Python core libraries) |
| **specklepy** | Speckle API client for Python |

### C# for AEC

**Key Frameworks:**
| Framework | Use |
|-----------|-----|
| **RhinoCommon** | Rhino geometry and plugin development |
| **Grasshopper SDK** | Custom Grasshopper component development |
| **Revit API** | Revit automation and plugin development |
| **Dynamo ZeroTouch** | Custom Dynamo nodes from C# libraries |
| **Hypar SDK** | Cloud-based generative design functions |
| **xBIM** | IFC processing and BIM development |

### Other Languages

| Language | AEC Use |
|----------|---------|
| **VEX (Houdini)** | Per-element computation in Houdini SOPs |
| **Rust** | High-performance geometry kernels, emerging in AEC tools |
| **TypeScript/JavaScript** | Web-based viewers (three.js, IFC.js), Speckle frontend |
| **Julia** | Scientific computing, emerging in structural optimization research |
| **R** | Statistical analysis of building performance data |

---

## 11. COMPAS Framework

**Overview:** COMPAS (Computational Framework for Research in Architecture and Structures) is an open-source Python framework developed by the Block Research Group at ETH Zurich. It provides a comprehensive set of tools for computational design research, spanning geometry processing, structural analysis, robotic fabrication, and data management.

**Key Packages:**
| Package | Description |
|---------|-------------|
| **compas** | Core: geometry, data structures, numerical methods, visualization |
| **compas_rhino** | Rhino/Grasshopper integration |
| **compas_blender** | Blender integration |
| **compas_fea / compas_fea2** | Finite element analysis interface |
| **compas_fab** | Robotic fabrication planning (MoveIt integration) |
| **compas_tna** | Thrust Network Analysis for funicular structures |
| **compas_ags** | Algebraic graphic statics |
| **compas_3gs** | 3D graphic statics |
| **compas_assembly** | Discrete element assembly planning |
| **compas_timber** | Timber structure modeling and fabrication |
| **compas_slicer** | 3D printing slicing and toolpath generation |
| **compas_view2** | Stand-alone 3D visualization |
| **compas_singular** | Singularity-aware quad mesh generation |
| **compas_cgal** | CGAL computational geometry bindings |

**Why COMPAS Matters:** COMPAS provides a unified computational environment for AEC research that works across platforms (Rhino, Blender, standalone Python). It is the most comprehensive open-source computational design framework available, backed by world-class research at ETH Zurich and an active community of researchers worldwide.

---

## 12. Simulation Engines (Backend)

These are the simulation engines that power the analysis plugins listed in the SKILL.md. Understanding what runs "under the hood" is important for interpreting results and troubleshooting.

| Engine | Domain | Used By |
|--------|--------|---------|
| **EnergyPlus** | Building energy simulation | Honeybee, DesignBuilder, OpenStudio |
| **Radiance** | Physically-based lighting simulation | Honeybee, ClimateStudio, DIVA |
| **OpenFOAM** | Computational fluid dynamics | Butterfly, various research tools |
| **OpenStudio** | Building energy modeling framework | Honeybee, standalone |
| **CalculiX** | Open-source FEA solver | COMPAS FEA, various research tools |
| **Abaqus** | Commercial FEA solver | Research, COMPAS FEA interface |
| **SAP2000 / ETABS** | Commercial structural analysis | Practice-standard structural tools |
| **ANSYS** | Multi-physics simulation suite | Structural, thermal, fluid simulation |
| **COMSOL** | Multi-physics simulation | Research-focused coupled simulation |
| **Radiance (3-phase/5-phase)** | Advanced daylight simulation methods | ClimateStudio, Honeybee |

---

## 13. Version Control and Collaboration

| Tool | Description | AEC Relevance |
|------|-------------|---------------|
| **Git** | Distributed version control | Track changes to scripts, Grasshopper XML, Dynamo JSON |
| **GitHub / GitLab** | Cloud-hosted Git repositories | Share computational design definitions, collaborate on code |
| **Speckle** | AEC-specific data versioning | Version control for 3D geometry and BIM data |
| **BIM 360 / ACC** | Autodesk cloud collaboration | Revit model hosting, issue tracking |
| **BIMcollab** | BCF-based issue management | Cross-platform BIM coordination |
| **Notion / Confluence** | Documentation | Computational design process documentation |

---

## 14. Hardware Considerations

### Workstation Recommendations for Computational Design

| Component | Minimum | Recommended | Heavy Simulation |
|-----------|---------|-------------|------------------|
| **CPU** | 8-core (Intel i7 / AMD Ryzen 7) | 16-core (i9 / Ryzen 9 / Threadripper) | 32+ core (Threadripper PRO) |
| **RAM** | 32 GB | 64 GB | 128-256 GB |
| **GPU** | NVIDIA RTX 3060 (12 GB) | NVIDIA RTX 4080 (16 GB) | NVIDIA RTX 4090 or A6000 |
| **Storage** | 1 TB NVMe SSD | 2 TB NVMe SSD + HDD | 4+ TB NVMe SSD RAID |
| **Display** | 2560x1440 | 3840x2160 (4K) dual | Triple 4K or ultra-wide |

**Key Notes:**
- Grasshopper is largely single-threaded; high single-core clock speed matters more than core count for GH definitions
- Simulation (EnergyPlus, Radiance, OpenFOAM) benefits from many cores
- GPU matters for rendering (Cycles, Vray), real-time visualization (Unity/Unreal), and ML training
- RAM is critical for large meshes, point clouds, and complex BIM models

---

*This reference is maintained as a living document and updated as the tools ecosystem evolves.*
