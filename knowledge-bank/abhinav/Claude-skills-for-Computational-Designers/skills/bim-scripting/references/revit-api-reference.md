# Revit API Deep Reference

Comprehensive code-level reference for the Autodesk Revit API. All examples are
in Python (pyRevit / RevitPythonShell / Dynamo CPython) unless noted otherwise.
The .NET namespace is `Autodesk.Revit.DB` for model operations and
`Autodesk.Revit.UI` for UI interactions.

---

## 1. FilteredElementCollector Patterns

The `FilteredElementCollector` is the single most important class in the Revit
API. It queries the model database efficiently using a combination of quick
filters (index-based) and slow filters (per-element evaluation).

### Basic Collection Patterns

```python
from Autodesk.Revit.DB import *

doc = __revit__.ActiveUIDocument.Document

# 1. All wall instances (not types)
walls = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .WhereElementIsNotElementType() \
    .ToElements()

# 2. All wall types (not instances)
wall_types = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .WhereElementIsElementType() \
    .ToElements()

# 3. All family instances (doors, windows, furniture, etc.)
family_instances = FilteredElementCollector(doc) \
    .OfClass(FamilyInstance) \
    .ToElements()

# 4. All levels
levels = FilteredElementCollector(doc) \
    .OfClass(Level) \
    .ToElements()

# 5. All grids
grids = FilteredElementCollector(doc) \
    .OfClass(Grid) \
    .ToElements()

# 6. All rooms
rooms = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Rooms) \
    .WhereElementIsNotElementType() \
    .ToElements()

# 7. All sheets
sheets = FilteredElementCollector(doc) \
    .OfClass(ViewSheet) \
    .ToElements()

# 8. All floor plan views
plans = FilteredElementCollector(doc) \
    .OfClass(ViewPlan) \
    .WhereElementIsNotElementType() \
    .ToElements()

# 9. All 3D views
views3d = FilteredElementCollector(doc) \
    .OfClass(View3D) \
    .WhereElementIsNotElementType() \
    .ToElements()

# 10. All section views
sections = FilteredElementCollector(doc) \
    .OfClass(ViewSection) \
    .WhereElementIsNotElementType() \
    .ToElements()

# 11. All view templates (views where IsTemplate is True)
templates = [v for v in FilteredElementCollector(doc).OfClass(View).ToElements()
             if v.IsTemplate]

# 12. Elements visible in a specific view
view_elements = FilteredElementCollector(doc, active_view.Id) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .ToElements()

# 13. All materials
materials = FilteredElementCollector(doc) \
    .OfClass(Material) \
    .ToElements()

# 14. All line styles
line_styles = FilteredElementCollector(doc) \
    .OfClass(GraphicsStyle) \
    .ToElements()

# 15. All fill patterns
fill_patterns = FilteredElementCollector(doc) \
    .OfClass(FillPatternElement) \
    .ToElements()
```

### Filtered Queries with Parameter Filters

```python
from Autodesk.Revit.DB import *

# 16. Walls with a specific type name
provider = ParameterValueProvider(ElementId(BuiltInParameter.SYMBOL_NAME_PARAM))
rule = FilterStringRule(provider, FilterStringContains(), "Concrete")
param_filter = ElementParameterFilter(rule)

concrete_walls = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .WhereElementIsNotElementType() \
    .WherePasses(param_filter) \
    .ToElements()

# 17. Rooms with area greater than threshold
area_provider = ParameterValueProvider(
    ElementId(BuiltInParameter.ROOM_AREA))
area_rule = FilterDoubleRule(
    area_provider, FilterNumericGreater(), 500.0, 0.01)  # 500 sq ft
area_filter = ElementParameterFilter(area_rule)

large_rooms = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Rooms) \
    .WhereElementIsNotElementType() \
    .WherePasses(area_filter) \
    .ToElements()

# 18. Elements on a specific level
level_filter = ElementLevelFilter(target_level.Id)
elements_on_level = FilteredElementCollector(doc) \
    .WherePasses(level_filter) \
    .ToElements()

# 19. Elements in a specific workset
workset_filter = ElementWorksetFilter(workset_id)
workset_elements = FilteredElementCollector(doc) \
    .WherePasses(workset_filter) \
    .ToElements()

# 20. Elements within a bounding box (spatial query)
outline = Outline(XYZ(min_x, min_y, min_z), XYZ(max_x, max_y, max_z))
bb_filter = BoundingBoxIntersectsFilter(outline)

elements_in_box = FilteredElementCollector(doc) \
    .WherePasses(bb_filter) \
    .ToElements()

# 21. Combining filters with LogicalAndFilter / LogicalOrFilter
cat_filter = ElementCategoryFilter(BuiltInCategory.OST_Walls)
level_filter = ElementLevelFilter(level.Id)
combined = LogicalAndFilter(cat_filter, level_filter)

walls_on_level = FilteredElementCollector(doc) \
    .WherePasses(combined) \
    .WhereElementIsNotElementType() \
    .ToElements()

# 22. Exclude specific element IDs
exclusion = ExclusionFilter([element1.Id, element2.Id, element3.Id])
remaining = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .WherePasses(exclusion) \
    .ToElements()

# 23. Elements owned by a specific design option
option_filter = ElementDesignOptionFilter(design_option.Id)
option_elements = FilteredElementCollector(doc) \
    .WherePasses(option_filter) \
    .ToElements()

# 24. Structural elements only (structural usage filter)
struct_filter = ElementStructuralTypeFilter(StructuralType.Column)
columns = FilteredElementCollector(doc) \
    .OfClass(FamilyInstance) \
    .WherePasses(struct_filter) \
    .ToElements()
```

### Performance Tips for Collectors

```python
# FAST: use OfClass or OfCategory as the first filter (index-based)
# SLOW: WherePasses with parameter filter first, then OfCategory

# GOOD: quick filter first
collector = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .WherePasses(param_filter)

# BAD: slow filter first
collector = FilteredElementCollector(doc) \
    .WherePasses(param_filter) \
    .OfCategory(BuiltInCategory.OST_Walls)

# Use ToElementIds() when you only need IDs (less memory)
wall_ids = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .WhereElementIsNotElementType() \
    .ToElementIds()

# Use FirstElement() when you need just one
first_wall = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .WhereElementIsNotElementType() \
    .FirstElement()

# Use GetElementCount() for counting without element instantiation
count = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_Walls) \
    .WhereElementIsNotElementType() \
    .GetElementCount()
```

---

## 2. Transaction Patterns

### Single Transaction

```python
from Autodesk.Revit.DB import Transaction

doc = __revit__.ActiveUIDocument.Document

t = Transaction(doc, "My Operation")
t.Start()
try:
    # modify model
    wall.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS).Set("Updated")
    t.Commit()
except Exception as e:
    t.RollBack()
    raise e
```

### Transaction Group (Assimilate)

```python
from Autodesk.Revit.DB import Transaction, TransactionGroup

tg = TransactionGroup(doc, "Multi-Step Operation")
tg.Start()

t1 = Transaction(doc, "Step 1")
t1.Start()
# ... modifications ...
t1.Commit()

t2 = Transaction(doc, "Step 2")
t2.Start()
# ... modifications ...
t2.Commit()

tg.Assimilate()  # merges all into one undo step
# OR tg.Commit() to keep individual undo steps
# OR tg.RollBack() to undo everything
```

### Sub-Transaction

```python
from Autodesk.Revit.DB import Transaction, SubTransaction

t = Transaction(doc, "Operation with Rollback")
t.Start()

# Try something
st = SubTransaction(doc)
st.Start()
try:
    # tentative modification
    element.Location.Move(XYZ(10, 0, 0))
    st.Commit()
except:
    st.RollBack()  # undo just this part

# Continue with main transaction
# ... more modifications ...
t.Commit()
```

### Failure Handling

```python
from Autodesk.Revit.DB import (
    Transaction, FailureHandlingOptions,
    FailureSeverity
)

t = Transaction(doc, "Suppressed Warnings")
options = t.GetFailureHandlingOptions()

# Create a preprocessor to handle warnings
class WarningSwallower(IFailuresPreprocessor):
    def PreprocessFailures(self, failuresAccessor):
        failures = failuresAccessor.GetFailureMessages()
        for f in failures:
            if f.GetSeverity() == FailureSeverity.Warning:
                failuresAccessor.DeleteWarning(f)
        return FailureProcessingResult.Continue

options.SetFailuresPreprocessor(WarningSwallower())
t.SetFailureHandlingOptions(options)

t.Start()
# ... operations that may produce warnings ...
t.Commit()
```

### pyRevit Transaction Context Manager

```python
from pyrevit import revit

# Simplest form
with revit.Transaction("My Operation"):
    element.LookupParameter("Comments").Set("Done")

# With error handling
with revit.Transaction("Careful Operation") as t:
    try:
        element.LookupParameter("Comments").Set("Done")
    except:
        t.RollBack()
```

---

## 3. Parameter Access Patterns

### By Built-in Parameter

```python
# Direct access to built-in parameters (most reliable)
wall = doc.GetElement(ElementId(12345))

# Instance parameters
base_offset = wall.get_Parameter(BuiltInParameter.WALL_BASE_OFFSET).AsDouble()
base_level = wall.get_Parameter(BuiltInParameter.WALL_BASE_CONSTRAINT).AsElementId()
comments = wall.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS).AsString()
length = wall.get_Parameter(BuiltInParameter.CURVE_ELEM_LENGTH).AsDouble()

# Type parameters (access via element type)
wall_type = doc.GetElement(wall.GetTypeId())
width = wall_type.get_Parameter(BuiltInParameter.WALL_ATTR_WIDTH_PARAM).AsDouble()

# Set parameter value
with revit.Transaction("Set Comment"):
    wall.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS).Set("Reviewed")
```

### By Name (LookupParameter)

```python
# Access custom parameters by name
param = element.LookupParameter("Fire Rating")
if param:
    if param.StorageType == StorageType.String:
        value = param.AsString()
    elif param.StorageType == StorageType.Double:
        value = param.AsDouble()
    elif param.StorageType == StorageType.Integer:
        value = param.AsInteger()
    elif param.StorageType == StorageType.ElementId:
        value = param.AsElementId()
```

### By Shared Parameter GUID

```python
import System
from System import Guid

guid = Guid("12345678-1234-1234-1234-123456789012")
param = element.get_Parameter(guid)
if param:
    value = param.AsString()
```

### Parameter Value Setting by Type

```python
with revit.Transaction("Set Parameters"):
    # String
    element.LookupParameter("Room_Code").Set("A-101")

    # Double (always in internal units - feet for length)
    element.LookupParameter("Custom_Height").Set(10.0)  # 10 feet

    # Integer
    element.LookupParameter("Floor_Number").Set(3)

    # YesNo (Integer 0 or 1)
    element.LookupParameter("Is_Accessible").Set(1)  # Yes

    # ElementId (reference to another element)
    element.LookupParameter("Material").Set(material.Id)
```

### Reading All Parameters of an Element

```python
for param in element.Parameters:
    name = param.Definition.Name
    storage = param.StorageType
    if storage == StorageType.String:
        val = param.AsString() or ""
    elif storage == StorageType.Double:
        val = param.AsDouble()
    elif storage == StorageType.Integer:
        val = param.AsInteger()
    elif storage == StorageType.ElementId:
        val = param.AsElementId().IntegerValue
    print("{}: {} ({})".format(name, val, storage))
```

---

## 4. Geometry Extraction Patterns

### Basic Geometry Access

```python
from Autodesk.Revit.DB import Options

# Configure geometry options
opts = Options()
opts.ComputeReferences = True       # include references for dimensioning
opts.IncludeNonVisibleObjects = False
opts.DetailLevel = ViewDetailLevel.Fine

# Get geometry from element
geom_elem = element.get_Geometry(opts)
```

### Element to Solid

```python
def get_solids(element, opts=None):
    """Extract all solids from an element."""
    if opts is None:
        opts = Options()
        opts.ComputeReferences = True

    solids = []
    geom = element.get_Geometry(opts)
    if geom is None:
        return solids

    for geom_obj in geom:
        if isinstance(geom_obj, Solid):
            if geom_obj.Volume > 0:
                solids.append(geom_obj)
        elif isinstance(geom_obj, GeometryInstance):
            # For family instances, get instance geometry
            inst_geom = geom_obj.GetInstanceGeometry()
            for inst_obj in inst_geom:
                if isinstance(inst_obj, Solid):
                    if inst_obj.Volume > 0:
                        solids.append(inst_obj)
    return solids
```

### Solid to Faces

```python
solid = get_solids(wall)[0]

for face in solid.Faces:
    area = face.Area  # in square feet
    normal = face.ComputeNormal(UV(0.5, 0.5))  # normal at midpoint
    origin = face.Evaluate(UV(0.5, 0.5))       # point at midpoint

    # Get face edges
    for edge_loop in face.EdgeLoops:
        for edge in edge_loop:
            curve = edge.AsCurve()
            start = curve.GetEndPoint(0)
            end = curve.GetEndPoint(1)
```

### Solid to Edges

```python
for edge in solid.Edges:
    curve = edge.AsCurve()
    length = curve.Length  # in feet
    start = curve.GetEndPoint(0)
    end = curve.GetEndPoint(1)

    # Get faces that share this edge
    face_0 = edge.GetFace(0)
    face_1 = edge.GetFace(1)
```

### Wall Geometry (Location Curve)

```python
# Walls are line-based elements; their location is a curve
location = wall.Location
if isinstance(location, LocationCurve):
    curve = location.Curve
    start = curve.GetEndPoint(0)
    end = curve.GetEndPoint(1)
    length = curve.Length
    midpoint = curve.Evaluate(0.5, True)  # normalized parameter
```

### BoundingBox

```python
bb = element.get_BoundingBox(None)  # None = model space
if bb:
    min_pt = bb.Min  # XYZ
    max_pt = bb.Max  # XYZ
    center = (min_pt + max_pt) / 2.0
    width = max_pt.X - min_pt.X
    depth = max_pt.Y - min_pt.Y
    height = max_pt.Z - min_pt.Z
```

---

## 5. Element Creation Patterns

### Walls

```python
from Autodesk.Revit.DB import *

with revit.Transaction("Create Wall"):
    # Line-based wall
    start = XYZ(0, 0, 0)
    end = XYZ(20, 0, 0)  # 20 feet long
    line = Line.CreateBound(start, end)

    wall = Wall.Create(
        doc,
        line,                    # curve
        wall_type.Id,            # wall type ElementId
        level.Id,                # base level ElementId
        10.0,                    # height in feet
        0.0,                     # offset from level
        False,                   # flip orientation
        False                    # structural
    )
```

### Floors

```python
with revit.Transaction("Create Floor"):
    # Define floor boundary
    curves = CurveArray()
    curves.Append(Line.CreateBound(XYZ(0, 0, 0), XYZ(20, 0, 0)))
    curves.Append(Line.CreateBound(XYZ(20, 0, 0), XYZ(20, 15, 0)))
    curves.Append(Line.CreateBound(XYZ(20, 15, 0), XYZ(0, 15, 0)))
    curves.Append(Line.CreateBound(XYZ(0, 15, 0), XYZ(0, 0, 0)))

    # Revit 2022+: use CurveLoop
    curve_loop = CurveLoop()
    curve_loop.Append(Line.CreateBound(XYZ(0, 0, 0), XYZ(20, 0, 0)))
    curve_loop.Append(Line.CreateBound(XYZ(20, 0, 0), XYZ(20, 15, 0)))
    curve_loop.Append(Line.CreateBound(XYZ(20, 15, 0), XYZ(0, 15, 0)))
    curve_loop.Append(Line.CreateBound(XYZ(0, 15, 0), XYZ(0, 0, 0)))

    profile = [curve_loop]
    floor = Floor.Create(doc, profile, floor_type.Id, level.Id)
```

### Columns

```python
with revit.Transaction("Create Column"):
    point = XYZ(10, 10, 0)
    column = doc.Create.NewFamilyInstance(
        point,
        column_symbol,           # FamilySymbol (type)
        base_level,              # Level
        StructuralType.Column    # structural type
    )
```

### Beams

```python
with revit.Transaction("Create Beam"):
    start = XYZ(0, 0, 10)
    end = XYZ(20, 0, 10)
    line = Line.CreateBound(start, end)

    beam = doc.Create.NewFamilyInstance(
        line,
        beam_symbol,             # FamilySymbol (type)
        level,                   # Level
        StructuralType.Beam      # structural type
    )
```

### Family Instances (Generic)

```python
with revit.Transaction("Place Family"):
    # Point-based placement
    point = XYZ(5, 5, 0)
    instance = doc.Create.NewFamilyInstance(
        point,
        family_symbol,           # FamilySymbol must be activated first
        StructuralType.NonStructural
    )

    # Host-based placement (e.g., door in wall)
    door = doc.Create.NewFamilyInstance(
        XYZ(10, 0, 0),          # location on wall
        door_symbol,
        host_wall,
        level,
        StructuralType.NonStructural
    )
```

### Rooms

```python
with revit.Transaction("Create Room"):
    # Rooms are placed at a point within bounded area
    room = doc.Create.NewRoom(level, UV(10, 10))
    room.Name = "Office 101"
    room.Number = "101"
```

---

## 6. View Creation and Manipulation

```python
from Autodesk.Revit.DB import *

# Get view family type for floor plans
vft_id = doc.GetDefaultElementTypeId(ElementTypeGroup.ViewTypeFloorPlan)

with revit.Transaction("Create Views"):
    # Floor plan
    plan = ViewPlan.Create(doc, vft_id, level.Id)
    plan.Name = "Level 1 - Architectural"

    # Apply view template
    template = [v for v in FilteredElementCollector(doc).OfClass(View)
                if v.IsTemplate and v.Name == "Architectural Plan"][0]
    plan.ViewTemplateId = template.Id

    # Set crop box
    plan.CropBoxActive = True
    bb = plan.CropBox
    bb.Min = XYZ(-50, -50, bb.Min.Z)
    bb.Max = XYZ(150, 100, bb.Max.Z)
    plan.CropBox = bb

    # Set scale
    plan.Scale = 100  # 1:100

    # Set detail level
    plan.DetailLevel = ViewDetailLevel.Medium

    # 3D view
    vft_3d = doc.GetDefaultElementTypeId(ElementTypeGroup.ViewType3D)
    view3d = View3D.CreateIsometric(doc, vft_3d)
    view3d.Name = "Coordination 3D"

    # Section view
    section_box = BoundingBoxXYZ()
    section_box.Min = XYZ(-10, -5, 0)
    section_box.Max = XYZ(30, 5, 15)

    # Transform for section orientation
    transform = Transform.Identity
    transform.Origin = XYZ(10, 0, 7.5)
    transform.BasisX = XYZ(1, 0, 0)
    transform.BasisY = XYZ(0, 0, 1)
    transform.BasisZ = XYZ(0, -1, 0)
    section_box.Transform = transform

    vft_section = doc.GetDefaultElementTypeId(ElementTypeGroup.ViewTypeSection)
    section = ViewSection.CreateSection(doc, vft_section, section_box)
    section.Name = "Section A-A"
```

---

## 7. Schedule Creation via API

```python
from Autodesk.Revit.DB import *

with revit.Transaction("Create Schedule"):
    # Create a room schedule
    schedule = ViewSchedule.CreateSchedule(
        doc,
        ElementId(BuiltInCategory.OST_Rooms)
    )
    schedule.Name = "Room Schedule"

    # Add fields
    schedulable = schedule.Definition.GetSchedulableFields()
    field_names = ["Number", "Name", "Area", "Level", "Department"]

    for sf in schedulable:
        if sf.GetName(doc) in field_names:
            schedule.Definition.AddField(sf)

    # Add filter (rooms with area > 0)
    area_field_id = None
    for field in schedule.Definition.GetFieldOrder():
        f = schedule.Definition.GetField(field)
        if f.GetName() == "Area":
            area_field_id = f.FieldId
            break

    if area_field_id:
        sf = ScheduleFilter(area_field_id,
                           ScheduleFilterType.GreaterThan,
                           0.0)
        schedule.Definition.AddFilter(sf)

    # Add sorting
    if area_field_id:
        sort_group = ScheduleSortGroupField(area_field_id)
        sort_group.SortOrder = ScheduleSortOrder.Ascending
        schedule.Definition.AddSortGroupField(sort_group)
```

---

## 8. Export Methods

### PDF Export (Revit 2022+)

```python
sheets = FilteredElementCollector(doc) \
    .OfClass(ViewSheet) \
    .ToElements()

sheet_ids = List[ElementId]([s.Id for s in sheets if s.CanBePrinted])

pdf_options = PDFExportOptions()
pdf_options.FileName = "Project_Drawings"
pdf_options.Combine = True           # single PDF
pdf_options.PaperFormat = ExportPaperFormat.Default
pdf_options.ZoomType = ZoomType.FitToPage
pdf_options.ColorDepth = ColorDepthType.Color

doc.Export("C:/Output/", sheet_ids, pdf_options)
```

### DWG Export

```python
dwg_options = DWGExportOptions()
dwg_options.FileVersion = ACADVersion.R2018
dwg_options.ExportOfSolids = SolidGeometry.ACIS
dwg_options.SharedCoords = True

view_ids = List[ElementId]([view.Id])
doc.Export("C:/Output/", "exported_plan", view_ids, dwg_options)
```

### IFC Export

```python
ifc_options = IFCExportOptions()
ifc_options.FileVersion = IFCVersion.IFC4
ifc_options.SpaceBoundaryLevel = 1
ifc_options.ExportBaseQuantities = True
ifc_options.WallAndColumnSplitting = True
ifc_options.FilterViewId = ElementId.InvalidElementId  # whole model

doc.Export("C:/Output/", "model.ifc", ifc_options)
```

### Image Export

```python
img_options = ImageExportOptions()
img_options.ExportRange = ExportRange.SetOfViews
img_options.SetViewsAndSheets([view.Id])
img_options.ZoomType = ZoomFitType.FitToPage
img_options.PixelSize = 3840  # width in pixels
img_options.ImageResolution = ImageResolution.DPI_300
img_options.HLRandWFViewsFileType = ImageFileType.PNG
img_options.ShadowViewsFileType = ImageFileType.PNG
img_options.FilePath = "C:/Output/view_export"

doc.ExportImage(img_options)
```

---

## 9. External Events and IUpdater

### External Event Handler

For modifying the model from external threads (web callbacks, async operations):

```csharp
// C# implementation
public class MyEventHandler : IExternalEventHandler
{
    public string Data { get; set; }

    public void Execute(UIApplication app)
    {
        Document doc = app.ActiveUIDocument.Document;
        using (Transaction t = new Transaction(doc, "External Update"))
        {
            t.Start();
            // Modify model using this.Data
            t.Commit();
        }
    }

    public string GetName() => "MyEventHandler";
}

// Registration (in IExternalApplication.OnStartup)
var handler = new MyEventHandler();
var externalEvent = ExternalEvent.Create(handler);

// Trigger from external thread
handler.Data = "new_value";
externalEvent.Raise();
```

### IUpdater Interface

Reacts to model changes in real time:

```csharp
public class WallUpdater : IUpdater
{
    static AddInId _appId;
    static UpdaterId _updaterId;

    public WallUpdater(AddInId id)
    {
        _appId = id;
        _updaterId = new UpdaterId(_appId, new Guid("..."));
    }

    public void Execute(UpdaterData data)
    {
        Document doc = data.GetDocument();
        foreach (ElementId id in data.GetModifiedElementIds())
        {
            Wall wall = doc.GetElement(id) as Wall;
            // React to wall modification
        }
    }

    public string GetAdditionalInformation() => "Monitors wall changes";
    public ChangePriority GetChangePriority() => ChangePriority.FloorsRoofsStructuralWalls;
    public UpdaterId GetUpdaterId() => _updaterId;
    public string GetUpdaterName() => "WallUpdater";
}

// Registration
UpdaterRegistry.RegisterUpdater(new WallUpdater(app.ActiveAddInId));
UpdaterRegistry.AddTrigger(
    updaterId,
    new ElementCategoryFilter(BuiltInCategory.OST_Walls),
    Element.GetChangeTypeAny()
);
```

---

## 10. Common BuiltInParameter Reference

### General (All Elements)

| Enum | Description | Storage |
|---|---|---|
| `ALL_MODEL_INSTANCE_COMMENTS` | Comments parameter | String |
| `ALL_MODEL_MARK` | Mark parameter | String |
| `ELEM_CATEGORY_PARAM` | Element category | ElementId |
| `ELEM_FAMILY_PARAM` | Element family | ElementId |
| `ELEM_TYPE_PARAM` | Element type | ElementId |
| `DESIGN_OPTION_ID` | Design option membership | ElementId |
| `PHASE_CREATED` | Phase created | ElementId |
| `PHASE_DEMOLISHED` | Phase demolished | ElementId |
| `ELEM_PARTITION_PARAM` | Workset | Integer |

### Walls

| Enum | Description | Storage |
|---|---|---|
| `WALL_BASE_CONSTRAINT` | Base constraint (level) | ElementId |
| `WALL_BASE_OFFSET` | Base offset | Double (feet) |
| `WALL_HEIGHT_TYPE` | Top constraint (level or unconnected) | ElementId |
| `WALL_USER_HEIGHT_PARAM` | Unconnected height | Double (feet) |
| `WALL_TOP_OFFSET` | Top offset | Double (feet) |
| `WALL_ATTR_WIDTH_PARAM` | Wall width (type parameter) | Double (feet) |
| `CURVE_ELEM_LENGTH` | Wall length | Double (feet) |
| `HOST_AREA_COMPUTED` | Wall area | Double (sq ft) |
| `HOST_VOLUME_COMPUTED` | Wall volume | Double (cu ft) |
| `WALL_KEY_REF_PARAM` | Location line (center, face, core) | Integer |
| `WALL_STRUCTURAL_SIGNIFICANT` | Structural usage | Integer |

### Rooms and Spaces

| Enum | Description | Storage |
|---|---|---|
| `ROOM_NAME` | Room name | String |
| `ROOM_NUMBER` | Room number | String |
| `ROOM_AREA` | Room area | Double (sq ft) |
| `ROOM_VOLUME` | Room volume | Double (cu ft) |
| `ROOM_PERIMETER` | Room perimeter | Double (feet) |
| `ROOM_HEIGHT` | Computation height | Double (feet) |
| `ROOM_LEVEL_ID` | Room level | ElementId |
| `ROOM_UPPER_LEVEL` | Upper limit | ElementId |
| `ROOM_UPPER_OFFSET` | Limit offset | Double (feet) |
| `ROOM_DEPARTMENT` | Department | String |
| `ROOM_OCCUPANCY` | Occupancy | String |
| `ROOM_FINISH_FLOOR` | Floor finish | String |
| `ROOM_FINISH_WALL` | Wall finish | String |
| `ROOM_FINISH_CEILING` | Ceiling finish | String |
| `ROOM_FINISH_BASE` | Base finish | String |

### Doors and Windows

| Enum | Description | Storage |
|---|---|---|
| `DOOR_HEIGHT` | Height | Double (feet) |
| `DOOR_WIDTH` | Width | Double (feet) |
| `INSTANCE_HEAD_HEIGHT_PARAM` | Head height | Double (feet) |
| `INSTANCE_SILL_HEIGHT_PARAM` | Sill height | Double (feet) |
| `FAMILY_LEVEL_PARAM` | Level | ElementId |
| `INSTANCE_ELEVATION_PARAM` | Elevation from level | Double (feet) |
| `HOST_ID_PARAM` | Host element (wall) | ElementId |
| `DOOR_NUMBER` | Mark / Number | String |

### Views

| Enum | Description | Storage |
|---|---|---|
| `VIEW_SCALE` | View scale denominator (e.g., 100) | Integer |
| `VIEW_DETAIL_LEVEL` | Detail level (coarse/medium/fine) | Integer |
| `VIEW_DISCIPLINE` | Discipline (architectural, structural, MEP) | Integer |
| `VIEW_TEMPLATE` | Applied view template | ElementId |
| `VIEW_PHASE` | Phase filter | ElementId |
| `VIEWER_CROP_REGION_VISIBLE` | Crop region visible | Integer (0/1) |
| `VIEWER_CROP_REGION` | Crop region active | Integer (0/1) |

### Sheets

| Enum | Description | Storage |
|---|---|---|
| `SHEET_NUMBER` | Sheet number | String |
| `SHEET_NAME` | Sheet name | String |
| `SHEET_ISSUE_DATE` | Issue date | String |
| `SHEET_DRAWN_BY` | Drawn by | String |
| `SHEET_CHECKED_BY` | Checked by | String |
| `SHEET_APPROVED_BY` | Approved by | String |
| `SHEET_CURRENT_REVISION` | Current revision number | String |
| `SHEET_CURRENT_REVISION_DATE` | Current revision date | String |
| `SHEET_CURRENT_REVISION_DESCRIPTION` | Current revision description | String |

### Structural

| Enum | Description | Storage |
|---|---|---|
| `STRUCTURAL_MATERIAL_PARAM` | Structural material | ElementId |
| `STRUCTURAL_SECTION_SHAPE` | Section shape | Integer |
| `STRUCTURAL_CROSS_SECTION_AREA` | Cross-section area | Double |
| `STRUCTURAL_MOMENT_OF_INERTIA_X` | Moment of inertia (strong axis) | Double |
| `STRUCTURAL_BEAM_END0_RELEASE_FX` | Beam end release | Integer |
| `COLUMN_BASE_LEVEL_PARAM` | Column base level | ElementId |
| `COLUMN_TOP_LEVEL_PARAM` | Column top level | ElementId |
| `FAMILY_BASE_LEVEL_OFFSET_PARAM` | Base level offset | Double |
| `FAMILY_TOP_LEVEL_OFFSET_PARAM` | Top level offset | Double |

---

## 11. Units Conversion Reference

### Length

| From | To | Factor |
|---|---|---|
| Feet (internal) | Meters | multiply by 0.3048 |
| Meters | Feet (internal) | multiply by 3.28084 |
| Feet | Millimeters | multiply by 304.8 |
| Millimeters | Feet | multiply by 0.00328084 |
| Feet | Inches | multiply by 12 |
| Inches | Feet | multiply by 0.08333 |

### Area

| From | To | Factor |
|---|---|---|
| Square feet (internal) | Square meters | multiply by 0.092903 |
| Square meters | Square feet | multiply by 10.7639 |

### Volume

| From | To | Factor |
|---|---|---|
| Cubic feet (internal) | Cubic meters | multiply by 0.0283168 |
| Cubic meters | Cubic feet | multiply by 35.3147 |

### Angle

| From | To | Factor |
|---|---|---|
| Radians (internal) | Degrees | multiply by 57.2958 (180/pi) |
| Degrees | Radians | multiply by 0.0174533 (pi/180) |

### API Conversion (Revit 2022+)

```python
from Autodesk.Revit.DB import UnitUtils, UnitTypeId

# Convert from internal (feet) to meters
meters = UnitUtils.ConvertFromInternalUnits(feet_value, UnitTypeId.Meters)

# Convert from meters to internal (feet)
feet = UnitUtils.ConvertToInternalUnits(meters_value, UnitTypeId.Meters)

# Common UnitTypeId values:
# UnitTypeId.Meters, UnitTypeId.Millimeters, UnitTypeId.Centimeters
# UnitTypeId.Feet, UnitTypeId.Inches
# UnitTypeId.SquareMeters, UnitTypeId.SquareFeet
# UnitTypeId.CubicMeters, UnitTypeId.CubicFeet
# UnitTypeId.Degrees, UnitTypeId.Radians
```

### Legacy Conversion (Revit 2021 and earlier)

```python
from Autodesk.Revit.DB import UnitUtils, DisplayUnitType

meters = UnitUtils.ConvertFromInternalUnits(
    feet_value,
    DisplayUnitType.DUT_METERS
)
```

---

## 12. Error Handling Reference

### Common Exceptions

| Exception | Cause | Solution |
|---|---|---|
| `InvalidOperationException` | Model modification outside transaction | Wrap in Transaction |
| `ArgumentException` | Invalid parameter value (e.g., duplicate name) | Validate input before setting |
| `Autodesk.Revit.Exceptions.InvalidOperationException` | Element in use, cannot modify | Check element state; skip in-use elements |
| `Autodesk.Revit.Exceptions.ArgumentOutOfRangeException` | Value outside valid range | Clamp or validate value range |
| `Autodesk.Revit.Exceptions.ModificationForbiddenException` | Read-only document or element | Check `Document.IsModifiable` |
| `Autodesk.Revit.Exceptions.ModificationOutsideTransactionException` | Model change without transaction | Always use Transaction |
| `Autodesk.Revit.Exceptions.ForbiddenForDynamicUpdateException` | Illegal operation in updater | Use ExternalEvent for complex modifications |
| `Autodesk.Revit.Exceptions.CorruptModelException` | Model file is corrupted | Audit and repair the file |
| `Autodesk.Revit.Exceptions.FileAccessException` | Cannot access linked file or path | Check file paths and permissions |
| `Autodesk.Revit.Exceptions.InternalException` | Revit internal error | Often a Revit bug; try alternative approach |

### Defensive Coding Pattern

```python
from pyrevit import revit, DB, forms
import traceback

def safe_set_parameter(element, param_name, value):
    """Safely set a parameter value with full error handling."""
    param = element.LookupParameter(param_name)
    if param is None:
        return False, "Parameter '{}' not found".format(param_name)
    if param.IsReadOnly:
        return False, "Parameter '{}' is read-only".format(param_name)
    try:
        if param.StorageType == DB.StorageType.String:
            param.Set(str(value))
        elif param.StorageType == DB.StorageType.Double:
            param.Set(float(value))
        elif param.StorageType == DB.StorageType.Integer:
            param.Set(int(value))
        elif param.StorageType == DB.StorageType.ElementId:
            param.Set(DB.ElementId(int(value)))
        return True, "OK"
    except Exception as e:
        return False, str(e)

# Usage
doc = revit.doc
elements = DB.FilteredElementCollector(doc) \
    .OfCategory(DB.BuiltInCategory.OST_Rooms) \
    .WhereElementIsNotElementType() \
    .ToElements()

results = {"success": 0, "failed": 0, "errors": []}

with revit.Transaction("Safe Batch Update"):
    for elem in elements:
        ok, msg = safe_set_parameter(elem, "Department", "Engineering")
        if ok:
            results["success"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(
                "Element {}: {}".format(elem.Id, msg))

forms.alert(
    "Updated: {}\nFailed: {}\n\n{}".format(
        results["success"],
        results["failed"],
        "\n".join(results["errors"][:10])
    ),
    title="Batch Update Results"
)
```
