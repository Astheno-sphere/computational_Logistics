# BIM Automation Specification Template

Professional template for specifying, developing, testing, and deploying BIM
automation tools. Use this template to document the requirements, logic, and
delivery plan for any Revit API script, Dynamo graph, pyRevit extension, IFC
processing tool, or cross-platform BIM automation workflow.

Fill in each section completely before development begins. This document serves
as the contract between the requestor (BIM manager, project architect, design
lead) and the developer (computational designer, BIM developer).

---

## 1. Automation Objective

### 1.1 Problem Statement

Describe the manual workflow that this automation will replace or improve. Be
specific about the pain points: time consumed, error frequency, number of
repetitions, stakeholders affected.

```
Current manual workflow:
  [Describe the step-by-step manual process currently performed]

Pain points:
  - Time per execution: [  ] hours / minutes
  - Frequency: [  ] times per project / per phase / per week
  - Error rate: [ ]% (estimated or measured)
  - Number of affected projects: [  ]
  - Number of affected users: [  ]
```

### 1.2 Automation Goal

State what the tool will accomplish in one or two sentences. This is the "elevator pitch" for the automation.

```
Goal:
  [One sentence describing what the automation does]

Success criteria:
  - [ ] Reduces execution time from [  ] to [  ]
  - [ ] Eliminates [  ] type of errors
  - [ ] Standardizes [  ] across all projects
  - [ ] Enables [  ] workflow that was previously impossible
```

### 1.3 Scope Boundaries

Define explicitly what is in scope and out of scope.

```
In scope:
  - [ ] [specific functionality]
  - [ ] [specific element types]
  - [ ] [specific Revit versions]

Out of scope:
  - [ ] [functionality deferred to future version]
  - [ ] [edge cases not handled]
  - [ ] [related workflows not included]
```

### 1.4 Priority and Timeline

```
Priority:    [ ] Critical  [ ] High  [ ] Medium  [ ] Low
Requested by: [Name, Role]
Target date:  [Date]
Estimated effort: [  ] hours / days
```

---

## 2. Input Requirements

### 2.1 Model Requirements

Describe the state the Revit model (or IFC file) must be in for the tool to
function correctly.

```
Required model state:
  - [ ] Model must be synced with central (workshared projects)
  - [ ] Specific worksets must be open: [  ]
  - [ ] Design options active: [ ] Main Model only  [ ] Specific option: [  ]
  - [ ] Phase: [  ]
  - [ ] Links loaded: [ ] Yes  [ ] No  [ ] Specific links: [  ]
```

### 2.2 Required Elements

List the element categories and parameters the tool depends on.

```
Required element categories:
  - [ ] Walls (BuiltInCategory.OST_Walls)
  - [ ] Floors (BuiltInCategory.OST_Floors)
  - [ ] Rooms (BuiltInCategory.OST_Rooms)
  - [ ] Doors (BuiltInCategory.OST_Doors)
  - [ ] Windows (BuiltInCategory.OST_Windows)
  - [ ] Columns (BuiltInCategory.OST_Columns / OST_StructuralColumns)
  - [ ] Structural Framing (BuiltInCategory.OST_StructuralFraming)
  - [ ] Generic Models (BuiltInCategory.OST_GenericModel)
  - [ ] Other: [  ]

Required parameters (per element category):
  Category: [  ]
    - Parameter name: [  ]  Type: [ ] String  [ ] Double  [ ] Integer  [ ] ElementId
      Source: [ ] Built-in  [ ] Shared  [ ] Project
      Required: [ ] Yes  [ ] No (default: [  ])
```

### 2.3 User Inputs (Runtime)

Define what the user must provide when running the tool.

```
User inputs:
  1. [Input name]: [type]  [description]
     - Method: [ ] Dialog  [ ] Selection  [ ] File picker  [ ] Dropdown
     - Validation: [  ]
     - Default value: [  ]

  2. [Input name]: [type]  [description]
     ...
```

### 2.4 External Data Sources

```
External data:
  - [ ] Excel file: [path / format description]
  - [ ] CSV file: [path / format description]
  - [ ] Database: [connection string / API endpoint]
  - [ ] Shared parameter file: [path]
  - [ ] Keynote file: [path]
  - [ ] IFC file: [version, MVD]
  - [ ] None
```

---

## 3. Processing Logic

### 3.1 Algorithm Overview

Describe the high-level processing steps as a numbered list or flowchart.

```
Step 1: [Collect elements using FilteredElementCollector]
         Filter criteria: [  ]

Step 2: [Validate collected elements]
         Validation rules: [  ]

Step 3: [Process elements]
         Logic: [  ]
         Grouping: [  ]
         Sorting: [  ]

Step 4: [Apply modifications / generate output]
         Modification type: [ ] Parameter update  [ ] Element creation
                            [ ] Element deletion  [ ] Geometry modification
                            [ ] View creation     [ ] Export

Step 5: [Post-processing / reporting]
         Report format: [  ]
```

### 3.2 Business Rules

List every rule the automation must enforce. Number each rule for traceability.

```
BR-001: [Rule description]
        Condition: [when this applies]
        Action: [what happens]
        Exception: [edge cases]

BR-002: [Rule description]
        ...
```

### 3.3 Calculation Methods

If the tool performs calculations, document the formulas, units, and rounding.

```
Calculation: [Name]
  Formula: [  ]
  Input units: [  ] (internal: feet, sq ft, cu ft, radians)
  Output units: [  ]
  Rounding: [  ] decimal places
  Edge cases: [  ]
```

### 3.4 Decision Logic

```
IF [condition]:
    THEN [action]
ELIF [condition]:
    THEN [action]
ELSE:
    [default action]
```

### 3.5 Transaction Strategy

```
Transaction approach:
  [ ] Single transaction (all-or-nothing)
  [ ] Transaction group with assimilate (appears as one undo)
  [ ] Multiple independent transactions (partial success allowed)
  [ ] Sub-transactions for tentative operations

Transaction name: "[descriptive name for undo history]"

Rollback behavior:
  On error: [ ] Roll back all changes  [ ] Keep successful changes
  User notification: [ ] Alert dialog  [ ] Output window  [ ] Log file
```

---

## 4. Output Specification

### 4.1 Model Modifications

```
Elements created:
  - Category: [  ]  Type: [  ]  Count: [estimated]
  - Parameters set on created elements:
    - [param name]: [value source / formula]

Elements modified:
  - Category: [  ]
  - Parameters updated:
    - [param name]: [old value source] → [new value logic]

Elements deleted:
  - Category: [  ]
  - Deletion criteria: [  ]
  - Confirmation required: [ ] Yes  [ ] No

Views created:
  - View type: [ ] Floor Plan  [ ] Section  [ ] 3D  [ ] Schedule  [ ] Sheet
  - Naming convention: [  ]
  - View template: [  ]
  - Scale: [  ]
```

### 4.2 Reports and Exports

```
Report output:
  - Format: [ ] pyRevit output window (HTML)  [ ] CSV  [ ] Excel  [ ] PDF
            [ ] Console / print  [ ] Log file  [ ] JSON
  - Content: [describe columns / fields]
  - File path: [ ] User-selected  [ ] Fixed: [  ]  [ ] Project folder
  - Naming convention: [  ]

Export output:
  - Format: [ ] PDF  [ ] DWG  [ ] IFC  [ ] NWC  [ ] Image
  - Settings: [  ]
  - Scope: [ ] All sheets  [ ] Selected views  [ ] Current view
```

### 4.3 User Feedback

```
Progress indication:
  [ ] pyRevit progress bar (for long operations)
  [ ] Status messages in output window
  [ ] None needed (fast operation)

Completion notification:
  [ ] TaskDialog / forms.alert with summary
  [ ] Output window report
  [ ] None (silent operation)

Summary information:
  - Elements processed: [count]
  - Elements modified: [count]
  - Errors encountered: [count]
  - Time elapsed: [duration]
```

---

## 5. Error Handling

### 5.1 Anticipated Errors

```
Error ID: ERR-001
  Condition: [when this error occurs]
  Severity: [ ] Fatal (abort)  [ ] Warning (continue)  [ ] Info (log only)
  User message: "[friendly error message]"
  Recovery: [automatic retry / skip element / abort operation]
  Logging: [ ] Yes  [ ] No

Error ID: ERR-002
  ...
```

### 5.2 Validation Checks (Pre-Execution)

```
Before execution, verify:
  1. [ ] Active document is not a family document
  2. [ ] Active document is not read-only
  3. [ ] Required worksets are loaded (workshared projects)
  4. [ ] Required parameters exist on target elements
  5. [ ] Required families/types are loaded in the project
  6. [ ] User has selected required elements (if selection-based)
  7. [ ] External data file exists and is accessible
  8. [ ] Revit version is compatible ([min version] - [max version])
```

### 5.3 Failure Handling Strategy

```
On element-level failure:
  [ ] Log error, skip element, continue with remaining elements
  [ ] Abort entire operation, roll back all changes
  [ ] Prompt user to continue or abort

On transaction failure:
  [ ] Roll back, show error, exit
  [ ] Roll back, retry once
  [ ] Show error details for debugging

On external data failure (file not found, invalid format):
  [ ] Show error, abort before any model changes
  [ ] Use default values, warn user
```

---

## 6. User Interface Requirements

### 6.1 Invocation Method

```
Tool location:
  [ ] pyRevit ribbon tab: [tab name] > [panel name] > [button name]
  [ ] Dynamo Player script
  [ ] Dynamo graph (interactive)
  [ ] Revit add-in ribbon button
  [ ] RevitPythonShell command
  [ ] External script (command line)
  [ ] Scheduled / automated (no UI)
```

### 6.2 UI Components

```
Dialog / Form:
  [ ] No UI (runs immediately on click)
  [ ] Simple confirmation dialog (Yes/No)
  [ ] Selection list (forms.SelectFromList)
  [ ] Text input (forms.ask_for_string)
  [ ] File picker (forms.pick_file)
  [ ] Custom WPF form

Custom form fields:
  1. [Field name]: [control type] [options/validation]
  2. [Field name]: [control type] [options/validation]
  ...
```

### 6.3 Icon and Tooltip

```
Icon:
  - Size: 32x32 px (large) + 16x16 px (small)
  - Style: [describe or reference existing icons]
  - File: icon.png in pushbutton folder

Tooltip:
  Title: "[button title]"
  Description: "[1-2 sentence description of what the button does]"
  Author: "[developer name]"
  Help URL: "[link to documentation / wiki]"
```

---

## 7. Testing Plan

### 7.1 Test Model

```
Test model:
  - File name: [  ]
  - Location: [  ]
  - Contents: [describe representative elements]
  - Size: [  ] elements, [  ] MB
  - Revit version: [  ]
```

### 7.2 Test Cases

```
TC-001: [Test name - Happy path]
  Precondition: [model state]
  Input: [user input / selection]
  Expected result: [what should happen]
  Pass criteria: [measurable outcome]

TC-002: [Test name - Edge case]
  Precondition: [unusual model state]
  Input: [edge case input]
  Expected result: [graceful handling]
  Pass criteria: [no crash, appropriate message]

TC-003: [Test name - Empty input]
  Precondition: [no elements matching criteria]
  Input: [none / empty selection]
  Expected result: [informative message, no model changes]
  Pass criteria: [no errors, clear feedback]

TC-004: [Test name - Large dataset performance]
  Precondition: [large model with 10,000+ target elements]
  Input: [standard input]
  Expected result: [completes within acceptable time]
  Pass criteria: [execution time < [  ] seconds]

TC-005: [Test name - Error condition]
  Precondition: [invalid model state / missing data]
  Input: [standard input]
  Expected result: [error message, no model corruption]
  Pass criteria: [transaction rolled back, model intact]

TC-006: [Test name - Version compatibility]
  Precondition: [same model opened in different Revit versions]
  Input: [standard input]
  Expected result: [same result across versions]
  Pass criteria: [works on Revit 2022, 2023, 2024, 2025]
```

### 7.3 Regression Testing

```
After Revit updates or script modifications, re-run:
  [ ] TC-001 through TC-006
  [ ] Performance benchmark
  [ ] UI verification (buttons load, tooltips display)
  [ ] Transaction integrity (undo works correctly)
```

---

## 8. Deployment Plan

### 8.1 Deployment Method

```
Deployment type:
  [ ] pyRevit extension (shared network path)
  [ ] pyRevit extension (Git repository)
  [ ] Dynamo script (.dyn file on shared drive)
  [ ] Compiled add-in (.addin + .dll)
  [ ] RevitPythonShell script
  [ ] Manual distribution (email / download)

Deployment path:
  Network: [\\server\share\pyrevit-extensions\]
  Git: [https://github.com/org/repo.git]
  Local: [C:\ProgramData\pyRevit\Extensions\]
```

### 8.2 Dependencies

```
Runtime dependencies:
  - [ ] pyRevit [version]
  - [ ] Python packages: [list]
  - [ ] .NET assemblies: [list]
  - [ ] Shared parameter file: [path]
  - [ ] External data files: [list with paths]
  - [ ] Revit families: [list]
  - [ ] None

Build dependencies:
  - [ ] Visual Studio [version] (for C# add-ins)
  - [ ] Python [version]
  - [ ] NuGet packages: [list]
  - [ ] None (pure Python script)
```

### 8.3 Rollout Strategy

```
Phase 1: Developer testing
  - Developer runs on test model
  - Fix issues found
  - Duration: [  ] days

Phase 2: Pilot testing
  - 2-3 users test on active project
  - Collect feedback
  - Duration: [  ] days

Phase 3: Firm-wide deployment
  - Deploy to shared extension path
  - Send announcement with instructions
  - Provide brief training (walkthrough / video)
  - Duration: [  ] days

Phase 4: Monitoring
  - Collect usage statistics (if applicable)
  - Address reported issues within [  ] business days
  - Review and iterate quarterly
```

### 8.4 User Documentation

```
Documentation deliverables:
  - [ ] Quick-start guide (1 page with screenshots)
  - [ ] Detailed user manual
  - [ ] Video walkthrough ([  ] minutes)
  - [ ] FAQ / troubleshooting section
  - [ ] In-tool tooltips and help text
  - [ ] None (tool is self-explanatory)

Documentation location:
  [ ] Team wiki: [URL]
  [ ] SharePoint: [path]
  [ ] README in Git repository
  [ ] PDF in shared drive: [path]
```

---

## 9. Maintenance Plan

### 9.1 Ownership

```
Primary developer: [Name]
Backup developer: [Name]
BIM manager (stakeholder): [Name]
Support contact: [email / Teams channel]
```

### 9.2 Version History

```
Version: 1.0.0
  Date: [  ]
  Changes: Initial release
  Developer: [  ]

Version: 1.1.0
  Date: [  ]
  Changes: [  ]
  Developer: [  ]
```

### 9.3 Maintenance Schedule

```
Routine maintenance:
  - [ ] Test after each Revit annual release (verify API compatibility)
  - [ ] Test after pyRevit updates
  - [ ] Review and update shared parameter file if schema changes
  - [ ] Review and update external data mappings
  - [ ] Quarterly review of usage and error logs

Bug fix response times:
  - Critical (tool broken, blocking production): [  ] hours
  - Major (incorrect results, workaround available): [  ] business days
  - Minor (cosmetic, non-blocking): [  ] business days
  - Enhancement request: next quarterly review cycle
```

### 9.4 Known Limitations

```
1. [Limitation description]
   Workaround: [  ]
   Planned fix: [ ] Yes (version [  ])  [ ] No (by design)

2. [Limitation description]
   ...
```

### 9.5 Future Enhancements

```
Backlog (prioritized):
  1. [Enhancement description] - Priority: [ ] High  [ ] Medium  [ ] Low
  2. [Enhancement description] - Priority: [ ] High  [ ] Medium  [ ] Low
  3. [Enhancement description] - Priority: [ ] High  [ ] Medium  [ ] Low
```

---

## Appendix A: Reference Architecture

### pyRevit Extension Structure

```
[ExtensionName].extension/
  ├── [TabName].tab/
  │    ├── [PanelName].panel/
  │    │    ├── [ButtonName].pushbutton/
  │    │    │    ├── script.py
  │    │    │    ├── icon.png
  │    │    │    └── bundle.yaml
  │    │    └── ...
  │    └── ...
  ├── lib/
  │    ├── __init__.py
  │    └── [shared_modules].py
  └── hooks/
       └── [hook_scripts].py
```

### Dynamo Graph Conventions

```
[ScriptName].dyn
  - File naming: PascalCase, descriptive (e.g., BatchUpdateRoomParameters.dyn)
  - Input nodes: grouped at left, clearly labeled
  - Output nodes: grouped at right
  - Python nodes: include docstring header
  - Comments: group nodes with colored backgrounds and title annotations
  - Version: note target Dynamo version in description
```

### C# Add-in Structure

```
MyAddin/
  ├── MyAddin.sln
  ├── MyAddin/
  │    ├── MyAddin.csproj
  │    ├── App.cs                    (IExternalApplication)
  │    ├── Commands/
  │    │    ├── MyCommand.cs         (IExternalCommand)
  │    │    └── ...
  │    ├── Models/
  │    │    └── ...                   (data models)
  │    ├── Services/
  │    │    └── ...                   (business logic)
  │    ├── UI/
  │    │    ├── MyWindow.xaml
  │    │    └── MyWindow.xaml.cs
  │    └── Resources/
  │         ├── icon-16.png
  │         └── icon-32.png
  ├── MyAddin.addin                   (manifest for Revit)
  └── README.md
```

---

## Appendix B: Revit API Quick Reference

### Common Imports (Python)

```python
# pyRevit style
from pyrevit import revit, DB, UI, forms, script, output

# Direct API style
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
```

### Common Operations Cheat Sheet

```python
# Current document
doc = revit.doc  # pyRevit
doc = __revit__.ActiveUIDocument.Document  # RevitPythonShell

# Active view
view = doc.ActiveView

# Selected elements
selection = revit.get_selection()  # pyRevit
uidoc = __revit__.ActiveUIDocument
sel = uidoc.Selection.GetElementIds()

# Collect and filter
elements = DB.FilteredElementCollector(doc) \
    .OfCategory(DB.BuiltInCategory.OST_Walls) \
    .WhereElementIsNotElementType() \
    .ToElements()

# Transaction
with revit.Transaction("Do Something"):
    element.LookupParameter("Comments").Set("Done")

# User dialog
forms.alert("Message", title="Title")
result = forms.alert("Continue?", yes=True, no=True)
selected = forms.SelectFromList.show(items, multiselect=True)
text = forms.ask_for_string(prompt="Enter value:")
filepath = forms.pick_file(file_ext="xlsx")

# Output report
out = output.get_output()
out.print_md("## Report Title")
out.print_table(data, columns=["Col1", "Col2", "Col3"])
```

---

## Appendix C: Specification Checklist

Before submitting this specification for development, verify:

```
[ ] Section 1: Objective is clear, measurable, and scoped
[ ] Section 2: All input requirements are documented
[ ] Section 3: Processing logic covers all business rules and edge cases
[ ] Section 4: Output specification matches stakeholder expectations
[ ] Section 5: Error scenarios are identified with recovery strategies
[ ] Section 6: UI requirements are specified (or confirmed as not needed)
[ ] Section 7: Test cases cover happy path, edge cases, errors, and performance
[ ] Section 8: Deployment method and dependencies are documented
[ ] Section 9: Maintenance ownership and schedule are agreed upon
[ ] Estimated effort is reviewed and accepted by developer and stakeholder
[ ] Priority and timeline are agreed upon
[ ] Specification is reviewed by at least one additional team member
```

---

*Template version: 1.0.0*
*Applicable to: Revit API scripts, pyRevit extensions, Dynamo graphs, C# add-ins, IFC processing tools, cross-platform BIM automation*
