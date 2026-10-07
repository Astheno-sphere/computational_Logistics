# Computational Design Learning Pathways

This reference provides structured learning roadmaps for computational designers at all levels, organized by skill level, by tool, and by domain specialization. It includes curated books, courses, conferences, communities, and portfolio guidance.

---

## 1. Skill Level Pathways

### 1.1 Beginner (0-6 months)

**Goal:** Understand what computational design is, learn one primary tool fluently, and produce basic parametric models.

**Mindset Shift:** You are not learning a tool — you are learning a way of thinking. Computational design is about describing design intent as relationships, not drawing shapes.

**Learning Sequence:**

| Week | Focus | Activities |
|------|-------|------------|
| 1-2 | **Conceptual foundation** | Read "What is Computational Design?" resources; watch talks by Marc Fornes, Patrik Schumacher, Neri Oxman; understand the difference between parametric, generative, and algorithmic design |
| 3-4 | **Rhino basics** | Rhino interface, NURBS fundamentals, basic modeling commands (Extrude, Loft, Sweep, Boolean), layers, display modes |
| 5-8 | **Grasshopper fundamentals** | Components, wires, data flow; Number Sliders; basic geometry (points, curves, surfaces); Move, Rotate, Scale; Divide Curve/Surface |
| 9-10 | **Lists and data management** | List operations (Sort, Reverse, Cull, Dispatch); understanding data matching; Panel and Param Viewer for debugging |
| 11-14 | **Intermediate Grasshopper** | Data trees (Graft, Flatten, Simplify); Attractor logic; Surface evaluation; Loft, Sweep from Grasshopper curves; Custom Preview |
| 15-18 | **First project** | Design and build a complete parametric model: a facade system, a pavilion, or a furniture piece. Document the logic, not just the output |
| 19-24 | **Expanding toolkit** | Introduction to Kangaroo (basic physics), LunchBox (paneling), Ladybug (sun path), and Python scripting basics in GhPython |

**Deliverable:** A portfolio piece showing a parametric design with clear documentation of the Grasshopper definition, parameter ranges, and design intent.

**Common Beginner Mistakes to Avoid:**
- Starting with complex definitions before understanding data flow
- Ignoring data trees — they are not optional, they are fundamental
- Copying tutorials without understanding why each component is used
- Focusing on visual complexity rather than design logic

---

### 1.2 Intermediate (6-18 months)

**Goal:** Combine multiple tools and analysis types, develop scripting ability, and produce performance-driven parametric designs.

**Learning Sequence:**

| Month | Focus | Activities |
|-------|-------|------------|
| 1-2 | **Advanced data trees** | Path Mapper, Flip Matrix, complex tree matching; learn to think in tree structures; debug real-world data tree mismatches |
| 2-3 | **Python scripting** | GhPython component basics; rhinoscriptsyntax; loops, conditionals, functions; reading/writing data from files; list comprehensions |
| 3-4 | **Environmental analysis** | Ladybug: weather data analysis, sun path, radiation; Honeybee: basic energy modeling and daylight analysis; understanding EPW files, climate data |
| 5-6 | **Structural basics** | Karamba3D: defining structural models (beams, shells, loads, supports), analyzing deformation and stress; Kangaroo: dynamic relaxation, form-finding |
| 7-8 | **Optimization** | Galapagos: single-objective evolutionary optimization; Colibri + Design Explorer: design space visualization; understanding fitness functions |
| 9-10 | **Fabrication awareness** | Surface panelization strategies; unrolling; nesting basics; understanding CNC, laser cutting, and 3D printing constraints; Elefront for baking |
| 11-12 | **Interoperability** | Speckle: Grasshopper to Revit workflow; Rhino.Inside basics; IFC concepts; understanding BIM requirements for parametric geometry |

**Deliverable:** A multi-objective design project integrating parametric modeling, environmental analysis, and structural feedback. A Grasshopper definition that others can use (documented, grouped, labeled).

---

### 1.3 Advanced (18-36 months)

**Goal:** Develop expertise in a specialization, contribute to the community, build custom tools, and lead computational design workflows in practice.

**Learning Sequence:**

| Quarter | Focus | Activities |
|---------|-------|------------|
| Q1 | **Advanced Python/C#** | RhinoCommon API; writing custom Grasshopper components in C#; Python libraries (numpy, scipy); object-oriented programming for design systems |
| Q2 | **Specialization deep-dive** | Choose 1-2 specializations: (a) structural optimization, (b) environmental simulation, (c) digital fabrication, (d) generative urbanism, (e) machine learning for design |
| Q3 | **Multi-objective optimization** | Octopus: multi-objective evolutionary optimization; Pareto front analysis; surrogate modeling (Opossum); design space exploration methodology |
| Q4 | **Tool development** | Building custom Grasshopper plugins (C#); developing Python tool libraries; creating Hops-based remote computation services; contributing to open-source projects (COMPAS, Speckle) |

**Deliverable:** A custom tool or plugin that solves a real workflow problem, published on Food4Rhino or GitHub. A specialization portfolio demonstrating deep expertise. Potentially a conference presentation or paper.

---

### 1.4 Expert (3+ years)

**Goal:** Push the boundaries of the field, mentor others, develop novel methods, and define computational design strategy for organizations.

**Focus Areas:**

- **Research:** Develop novel algorithms, methods, or workflows. Publish at ACADIA, CAADRIA, eCAADe, SimAUD, IASS, or in Architectural Design (AD)
- **Practice leadership:** Define computational design strategy for firms. Build internal tool libraries. Establish design-to-fabrication pipelines. Mentor junior computational designers
- **Teaching:** Develop curriculum. Create educational resources. Lead workshops at conferences and universities
- **Community:** Contribute to open-source projects. Organize local computational design meetups. Participate in review panels and juries
- **Cross-disciplinary:** Bridge to data science, machine learning, robotics, materials science. Collaborate with researchers outside AEC

---

## 2. Tool-Specific Pathways

### 2.1 Grasshopper Mastery Pathway

| Level | Topics | Resources |
|-------|--------|-----------|
| **Beginner** | Interface, components, sliders, basic geometry, data flow | Mode Lab's Grasshopper Primer; Modelab tutorials; Parametric House YouTube |
| **Intermediate** | Data trees (deep), scripting (GhPython), analysis plugins (Ladybug, Karamba), optimization (Galapagos) | ThinkParametric courses; Gediminas Kirdeikis tutorials; David Rutten's webinars |
| **Advanced** | Custom C# components, Hops for remote computation, complex data tree manipulation, performance optimization | McNeel developer docs; RhinoCommon SDK; Andrew Heumann's talks; Long Nguyen's advanced tutorials |
| **Expert** | Plugin development (Visual Studio), contributing to Grasshopper 2 ecosystem, building platforms on top of GH | Grasshopper SDK documentation; GitHub open-source plugin codebases; GH developer forum |

### 2.2 Dynamo / Revit Computational Pathway

| Level | Topics | Resources |
|-------|--------|-----------|
| **Beginner** | Dynamo interface, nodes, basic Revit element creation, list management | Dynamo Primer (free); AU (Autodesk University) classes; DiRoots tutorials |
| **Intermediate** | Python scripting in Dynamo, Revit API access, custom packages, Generative Design | archi-lab tutorials; Dynamo Developer blog; BIM Chapters; Paul Aubin's courses |
| **Advanced** | Complex Revit API automation, custom node development, Rhino.Inside.Revit integration | Jeremy Tammik's Building Coder blog; Dynamo developer documentation; Revit API documentation |
| **Expert** | Revit add-in development (C#), custom Generative Design solvers, enterprise-scale automation | Autodesk Developer Network; Forge/APS API; enterprise BIM automation case studies |

### 2.3 Python for AEC Pathway

| Level | Topics | Resources |
|-------|--------|-----------|
| **Beginner** | Python basics, rhinoscriptsyntax, GhPython, simple automation scripts | Rhino.Python tutorials (McNeel); Automate the Boring Stuff (general Python); Codecademy Python |
| **Intermediate** | RhinoCommon API, numpy/scipy, data processing (pandas), file I/O (JSON, CSV, IFC) | COMPAS documentation; IfcOpenShell tutorials; Real Python website |
| **Advanced** | Machine learning (scikit-learn, tensorflow), computational geometry (shapely, trimesh), custom tool development | Fast.ai courses; Towards Data Science AEC articles; COMPAS workshop materials |
| **Expert** | Building production-grade tools, web services, API development, contributing to open-source AEC projects | Python packaging, CI/CD, software engineering best practices; open-source contribution guides |

---

## 3. Domain-Specific Pathways

### 3.1 Structural Computation

**Goal:** Computational design with structural performance as a primary driver.

| Stage | Focus | Tools | Resources |
|-------|-------|-------|-----------|
| **Foundation** | Structural intuition: load paths, equilibrium, material behavior, structural typologies | Physical models, hand calculations | *Why Buildings Stand Up* (Salvadori), *Structure in Architecture* (Salvadori & Heller) |
| **Analysis** | FEA basics, beam/shell/solid elements, boundary conditions, load cases, result interpretation | Karamba3D, Kangaroo | Karamba3D manual and tutorials; Clemens Preisinger's workshops |
| **Form-finding** | Dynamic relaxation, thrust network analysis, force density method, graphic statics | Kangaroo, COMPAS TNA/AGS | Philippe Block's lectures (ETHZ); COMPAS tutorials; *Form and Forces* (Allen & Zalewski) |
| **Optimization** | Topology optimization, sizing optimization, shape optimization, multi-objective structural optimization | Millipede, Ameba, Karamba + Galapagos | Caitlin Mueller's lectures (MIT); Bendsoe & Sigmund *Topology Optimization* |
| **Advanced** | Nonlinear analysis, buckling, dynamic loading, ML for structural prediction | Sofistik, Abaqus, custom Python | University-level structural mechanics courses; research papers |

### 3.2 Environmental Simulation

**Goal:** Performance-driven design using environmental analysis feedback.

| Stage | Focus | Tools | Resources |
|-------|-------|-------|-----------|
| **Foundation** | Climate science basics, bioclimatic design principles, passive strategies, comfort metrics | Climate Consultant, Psychrometric charts | *Sun, Wind & Light* (Brown & DeKay), *Design with Climate* (Olgyay) |
| **Solar analysis** | Sun path diagrams, radiation analysis, shadow studies, solar access | Ladybug, Rhino Sun | Ladybug Tools tutorials; Chris Mackey's documentation |
| **Daylight** | Daylight factor, spatial daylight autonomy (sDA), annual sunlight exposure (ASE), glare | Honeybee (Radiance), ClimateStudio | LEED/WELL daylight criteria; IES LM-83; Honeybee tutorials |
| **Energy** | Building energy modeling, HVAC basics, envelope performance, energy use intensity (EUI) | Honeybee (EnergyPlus), DesignBuilder | ASHRAE Fundamentals; EnergyPlus documentation; OpenStudio tutorials |
| **Wind/CFD** | Wind comfort, natural ventilation, pressure coefficients, urban wind effects | Butterfly (OpenFOAM), Eddy3D | Blocken's urban physics lectures; OpenFOAM tutorials |
| **Advanced** | Coupled simulation, optimization with environmental objectives, urban microclimate | Multi-tool workflows, custom Python | SimAUD conference papers; Building Simulation journal |

### 3.3 Digital Fabrication

**Goal:** Design for manufacturing using computational tools.

| Stage | Focus | Tools | Resources |
|-------|-------|-------|-----------|
| **Foundation** | Manufacturing processes (CNC, laser, 3D printing, casting), material properties, tolerance | Shop access, material experiments | *Digital Fabrications* (Iwamoto), *Fabricating Architecture* (Sheil) |
| **2D fabrication** | Laser cutting, CNC routing, nesting, flat-pack design, kerf bending, living hinges | Rhino, Grasshopper, RhinoNest | Maker community tutorials; FabLab resources |
| **3D printing** | FDM, SLA, SLS processes; support structures; slicing; G-code; large-scale concrete printing | Silkworm, PrusaSlicer, custom GH | 3D Printing for Architecture (various); Emerging Objects projects |
| **Robotic fabrication** | Robot kinematics, toolpath planning, end-effector design, safety protocols | HAL Robotics, KUKA\|prc, COMPAS FAB | HAL Robotics tutorials; COMPAS FAB documentation; Gramazio Kohler publications |
| **Advanced** | Multi-robot coordination, adaptive fabrication (sensor feedback), novel material processes | Custom development, ROS integration | ETH Zurich NCCR dfab publications; ICD Stuttgart publications |

---

## 4. Key Books

### Foundational Theory

| Title | Author(s) | Year | Focus |
|-------|-----------|------|-------|
| *Animate Form* | Greg Lynn | 1999 | Digital morphogenesis, calculus-based form |
| *The Autopoiesis of Architecture* Vol. 1 & 2 | Patrik Schumacher | 2010, 2012 | Parametricism as architectural theory |
| *The Digital Turn in Architecture 1992-2012* | Mario Carpo (ed.) | 2012 | History and theory of digital design |
| *The Second Digital Turn* | Mario Carpo | 2017 | Big data, ML, and the second digital revolution |
| *Algorithmic Architecture* | Kostas Terzidis | 2006 | Rigorous framework for algorithmic design |
| *Architecture in the Digital Age* | Branko Kolarevic | 2003 | Digital manufacturing and mass customization |
| *Digital Culture in Architecture* | Antoine Picon | 2010 | Cultural implications of digital design |
| *The Architecture of Emergence* | Mike Weinstock | 2010 | Morphogenetic design and complex systems |

### Technical / Practice

| Title | Author(s) | Year | Focus |
|-------|-----------|------|-------|
| *AAD: Algorithms-Aided Design* | Arturo Tedeschi | 2014 | Grasshopper parametric strategies |
| *Parametric Design for Architecture* | Wassim Jabi | 2013 | Grasshopper and GenerativeComponents workflows |
| *Morphoecologies* | Michael Hensel, Achim Menges | 2006 | Material systems and environmental design |
| *Material Synthesis* | Achim Menges (AD) | 2015 | Physical and computational material design |
| *Form and Forces* | Edward Allen, Waclaw Zalewski | 2009 | Structural design with graphic statics |
| *Shell Structures for Architecture* | Sigrid Adriaenssens et al. (eds.) | 2014 | Form-finding and optimization of shells |
| *Scripting Cultures* | Mark Burry | 2011 | Programming cultures in architectural design |
| *Digital Fabrications* | Lisa Iwamoto | 2009 | Architectural fabrication techniques |
| *Topology Optimization* | Bendsoe, Sigmund | 2003 | Theory and methods of topology optimization |
| *The New Mathematics of Architecture* | Jane Burry, Mark Burry | 2010 | Mathematical concepts behind architectural geometry |

### Design Computation and AI

| Title | Author(s) | Year | Focus |
|-------|-----------|------|-------|
| *Architectural Intelligence* | Molly Wright Steenson | 2017 | History of AI in architecture (Negroponte, Alexander, Cedric Price) |
| *Design Computing and Cognition* | John Gero (ed.) | Various | Computational cognition in design |
| *Space Syntax* | Bill Hillier | 1996 | Graph-based analysis of spatial configuration |

---

## 5. Key Courses and Educational Programs

### Online Courses

| Course/Platform | Focus | Level | Cost |
|----------------|-------|-------|------|
| **ThinkParametric** | Grasshopper, Dynamo, environmental analysis, fabrication | Beginner-Advanced | Subscription ($29/month) |
| **Parametric House** | Grasshopper tutorials, algorithmic design | Beginner-Intermediate | Free (YouTube) + paid courses |
| **Mode Lab Grasshopper Primer** | Comprehensive Grasshopper fundamentals | Beginner | Free |
| **LinkedIn Learning (Lynda)** | Rhino, Grasshopper, Revit, Dynamo basics | Beginner | Subscription |
| **Coursera / edX** | General programming (Python, data science), some AEC-specific courses | Various | Free audit / paid certificate |
| **DesignMorphine** | Advanced computational design workshops | Intermediate-Advanced | Per workshop ($100-400) |
| **COMPAS Workshops** | COMPAS framework, structural design, robotic fabrication | Intermediate-Advanced | Usually free (academic) |
| **Ladybug Tools Academy** | Environmental analysis with Ladybug/Honeybee | Beginner-Advanced | Free (YouTube) |

### University Programs (Postgraduate)

| Program | University | Focus |
|---------|-----------|-------|
| **Design Research Laboratory (DRL)** | AA London | Generative design, material systems, urbanism |
| **Emergent Technologies & Design (EmTech)** | AA London | Material computation, structural morphology |
| **ICD/ITKE** | University of Stuttgart | Computational design and construction, robotic fabrication |
| **Master of Computational Design** | Carnegie Mellon University | Computational methods across design disciplines |
| **SMArchS Design Computation** | MIT | Design computation, AI, structural optimization |
| **IAAC** | Barcelona | Digital fabrication, smart cities, advanced architecture |
| **MAS DFAB** | ETH Zurich | Digital fabrication, robotic construction |
| **Bartlett RC** | UCL London | Design computation, interactive architecture |
| **SCI-Arc** | Los Angeles | Emerging technologies, speculative computation |
| **CITA** | Royal Danish Academy | Material and computational design |

---

## 6. Key Conferences

| Conference | Focus | Frequency | Community |
|-----------|-------|-----------|-----------|
| **ACADIA** | Association for Computer-Aided Design in Architecture | Annual | North America (primarily), global |
| **CAADRIA** | Computer-Aided Architectural Design Research in Asia | Annual | Asia-Pacific |
| **eCAADe** | Education and Research in CAAD in Europe | Annual | Europe |
| **SimAUD** | Simulation for Architecture and Urban Design | Annual | Simulation-focused, global |
| **IASS** | International Association for Shell and Spatial Structures | Annual | Structural computation, global |
| **RobArch** | Robotic Fabrication in Architecture | Biennial | Robotic fabrication, global |
| **Advances in Architectural Geometry (AAG)** | Geometry processing for architecture | Biennial | Geometric computation, global |
| **Fabricate** | Digital fabrication in architecture | Triennial | Fabrication, UCL/MIT/Stuttgart |
| **SmartGeometry** | Workshops + conference on computational design | Annual | Practitioner-focused, global |
| **Design Modelling Symposium (DMS)** | Computational design and modeling | Biennial | Berlin (UdK), academic |

---

## 7. Key Communities and Resources

### Online Communities

| Community | Platform | Focus |
|-----------|----------|-------|
| **McNeel Discourse Forum** | discourse.mcneel.com | Rhino + Grasshopper (extremely active, developers participate) |
| **Dynamo Forum** | forum.dynamobim.com | Dynamo + Revit computational workflows |
| **Speckle Community** | speckle.community | Interoperability, data exchange, automation |
| **COMPAS Forum** | forum.compas-framework.org | COMPAS framework, structural/fabrication computation |
| **r/architecture + r/parametricdesign** | Reddit | General discussion, sharing work |
| **Computational Design Discord** | Discord | Real-time chat, sharing, help |
| **Parametric Architecture** | Instagram/Web | Showcasing computational design projects |
| **Food4Rhino** | food4rhino.com | Plugin repository, reviews, discussions |

### Blogs and Websites

| Resource | Focus |
|----------|-------|
| **ParametricHouse.com** | Tutorials, resources, community for parametric design |
| **Designalyze.com** | Zach Downey's tutorials on Grasshopper and computational geometry |
| **TheBuildingCoder.typepad.com** | Jeremy Tammik's blog on Revit API development |
| **Proving Ground** | Nathan Miller's computational design practice and tools |
| **CORE studio (Thornton Tomasetti)** | Computational engineering practice and open-source tools |
| **DesignReform.net** | Tutorials and computational design resources |
| **GrasshopperDocs.com** | Community-sourced Grasshopper component documentation |

---

## 8. Portfolio Development Guidance

### What Computational Design Portfolios Should Demonstrate

A computational designer's portfolio must show not just beautiful outputs but the thinking, logic, and rigor behind the work. It should demonstrate:

1. **Design Intent:** Why computational methods were used — what question was being explored, what problem was being solved. Computation should serve a purpose, not be decoration.

2. **Process Documentation:** Show the Grasshopper definition (clean, organized, labeled), the data flow logic, the parameter space explored, and the decision points. Include annotated screenshots of definitions, not just rendered images.

3. **Parameter Space Exploration:** Show multiple variants generated by the system, not just the "hero shot." Demonstrate that the parametric model explores a meaningful design space.

4. **Analysis Integration:** If environmental or structural analysis was used, show the analysis results, how they influenced design decisions, and the feedback loop between analysis and geometry.

5. **Fabrication Awareness:** If applicable, show how the design was rationalized for fabrication — panelization strategy, material constraints, assembly sequence.

6. **Technical Skill Range:** Demonstrate breadth (multiple tools, analysis types, fabrication methods) and depth (one or two areas of specialization).

7. **Code Samples:** For advanced roles, include clean, documented code (Python scripts, C# components, custom plugins). Show that you can write code, not just connect nodes.

### Portfolio Structure Recommendations

| Section | Content | Length |
|---------|---------|--------|
| **Overview/Bio** | Who you are, what you specialize in, what drives your work | 1 page |
| **Featured Projects** (3-5) | Detailed case studies with process, analysis, output, fabrication | 4-8 pages each |
| **Technical Skills** | Tools matrix, programming languages, analysis capabilities | 1 page |
| **Quick Projects** (5-10) | Smaller explorations showing range | 1-2 pages each |
| **Code/Tools** | Custom tools, plugins, scripts developed | 2-4 pages |
| **Research/Publications** | If applicable: papers, conference presentations, teaching | 1-2 pages |

### Common Portfolio Mistakes

- **All surface, no substance:** Beautiful renders but no explanation of the computational logic
- **Tool showcase, not design showcase:** "I used Grasshopper" is not a design statement. Show what the tool enabled that wouldn't have been possible otherwise
- **No design intent:** Voronoi patterns and attractor fields without explaining why those methods serve the design problem
- **Spaghetti definitions:** Showing messy, unlabeled Grasshopper definitions as "proof of complexity" — this shows poor practice, not skill
- **No fabrication/reality connection:** Purely speculative computational geometry with no consideration of how it would be built, what it would cost, or how it would perform
- **Identical to tutorials:** Projects that are clearly tutorial reproductions. Modify, extend, and apply tutorial techniques to original design problems

---

## 9. Career Pathways

### Roles in Computational Design

| Role | Description | Typical Employer |
|------|-------------|------------------|
| **Computational Designer** | Creates parametric models, analysis workflows, and design tools for project teams | Architecture firms (ZHA, Foster, BIG, SOM, etc.) |
| **BIM Specialist/Manager** | Develops and manages computational BIM workflows, automation, and standards | Architecture/engineering firms, contractors |
| **Design Technology Specialist** | Builds custom tools, plugins, and automation for the firm | Large architecture/engineering firms |
| **Facade Consultant** | Computational facade design, panelization, environmental performance | Specialist consultancies (Front Inc, Eckersley O'Callaghan) |
| **Structural Computation Specialist** | Computational structural design, form-finding, optimization | Engineering firms (Arup AGU, BuroHappold SMART, Bollinger+Grohmann) |
| **Digital Fabrication Specialist** | Design-to-fabrication workflows, robotic programming, CNC toolpath | Fabrication workshops, research labs |
| **Software Developer (AEC)** | Building AEC software tools, plugins, platforms | Software companies (McNeel, Autodesk, Speckle, Hypar) |
| **Researcher** | Academic or industrial research in computational design methods | Universities, corporate research labs (Autodesk Research) |
| **Urban Computation Specialist** | Data-driven urbanism, GIS analysis, urban generation | Urban design firms, city planning departments |

### Salary Context (Approximate, varies greatly by location and firm size)

| Level | Role | Typical Range (USD, 2025) |
|-------|------|---------------------------|
| Entry (0-2 yrs) | Junior Computational Designer | $55,000-75,000 |
| Mid (3-5 yrs) | Computational Designer | $75,000-110,000 |
| Senior (5-10 yrs) | Senior Computational Designer / Design Technology Lead | $100,000-150,000 |
| Lead (10+ yrs) | Head of Design Technology / Computational Design Director | $130,000-200,000+ |
| Specialist | AEC Software Developer | $90,000-160,000 |

**Note:** Computational design skills command a premium over traditional architectural roles. Firms increasingly recognize that computational designers multiply the productivity and capability of entire teams.

---

## 10. Self-Assessment Checklist

Use this checklist to identify your current level and gaps in your computational design skills.

### Beginner Checkpoint

- [ ] Can explain the difference between parametric, generative, and algorithmic design
- [ ] Can build a Grasshopper definition with 20+ components from scratch
- [ ] Understands NURBS vs. mesh geometry
- [ ] Can use Number Sliders, Panels, and basic List operations
- [ ] Can create parametric surfaces (Loft, Sweep, Extrude) in Grasshopper
- [ ] Can use Divide Curve/Surface and evaluate points on geometry
- [ ] Understands the concept of data trees (even if struggles with them)
- [ ] Can bake geometry from Grasshopper to Rhino

### Intermediate Checkpoint

- [ ] Can debug data tree mismatches using Param Viewer
- [ ] Can write basic Python scripts in GhPython (loops, conditionals, functions)
- [ ] Can set up a Ladybug sun path and radiation analysis
- [ ] Can set up a basic Karamba3D structural model
- [ ] Can use Galapagos for single-objective optimization
- [ ] Can explain what a fitness function is and design one for a given problem
- [ ] Can use Kangaroo for basic physics simulation
- [ ] Understands surface panelization strategies
- [ ] Can exchange data between Grasshopper and at least one other platform

### Advanced Checkpoint

- [ ] Can write custom Grasshopper components in C# or complex GhPython libraries
- [ ] Can set up multi-objective optimization (Octopus) with meaningful objectives
- [ ] Can design and run a complete design-to-fabrication workflow
- [ ] Can use the COMPAS framework or equivalent for research-level computation
- [ ] Has contributed a plugin, tool, or significant tutorial to the community
- [ ] Can lead a computational design workflow on a real project
- [ ] Has deep expertise in at least one specialization (structure, environment, fabrication, urbanism)
- [ ] Can evaluate and select appropriate tools for a given design problem

### Expert Checkpoint

- [ ] Has developed novel methods or algorithms for computational design
- [ ] Has published research or presented at a major conference
- [ ] Can define computational design strategy for an organization
- [ ] Mentors junior computational designers effectively
- [ ] Can bridge between AEC-specific computation and broader CS/ML/data science
- [ ] Is recognized as a domain expert by peers in the field
- [ ] Has built tools or platforms used by others in the profession

---

*Learning computational design is a lifelong journey. The field evolves rapidly, and the best computational designers maintain a practice of continuous learning, experimentation, and community engagement.*
