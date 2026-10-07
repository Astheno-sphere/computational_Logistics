---
title: BIM Scripting
description: Revit API fundamentals, Dynamo for Revit, pyRevit framework, IFC schema and openBIM, model checking, automated documentation, clash detection, and BIM interoperability tools for AEC computational design
version: 1.0.0
tags: [BIM, Revit, Dynamo, pyRevit, IFC, openBIM, model-checking, automation, clash-detection, Speckle, BHoM]
auto_activate: true
user_invocable: true
invocation: /bim-scripting
---

# BIM Scripting

Comprehensive reference for automating Building Information Modeling workflows
through scripting, API access, and interoperability platforms. This skill covers
the full spectrum of BIM automation --- from visual programming with Dynamo
through deep Revit API scripting, pyRevit extension development, IFC/openBIM
data exchange, model checking, automated documentation, and cross-platform
interoperability via Speckle, BHoM, and Rhino.Inside.Revit.

---

## 1. BIM Automation Philosophy

### Why Script BIM

BIM models are databases disguised as 3D geometry. Every wall, door, room, and
duct segment carries structured data --- type, dimensions, material, cost code,
fire rating, acoustic class, phase, workset, design option. Manual manipulation
of that data does not scale. A 200-unit residential project may contain 40,000+
elements, each with 30--80 parameters. Changing a naming convention, verifying
parameter completeness, or exporting coordinated drawing sets by hand is not
just slow --- it is error-prone and unrepeatable.

Scripting BIM means treating the model as a programmable data source:

- **Read** element properties at scale (audit, validate, report).
- **Write** parameter values in batch (standards enforcement, data enrichment).
- **Create** elements procedurally (repetitive layouts, adaptive placement).
- **Transform** geometry computationally (facade panelization, structural optimization).
- **Export** deliverables automatically (sheets to PDF, models to IFC, data to dashboards).

### Manual vs. Automated BIM Workflows

| Workflow | Manual Approach | Automated Approach | Time Savings |
|---|---|---|---|
| Parameter QA | Open each element, check value | Script scans all elements, flags violations | 95% |
| Sheet creation | Place views, adjust crops, add tags one by one | Script generates sheets from template rules | 90% |
| Clash detection | Visual inspection in section views | Navisworks / script-based interference check | 85% |
| Export to IFC | File > Export > IFC, configure, repeat per model | Batch script exports all linked models with preset mappings | 80% |
| Room finish schedule | Manual schedule, manual formatting | API-generated schedule with conditional formatting | 75% |
| Design option comparison | Duplicate views, switch options, compare | Script generates comparison report with metrics | 90% |
| Naming convention enforcement | Manual review of browser tree | FilteredElementCollector + regex validation | 98% |

### ROI of BIM Automation

The return on investment for BIM scripting follows a clear pattern:

1. **First script** --- 2-8 hours to develop, saves 1-4 hours per use. Break-even after 2-3 uses.
2. **Script library** (20-50 tools) --- 200-500 hours to develop, saves 10-30 hours per project. Break-even within 1-2 projects.
3. **Custom application** --- 500-2000 hours to develop, saves 50-200 hours per project. Break-even within 3-5 projects.
4. **Enterprise platform** --- 2000-10,000 hours to develop, transforms entire practice workflow.

### The Automation Spectrum

```
Level 1: Visual Programming (Dynamo, Grasshopper)
  - Lowest barrier to entry
  - Best for designers who think visually
  - Limited scalability and version control
  - Good for: one-off design explorations, parameter mapping, geometry generation

Level 2: Scripting (Python in Dynamo, pyRevit, RevitPythonShell)
  - Moderate barrier to entry
  - Full API access with Python convenience
  - Version-controllable, shareable
  - Good for: batch operations, custom tools, data workflows

Level 3: Custom Tools (C# add-ins, pyRevit extensions)
  - Higher barrier to entry
  - Compiled performance, custom UI, ribbon integration
  - Deployable to teams
  - Good for: production tools, firm-wide standards enforcement

Level 4: Full Applications (standalone apps, web dashboards, microservices)
  - Highest barrier to entry
  - Complete control over UX and data pipeline
  - Cloud-scalable, multi-user
  - Good for: enterprise BIM management, cross-project analytics
```

### When to Automate vs. When to Model Manually

Automate when:
- The task repeats across projects or phases.
- The task involves more than 50 elements.
- Consistency and auditability are critical (QA/QC, code compliance).
- The output feeds downstream processes (cost, energy, structural analysis).
- Human error risk is high (naming, classification, spatial containment).

Model manually when:
- The task is a one-time creative act (early concept massing).
- Judgment and spatial intuition outweigh procedural logic.
- The element count is small and the rules are ambiguous.
- The cost of developing automation exceeds the cost of manual work.

### BIM Maturity Levels and Automation

| BIM Level | Description | Automation Role |
|---|---|---|
| Level 0 | 2D CAD, no BIM | CAD scripting (AutoLISP, VBA) for drawing automation |
| Level 1 | 3D modeling, 2D documentation | Basic Dynamo scripts, parameter management |
| Level 2 | Federated models, structured data exchange | IFC workflows, clash detection, model checking |
| Level 3 | Integrated single model, full lifecycle data | API-driven analytics, real-time dashboards, AI-assisted QA |
| Level 4 (emerging) | Digital twin, IoT-connected, predictive | Continuous model sync, ML-driven optimization, autonomous agents |

---

## 2. Revit API Fundamentals

### Architecture

The Revit API is a .NET framework (C# or VB.NET natively, Python via IronPython
or CPython with RevitPythonShell/pyRevit). The object hierarchy:

```
UIApplication
  └── Application           (Revit application-level settings, version info)
       └── Document          (the .rvt file; model database)
            ├── Elements      (everything in the model)
            ├── Views         (plans, sections, 3D views, schedules)
            ├── Phases        (existing, new construction, demolition)
            ├── DesignOptions  (option sets and options)
            ├── Worksets       (worksharing partitions)
            └── Settings       (project units, line styles, fill patterns)
```

### Element Types

Every object in a Revit model inherits from `Element`. Key subclasses:

| Class | Description | Example |
|---|---|---|
| `FamilyInstance` | Placed instance of a loadable family | Door, window, furniture, fixture |
| `Wall` | System family: wall element | Basic Wall, Curtain Wall, Stacked Wall |
| `Floor` | System family: floor slab | Generic Floor, composite assemblies |
| `Roof` | System family: roof element | Basic Roof, extrusion roof |
| `Ceiling` | System family: ceiling element | Compound ceiling, basic ceiling |
| `FamilyInstance` (structural) | Columns, beams, braces | Steel W-shapes, concrete columns |
| `Room` | Spatial element for architectural spaces | Bounded by room-bounding elements |
| `Area` | Spatial element for area plans | Gross area, rentable area |
| `View` | Any view in the model | `ViewPlan`, `ViewSection`, `View3D`, `ViewSheet` |
| `ViewSheet` | A sheet for documentation | Contains viewport placements |
| `ViewSchedule` | A schedule/quantity takeoff | Tabular data extraction |
| `Group` | Grouped elements | Model groups, detail groups |
| `Level` | Datum: horizontal reference plane | Defines story heights |
| `Grid` | Datum: vertical reference plane | Structural grid lines |
| `ReferencePlane` | Construction plane | Alignment references |

### Categories, Families, Types, Instances

This four-level hierarchy is central to Revit:

```
Category        (e.g., Doors)
  └── Family      (e.g., Single-Flush)
       └── Type     (e.g., 36" x 84")
            └── Instance  (placed door #1, #2, #3...)
```

- **Category**: broad classification (Walls, Doors, Floors, Furniture). Each has a `BuiltInCategory` enum.
- **Family**: a parametric definition (.rfa file for loadable families; system families are built-in).
- **Type**: a named set of parameter values within a family (dimensions, materials).
- **Instance**: a placed occurrence with instance-specific parameters (location, room, mark).

### Parameters

Parameters store all non-geometric data on elements.

| Parameter Kind | Scope | Definition | Access |
|---|---|---|---|
| Built-in | Hardcoded by Revit | Predefined (e.g., `WALL_BASE_OFFSET`) | `element.get_Parameter(BuiltInParameter.WALL_BASE_OFFSET)` |
| Project | One project file | Defined in Project Parameters dialog | `element.LookupParameter("MyParam")` |
| Shared | Across projects/families | Defined in Shared Parameters file (.txt) | `element.get_Parameter(guid)` or by name |
| Family | Inside .rfa family | Defined in Family Editor | Exposed as type or instance parameter |
| Global | Project-wide value | Not element-bound; referenced by formulas | `GlobalParametersManager` |

Parameter storage types:
- `StorageType.String` --- text
- `StorageType.Integer` --- integers and YesNo (0/1)
- `StorageType.Double` --- real numbers (always in internal units)
- `StorageType.ElementId` --- reference to another element (material, type, level)

### Transactions

Every model modification must occur inside a `Transaction`. Without it, the API
throws an `InvalidOperationException`.

```python
# Python (pyRevit / RevitPythonShell)
from Autodesk.Revit.DB import Transaction

doc = __revit__.ActiveUIDocument.Document
t = Transaction(doc, "Batch Update Parameters")
t.Start()

try:
    # ... modify elements ...
    t.Commit()
except Exception as e:
    t.RollBack()
    print("Error: {}".format(e))
```

Transaction types:
- **Transaction** --- standard single transaction (most common).
- **TransactionGroup** --- wraps multiple transactions; can assimilate (merge into one undo) or roll back all.
- **SubTransaction** --- nested within a Transaction; can roll back independently without aborting the parent.

### FilteredElementCollector

The primary mechanism for querying elements in a Revit model. It operates as a
builder pattern with filters:

```python
from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory,
    ElementCategoryFilter, ElementClassFilter
)

# All walls in the model
walls = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .WhereElementIsNotElementType() \
    .ToElements()

# All door types (not instances)
door_types = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Doors) \
    .WhereElementIsElementType() \
    .ToElements()

# All family instances of a specific class
instances = FilteredElementCollector(doc) \
    .OfClass(FamilyInstance) \
    .ToElements()

# Elements in a specific view
view_elements = FilteredElementCollector(doc, view.Id) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .ToElements()
```

### Geometry Access

Extracting geometry from Revit elements:

```
Element
  └── get_Geometry(Options)
       └── GeometryElement (iterable)
            ├── Solid
            │    ├── Faces (FaceArray)
            │    │    └── Face → Surface, UV domain, normal
            │    └── Edges (EdgeArray)
            │         └── Edge → Curve
            ├── GeometryInstance (for family instances)
            │    └── GetInstanceGeometry() → GeometryElement
            ├── Curve (for line-based elements)
            ├── Point
            └── PolyLine
```

### Units

Revit internal units are **always**:
- Length: **feet**
- Angle: **radians**
- Area: **square feet**
- Volume: **cubic feet**

Use `UnitUtils.ConvertFromInternalUnits()` and `UnitUtils.ConvertToInternalUnits()`
for conversion. In Revit 2022+, use `UnitTypeId` instead of `DisplayUnitType`.

### Events

The Revit API provides application and document-level events:
- `Application.DocumentOpened` / `DocumentClosing` / `DocumentSaved`
- `Application.ViewActivated`
- `Application.DialogBoxShowing` (intercept and auto-dismiss dialogs)
- `Document.DocumentChanged` (react to element modifications)
- `UIApplication.Idling` (periodic background processing)

### External Commands, Applications, Events

| Type | Purpose | Lifecycle |
|---|---|---|
| `IExternalCommand` | Single button click action | Runs once per invocation |
| `IExternalApplication` | Ribbon tab/panel setup, startup logic | Runs at Revit startup/shutdown |
| `IExternalDBApplication` | DB-level (no UI) startup logic | For services, updaters |
| `IExternalEventHandler` | Thread-safe model modification from external threads | Raised via `ExternalEvent` |

### C# vs. Python for Revit API

| Criterion | C# | Python (IronPython/CPython) |
|---|---|---|
| Performance | Compiled; fastest | Interpreted; slower for large loops |
| Debugging | Full Visual Studio debugger | Print statements, limited debugger |
| Deployment | DLL add-in; requires compilation | Script file; instant edit-run cycle |
| Learning curve | Steeper (typed language, project setup) | Gentler (dynamic typing, REPL) |
| API coverage | 100% | 100% (same .NET API via clr) |
| Ecosystem | NuGet packages, .NET libraries | Python packages (limited in IronPython) |
| UI creation | WPF, WinForms with full designer | WPF possible but harder; rpw simplifies |
| Best for | Production add-ins, enterprise tools | Rapid prototyping, small utilities, pyRevit |

---

## 3. Dynamo for Revit

### Core Advantages

Dynamo is a visual programming environment integrated with Revit (ships with
Revit since 2017). Key strengths:

- **Visual dataflow** --- nodes connected by wires; intuitive for non-programmers.
- **Live Revit connection** --- read/write model elements in real time.
- **Geometry preview** --- 3D preview of computational geometry before committing to Revit.
- **Extensibility** --- custom nodes in Python, C#, or DesignScript; package manager ecosystem.

### Revit-Specific Nodes

Dynamo provides dedicated Revit node categories:

- **Selection**: Select Model Element, Select Elements by Category, All Elements of Category
- **Create**: Wall.ByCurveAndHeight, Floor.ByOutlineTypeAndLevel, FamilyInstance.ByPoint
- **Modify**: Element.SetParameterByName, Element.MoveByVector, Element.OverrideColorInView
- **Query**: Element.GetParameterValueByName, Element.BoundingBox, Room.Boundaries

### Dynamo Player

Dynamo Player exposes Dynamo scripts as simple button-click tools for end users
who do not need to understand the graph. Configure inputs as user-facing
prompts. Best practice: design scripts specifically for Player with clear input
labels and minimal required interaction.

### Geometry Kernels

Dynamo uses **two separate geometry engines**:

1. **DesignScript / ASM (Autodesk Shape Manager)** --- Dynamo's native geometry kernel.
   Creates Points, Curves, Surfaces, Solids in Dynamo's 3D preview.
2. **Revit geometry** --- the actual BIM model geometry.

These are **not interchangeable**. A Dynamo `Surface` is not a Revit `Face`.
Converting between them requires explicit nodes:
- `Surface.ByPatch` (Dynamo) vs. `FaceWall.Create` (Revit)
- `Curve.ByPoints` (Dynamo) vs. `ModelCurve.ByCurve` (Revit)

### Common Revit Workflows in Dynamo

1. **Room-based floor finish placement** --- query room boundaries, offset curves, create floor elements by outline.
2. **Adaptive component placement** --- distribute families along curves or surfaces with parameter-driven spacing.
3. **Parameter read/write** --- bulk read element parameters to Excel, modify, write back.
4. **View creation** --- generate scope boxes, create dependent views per scope box, apply view templates.
5. **Sheet setup** --- create sheets from list, place viewports at coordinates, populate titleblock parameters.
6. **Keynote management** --- read keynote table, validate against model, update keynote parameters.
7. **Area analysis** --- extract room areas, calculate ratios (net-to-gross, circulation percentage), color-code by metric.

### Essential Packages

| Package | Author | Key Capabilities |
|---|---|---|
| Clockwork | Andreas Dieckmann | 500+ utility nodes; view manipulation, element filtering, string operations |
| Rhythm | John Pierson | Revit-focused; sheet management, view manipulation, element creation |
| archi-lab | Konrad Sobon | View/sheet automation, element selection, Revit API wrappers |
| spring nodes | Dimitar Venkov | Geometry, mesh processing, FEM analysis integration |
| BimorphNodes | Bimorph | Geometry, CAD import, mesh to solid conversion |
| Genius Loci | Alban de Chasteigner | Site tools, topography, Revit element manipulation |
| Data-Shapes | Mostafa El Ayoubi | Custom UI nodes (forms, dropdowns, file pickers) |
| Orchid | Erik Falck Jorgensen | Document management, family loading, workset operations |
| LunchBox | Nathan Miller | Paneling, geometric patterns, data management |

### Python Scripting in Dynamo

Python nodes in Dynamo provide full Revit API access:

```python
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')

from Autodesk.Revit.DB import *
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument

# Start transaction
TransactionManager.Instance.EnsureInTransaction(doc)

# ... API operations ...

TransactionManager.Instance.TransactionTaskDone()
```

Key differences from standalone pyRevit scripts:
- Use `TransactionManager` instead of raw `Transaction`.
- Use `DocumentManager.Instance.CurrentDBDocument` instead of `__revit__`.
- Inputs come from `IN[0], IN[1], ...`; output goes to `OUT`.

### Performance Considerations

Dynamo becomes slow when:
- Graphs exceed 200-300 nodes.
- Lists contain 10,000+ items with geometry preview on.
- Multiple levels of `List.Map` or `List@Level` create combinatorial explosions.

Alternatives when Dynamo is too slow:
- Move heavy logic into a single Python node (avoids inter-node marshalling).
- Use pyRevit for batch operations without geometry preview overhead.
- Use compiled C# add-in for maximum performance.
- Use Dynamo's `Passthrough` node to sequence operations and avoid unnecessary recalculation.

---

## 4. pyRevit Framework

### Architecture

pyRevit is a rapid application development framework for Revit. It creates
ribbon UI elements from a folder structure:

```
MyExtension.extension/
  ├── MyTab.tab/
  │    ├── MyPanel.panel/
  │    │    ├── MyButton.pushbutton/
  │    │    │    ├── script.py          (IronPython script)
  │    │    │    ├── icon.png           (16x16, 24x24, or 32x32)
  │    │    │    └── bundle.yaml        (tooltip, author, help URL)
  │    │    ├── MySplitButton.splitbutton/
  │    │    │    ├── Option1.pushbutton/
  │    │    │    └── Option2.pushbutton/
  │    │    └── MyPullDown.pulldown/
  │    │         ├── Item1.pushbutton/
  │    │         └── Item2.pushbutton/
  │    └── AnotherPanel.panel/
  └── lib/                             (shared Python modules)
       └── my_utils.py
```

### Script Types

- **IronPython (.py)** --- default; runs in Revit's IronPython engine. Access to .NET via `clr`.
- **CPython (.py with `#! python3`)** --- runs in CPython 3.x. Access to pip packages (pandas, numpy). Cannot access UI elements directly.
- **C# (.cs)** --- compiled at runtime. Full performance and type safety.

### pyRevit CLI

```bash
# Install pyRevit
pyrevit install

# Clone an extension from GitHub
pyrevit extend ui MyExtension https://github.com/user/repo.git

# List installed extensions
pyrevit extensions list

# Attach to a Revit version
pyrevit attach 2024 latest

# Enable/disable extensions
pyrevit extensions enable MyExtension
pyrevit extensions disable MyExtension

# Clear caches
pyrevit caches clear --all
```

### Built-in Tools Reference

pyRevit ships with dozens of production-ready tools:

- **Select** --- select all instances of a type, select by parameter value, select linked elements.
- **Match** --- match type properties, match graphic overrides between elements.
- **Keynotes** --- keynote manager with live editing and project keynote file management.
- **Sheets** --- batch create sheets, renumber sheets, print sheet sets.
- **Views** --- batch create views, set view templates, manage scope boxes.
- **Project** --- project parameter manager, shared parameter loader.
- **Toggles** --- quick toggles for halftone, crop regions, annotations.

### Creating Custom Extensions

Minimum viable pyRevit button:

```python
# script.py
"""Tooltip text shown on hover."""

__title__ = "My Button"
__author__ = "Your Name"

from pyrevit import revit, DB, forms

doc = revit.doc

# Get all rooms
rooms = DB.FilteredElementCollector(doc) \
    .OfCategory(DB.BuiltInCategory.OST_Rooms) \
    .WhereElementIsNotElementType() \
    .ToElements()

# Filter rooms with no number
unnamed = [r for r in rooms if not r.get_Parameter(
    DB.BuiltInParameter.ROOM_NUMBER).AsString()]

if unnamed:
    forms.alert("{} rooms have no number assigned.".format(len(unnamed)))
else:
    forms.alert("All rooms are numbered.", title="QA Check Passed")
```

### Transaction Handling in pyRevit

pyRevit provides a context manager for transactions:

```python
from pyrevit import revit, DB

with revit.Transaction("Update Room Names"):
    for room in rooms:
        param = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME)
        current = param.AsString()
        param.Set(current.upper())
```

### RevitPythonShell

An interactive Python REPL inside Revit. Useful for:
- Exploring the API interactively (inspect elements, test queries).
- Quick one-off operations without creating a full pyRevit script.
- Debugging: inspect element properties, test FilteredElementCollector queries.

### Template Scripts

**Batch parameter update:**
```python
from pyrevit import revit, DB, forms

doc = revit.doc
walls = DB.FilteredElementCollector(doc) \
    .OfCategory(DB.BuiltInCategory.OST_Walls) \
    .WhereElementIsNotElementType() \
    .ToElements()

with revit.Transaction("Set Wall Comments"):
    for wall in walls:
        wall.LookupParameter("Comments").Set("Reviewed")
```

**View creation from room list:**
```python
from pyrevit import revit, DB

doc = revit.doc
rooms = DB.FilteredElementCollector(doc) \
    .OfCategory(DB.BuiltInCategory.OST_Rooms) \
    .WhereElementIsNotElementType() \
    .ToElements()

level = rooms[0].Level
vft = doc.GetDefaultElementTypeId(DB.ElementTypeGroup.ViewTypeFloorPlan)

with revit.Transaction("Create Room Views"):
    for room in rooms:
        name = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString()
        view = DB.ViewPlan.Create(doc, vft, level.Id)
        view.Name = "Room - {}".format(name)
```

### Deployment

- **Shared extension path**: configure in pyRevit settings to point to a network share.
  All team members load extensions from the same location.
- **Version control**: store extensions in Git. Use CI/CD to deploy to the shared path.
- **pyRevit CLI** can install extensions from Git repositories directly.

### pyRevit Hooks

pyRevit supports event hooks via specially named scripts:

- `doc-changed-[hookid].py` --- fires when the document changes.
- `doc-opened-[hookid].py` --- fires when a document is opened.
- `doc-saved-[hookid].py` --- fires after a document is saved.
- `app-init-[hookid].py` --- fires when Revit starts (before any document).

Hooks live in a `hooks/` folder within the extension.

---

## 5. IFC & openBIM

### IFC Schema Overview

IFC (Industry Foundation Classes) is an ISO-standard (ISO 16739) open data
schema for BIM data exchange. Major versions:

| Version | Status | Key Additions |
|---|---|---|
| IFC2x3 | Legacy, widely supported | Most common in practice; 650+ entities |
| IFC4 | Current standard (ISO 16739-1:2018) | Improved geometry, new MEP entities, 4D/5D support |
| IFC4.3 | Released 2024 | Infrastructure: roads, bridges, rail, tunnels, ports |

### Key IFC Entities

```
IfcProject
  └── IfcSite
       └── IfcBuilding
            └── IfcBuildingStorey
                 ├── IfcWall / IfcWallStandardCase
                 ├── IfcSlab
                 ├── IfcBeam
                 ├── IfcColumn
                 ├── IfcDoor
                 ├── IfcWindow
                 ├── IfcSpace (equivalent of Revit Room)
                 ├── IfcCurtainWall
                 ├── IfcStair / IfcStairFlight
                 ├── IfcRamp / IfcRampFlight
                 ├── IfcRailing
                 ├── IfcRoof
                 ├── IfcCovering (finishes, ceilings)
                 ├── IfcFurnishingElement
                 └── IfcDistributionElement (MEP)
                      ├── IfcFlowSegment (pipes, ducts)
                      ├── IfcFlowTerminal (fixtures, diffusers)
                      └── IfcFlowFitting (elbows, tees)
```

### Property Sets and Quantity Sets

IFC data is carried in standardized property sets (Psets) and quantity sets (Qtos):

- **Pset_WallCommon**: Reference, Status, IsExternal, ThermalTransmittance, FireRating, AcousticRating
- **Pset_SlabCommon**: Reference, Status, IsExternal, LoadBearing, AcousticRating
- **Pset_DoorCommon**: Reference, FireRating, IsExternal, SecurityRating, HandicapAccessible
- **Pset_SpaceCommon**: Reference, IsExternal, GrossPlannedArea, NetPlannedArea, PubliclyAccessible
- **Qto_WallBaseQuantities**: Length, Width, Height, GrossVolume, NetVolume, GrossSideArea, NetSideArea
- **Qto_SlabBaseQuantities**: Width, Length, Depth, Perimeter, GrossArea, NetArea, GrossVolume, NetVolume

### IFC Export Settings in Revit

Critical export configuration:
- **IFC version**: IFC2x3 Coordination View 2.0 (most compatible) or IFC4 Reference View.
- **Export mapping table**: `IFC export classes` in Revit maps categories to IFC entities.
- **Property set mapping**: custom `.txt` mapping file for project-specific Psets.
- **Phase**: export only the relevant phase.
- **Base point**: shared coordinates for model federation.
- **Element selection**: current view vs. entire model.

### MVD (Model View Definition)

MVDs define subsets of the IFC schema for specific use cases:

| MVD | Purpose | Use Case |
|---|---|---|
| Coordination View 2.0 | Geometry + basic properties | Multi-discipline coordination |
| Design Transfer View | Rich geometry + full properties | Model handover between authoring tools |
| Reference View | Lightweight reference geometry | Lightweight context for coordination |
| Quantity Takeoff View | Properties + quantities | Cost estimation data exchange |

### BCF (BIM Collaboration Format)

BCF (ISO 21597) is a structured format for communicating issues in BIM:
- **BCF XML**: file-based (.bcfzip). Contains viewpoints (camera position, component visibility), comments, and issue metadata.
- **BCF API**: REST API for real-time issue sync between platforms.
- **Workflow**: reviewer opens federated model, creates BCF issue with snapshot, assigns to responsible party, tracks resolution.

### IFC Tools

| Tool | Language | Capabilities |
|---|---|---|
| IfcOpenShell | Python/C++ | Read/write/validate IFC; geometry processing; most mature open-source |
| IFC.js | JavaScript | Web-based IFC viewer/parser; WebGL rendering |
| xBIM | C# (.NET) | Read/write IFC; geometry meshing; WPF viewer |
| BIMserver | Java | Model server; IFC storage; version control; plugin architecture |
| Solibri | Desktop app | Model checking; clash detection; rule-based validation |
| BIMcollab | Web/Desktop | BCF management; cloud collaboration; issue tracking |
| BlenderBIM | Python | Full IFC authoring in Blender; IfcOpenShell-based |

### openBIM Coordination Workflow

```
Architect (Revit) ──export IFC──> Coordination Platform
Structural (Tekla) ──export IFC──>     (Solibri, BIMcollab,
MEP (Revit MEP) ──export IFC──>        Navisworks, or custom)
                                            │
                                    Federated Model
                                            │
                              ┌─────────────┼─────────────┐
                        Clash Detection   QA/QC       4D Planning
                              │             │             │
                         BCF Issues    Validation    Schedule Link
                              │          Report           │
                        ──BCF──> Author fixes ──re-export──>
```

---

## 6. Model Checking & Validation

### Rule-Based Checking

Model checking verifies that a BIM model meets predefined rules. Categories:

1. **Data completeness** --- required parameters are filled.
2. **Naming conventions** --- element names follow organizational standards.
3. **Spatial containment** --- elements are properly hosted on levels/rooms.
4. **Classification compliance** --- elements have correct Uniclass/OmniClass codes.
5. **Geometric validity** --- no zero-thickness walls, no overlapping elements.
6. **Design standards** --- minimum room sizes, maximum corridor lengths, accessibility clearances.

### Clash Detection Types

| Type | Description | Tolerance | Example |
|---|---|---|---|
| Hard clash | Physical intersection of elements | 0 mm | Duct passing through beam |
| Soft clash (clearance) | Insufficient clearance | Variable (50-300 mm typical) | Pipe too close to electrical cable tray |
| Workflow clash (4D) | Time-based conflict | Schedule overlap | Two trades occupying same zone simultaneously |
| Duplicate | Same element modeled twice | Position tolerance | Two identical walls overlapping |

### Navisworks Clash Detection Setup

1. **Append** all models (Revit NWC, IFC, DWG).
2. **Create selection sets** by discipline (Arch, Struct, MEP), system, or zone.
3. **Configure clash tests**: set A vs. set B, tolerance, clash type.
4. **Apply rules**: ignore clashes between connected elements, within same system, or by specific parameter match.
5. **Group results** by grid intersection, level, or element type.
6. **Generate report**: HTML, XML, or BCF for distribution.

### Custom Model Checking with Revit API

```python
from pyrevit import revit, DB, forms, output

doc = revit.doc
out = output.get_output()

# Check: All rooms must have a number and name
rooms = DB.FilteredElementCollector(doc) \
    .OfCategory(DB.BuiltInCategory.OST_Rooms) \
    .WhereElementIsNotElementType() \
    .ToElements()

issues = []
for room in rooms:
    number = room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).AsString()
    name = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString()
    area = room.get_Parameter(DB.BuiltInParameter.ROOM_AREA).AsDouble()

    if not number:
        issues.append(("Room {} has no number".format(room.Id), room.Id))
    if not name:
        issues.append(("Room {} has no name".format(room.Id), room.Id))
    if area == 0:
        issues.append(("Room {} is not bounded (0 area)".format(room.Id), room.Id))

out.print_md("## Room QA Report")
out.print_md("**Total rooms**: {}".format(len(rooms)))
out.print_md("**Issues found**: {}".format(len(issues)))
for msg, eid in issues:
    out.print_md("- {} [Click to select](revit://select?eid={})".format(msg, eid))
```

### LOD/LOI Verification

BIM Execution Plans specify required Level of Development (LOD) and Level of
Information (LOI) at each project stage. Automated verification:

- **LOD 100**: massing volumes present; check that IfcBuildingElementProxy exists.
- **LOD 200**: approximate geometry; check that elements have correct category but allow generic types.
- **LOD 300**: precise geometry; verify element dimensions match design intent; all parameters from EIR filled.
- **LOD 350**: coordination geometry; verify connections between disciplines; MEP clearances maintained.
- **LOD 400**: fabrication-ready; verify manufacturer data, part numbers, installation instructions.

### IFC Validation with IfcOpenShell

```python
import ifcopenshell
import ifcopenshell.validate

model = ifcopenshell.open("model.ifc")

# Schema validation
logger = ifcopenshell.validate.json_logger()
ifcopenshell.validate.validate(model, logger)

for error in logger.statements:
    print(error)

# Custom validation: all walls must have Pset_WallCommon
for wall in model.by_type("IfcWall"):
    psets = ifcopenshell.util.element.get_psets(wall)
    if "Pset_WallCommon" not in psets:
        print(f"Wall #{wall.id()} missing Pset_WallCommon")
```

---

## 7. Automated Documentation

### View Creation Automation

Programmatic view generation eliminates the tedious manual setup of project
views. Common patterns:

- **Floor plans per level** --- create architectural, structural, MEP, and fire safety plans for every level.
- **Dependent views per scope box** --- subdivide large floor plates into manageable sheets.
- **Sections at every grid intersection** --- structural section cuts for detailing.
- **Enlarged plans per room** --- interior elevations and enlarged plans keyed to room boundaries.
- **3D views per zone** --- isometric views for coordination reviews.

### Sheet Layout Automation

```python
from pyrevit import revit, DB

doc = revit.doc

# Get titleblock type
tb_type = DB.FilteredElementCollector(doc) \
    .OfCategory(DB.BuiltInCategory.OST_TitleBlocks) \
    .WhereElementIsElementType() \
    .FirstElement()

# Get all floor plan views
views = DB.FilteredElementCollector(doc) \
    .OfClass(DB.ViewPlan) \
    .WhereElementIsNotElementType() \
    .ToElements()

with revit.Transaction("Create Sheets"):
    for i, view in enumerate(views):
        if view.IsTemplate or view.Name.startswith("{"):
            continue
        # Create sheet
        sheet = DB.ViewSheet.Create(doc, tb_type.Id)
        sheet.SheetNumber = "A{:03d}".format(i + 1)
        sheet.Name = view.Name

        # Place viewport at center of sheet
        center = DB.XYZ(1.375, 0.875, 0)  # center of A1 sheet in feet
        DB.Viewport.Create(doc, sheet.Id, view.Id, center)
```

### Tag and Annotation Automation

- **Room tags**: iterate rooms, place `IndependentTag` at room location point.
- **Door tags**: iterate doors, place tag at door midpoint with leader if needed.
- **Dimension strings**: create `Dimension` objects along gridlines or wall faces.
- **Keynotes**: assign keynote values to elements, place keynote tags in views.

### Export Automation

```python
from pyrevit import revit, DB

doc = revit.doc

# Batch PDF export (Revit 2022+)
sheets = DB.FilteredElementCollector(doc) \
    .OfClass(DB.ViewSheet) \
    .ToElements()

pdf_options = DB.PDFExportOptions()
pdf_options.FileName = "ExportedSheets"
pdf_options.Combine = False  # separate PDF per sheet
pdf_options.PaperFormat = DB.ExportPaperFormat.Default
pdf_options.ZoomType = DB.ZoomType.FitToPage

sheet_ids = [s.Id for s in sheets if s.CanBePrinted]
doc.Export("C:/Output/", sheet_ids, pdf_options)
```

### Drawing List Management

Automate the drawing list schedule:
- Ensure all sheets have correct sheet number, name, revision, status.
- Generate a `ViewSchedule` of sheets via API with required fields.
- Export drawing list to Excel for transmittals.
- Validate sheet numbering against organizational standard (e.g., `A-101`, `S-201`, `M-301`).

---

## 8. BIM Interoperability Platforms

### Speckle

Speckle is an open-source data platform for AEC that treats 3D model data as
versionable, streamable, and queryable:

- **Connectors**: Revit, Rhino, Grasshopper, Blender, AutoCAD, Civil3D, Unity, Unreal, Excel, Power BI, QGIS.
- **Streams**: persistent data channels. Push model data to a stream; any connected app can receive it.
- **Commits**: every push creates a versioned commit. Full history, branching, diffing.
- **Web viewer**: browser-based 3D viewer with filtering, measurement, section cuts.
- **GraphQL API**: programmatic access to all data. Query elements, filter by properties.
- **Speckle Automate**: serverless functions triggered on new commits. Use for automated QA/QC, data enrichment, notifications.

**When to use Speckle**: cross-platform model sharing, design review with non-BIM
stakeholders, automated data pipelines, custom dashboards from model data.

### BHoM (Buildings and Habitats object Model)

BHoM is an open-source collaborative computational framework for the built
environment:

- **Object model**: unified .NET object definitions for structural, environmental, architectural, and planning objects.
- **Adapters**: bidirectional data exchange with analysis software:
  - Structural: Robot, GSA, ETABS, SAP2000, Lusas
  - Environmental: IES, EnergyPlus, Ladybug
  - BIM: Revit, IFC
  - Geometry: Rhino, Grasshopper
- **Engine**: computational methods that operate on BHoM objects (structural analysis queries, environmental calculations, geometry operations).
- **UI**: Grasshopper components and Excel plugin for accessible interaction.

**When to use BHoM**: multi-software structural analysis workflows, computational
design pipelines that span multiple analysis tools, when you need a unified
object model across disciplines.

### Rhino.Inside.Revit

Rhino.Inside.Revit runs the full Rhino and Grasshopper environment inside the
Revit process, enabling:

- **Grasshopper → Revit**: create Revit elements (walls, floors, roofs, adaptive components) from Grasshopper geometry.
- **Revit → Grasshopper**: query Revit elements, extract geometry, read parameters.
- **Bidirectional live link**: changes in Grasshopper update Revit elements; changes in Revit reflect in Grasshopper.
- **Rhino geometry in Revit views**: use Rhino's superior NURBS engine for complex geometry, bake to Revit as DirectShape or native elements.

Use cases:
- Complex facade panelization designed in GH, built as Revit curtain panels.
- Parametric roof geometry from GH, exported as Revit roof-by-face.
- Site grading and landscape computed in GH, placed as Revit topography.
- Structural optimization in GH (Karamba3D), results pushed to Revit structural model.

### Comparison Table

| Feature | Speckle | BHoM | Rhino.Inside.Revit |
|---|---|---|---|
| Primary use | Data exchange & versioning | Computational workflows | Geometry & design |
| Architecture | Cloud-based streams | .NET object model + adapters | In-process (runs inside Revit) |
| Revit support | Connector (push/pull) | Adapter (read/write) | Full bidirectional live link |
| Rhino/GH support | Connector | GH components | Native (Rhino is the engine) |
| Analysis tools | Via Automate | Native adapters (Robot, GSA, etc.) | Via GH plugins (Karamba, Ladybug) |
| Open source | Yes (Apache 2.0) | Yes (LGPL 3.0) | Yes (MIT) |
| Best for | Cross-platform data flow | Multi-tool analysis pipelines | Complex geometry in Revit |

---

## 9. BIM Scripting Best Practices

### Error Handling and Logging

```python
from pyrevit import revit, DB, forms
import traceback

doc = revit.doc
errors = []
success_count = 0

with revit.Transaction("Batch Operation"):
    for element in elements:
        try:
            # operation that might fail
            param = element.LookupParameter("Target Param")
            if param and not param.IsReadOnly:
                param.Set(new_value)
                success_count += 1
            else:
                errors.append("Element {}: parameter not found or read-only".format(element.Id))
        except Exception as e:
            errors.append("Element {}: {}".format(element.Id, str(e)))

# Report results
msg = "Processed: {}\nErrors: {}".format(success_count, len(errors))
if errors:
    msg += "\n\n" + "\n".join(errors[:20])  # limit error display
forms.alert(msg, title="Operation Complete")
```

### Performance Best Practices

1. **Minimize FilteredElementCollector calls** --- collect once, filter in Python.
2. **Use quick filters** (OfClass, OfCategory) before slow filters (WherePasses with parameter filter).
3. **Disable regeneration** when not needed: `doc.Regenerate()` only when required.
4. **Batch element creation** --- create elements in a single transaction, not one transaction per element.
5. **Avoid `Element.Geometry` in loops** --- geometry extraction is expensive. Cache results.
6. **Use `ElementId` sets** for fast lookups instead of element lists.
7. **Turn off warning suppression wisely** --- `FailureHandlingOptions` can skip dialog boxes during batch operations.

### User Input Patterns

```python
from pyrevit import forms

# Simple alert
forms.alert("Operation complete.", title="Success")

# Yes/No prompt
if forms.alert("Continue with operation?", yes=True, no=True):
    # proceed
    pass

# Select from list
selected = forms.SelectFromList.show(
    options,
    title="Select Elements",
    multiselect=True
)

# Text input
value = forms.ask_for_string(
    prompt="Enter new parameter value:",
    title="Parameter Update"
)
```

### Transaction Management

| Pattern | Use Case | Undo Behavior |
|---|---|---|
| Single Transaction | Most operations | One undo step |
| TransactionGroup (assimilate) | Multi-step that should appear as one undo | One undo step |
| TransactionGroup (no assimilate) | Multi-step with individual undo | Multiple undo steps |
| SubTransaction | Tentative changes within a transaction | Roll back sub-changes without aborting main transaction |

### Version Compatibility

Key API changes across Revit versions:

| Version | Notable API Changes |
|---|---|
| 2021 | `ForgeTypeId` begins replacing `UnitType` and `DisplayUnitType` |
| 2022 | `UnitTypeId` fully replaces `DisplayUnitType`; PDF export API added |
| 2023 | `Toposolid` replaces `TopographySurface`; analytical model API overhaul |
| 2024 | `Document.GetUnusedElements()` added; `Element.IsHidden()` improvements |
| 2025 | `ParameterFilterElement` improvements; enhanced schedule API |

### Code Organization

```
my_extension.extension/
  ├── lib/
  │    ├── __init__.py
  │    ├── config.py           (settings, constants)
  │    ├── collectors.py       (reusable FilteredElementCollector wrappers)
  │    ├── param_utils.py      (parameter read/write helpers)
  │    ├── geom_utils.py       (geometry extraction helpers)
  │    ├── export_utils.py     (PDF, DWG, IFC export wrappers)
  │    └── report.py           (HTML report generation)
  ├── MyTab.tab/
  │    ├── QA.panel/
  │    │    ├── CheckRooms.pushbutton/
  │    │    ├── CheckNaming.pushbutton/
  │    │    └── CheckParams.pushbutton/
  │    ├── Export.panel/
  │    │    ├── BatchPDF.pushbutton/
  │    │    └── BatchIFC.pushbutton/
  │    └── Data.panel/
  │         ├── ParamWriter.pushbutton/
  │         └── ExcelSync.pushbutton/
  └── hooks/
       └── doc-opened-[audit].py
```

### Testing Strategies

1. **Test on a dedicated test model** --- a small .rvt file with representative elements of every category.
2. **Log extensively during development** --- use `print()` or pyRevit's output module.
3. **Test edge cases** --- empty parameters, zero-area rooms, unplaced rooms, design options, phases, linked models.
4. **Version test** --- verify scripts work across target Revit versions (2022, 2023, 2024, 2025).
5. **Performance test** --- run scripts on the largest project model to identify bottlenecks.
6. **User acceptance test** --- deploy to 2-3 users before firm-wide rollout; collect feedback.
7. **Regression test** --- after Revit updates, re-run all scripts to verify continued functionality.
