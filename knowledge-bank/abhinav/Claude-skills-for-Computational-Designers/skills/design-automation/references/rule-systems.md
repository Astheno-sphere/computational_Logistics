# Rule-Based Design Systems: Deep Reference

This reference provides comprehensive coverage of rule-based design systems for AEC automation, from formal shape grammars through production rule engines to practical building code rule libraries.

---

## 1. Shape Grammar Formalism

### 1.1 Formal Definition

A shape grammar is a production system operating on shapes in Euclidean space. Formally defined as:

```
SG = (S, L, R, I, T)
where:
  S = finite set of shapes (geometric primitives: points, lines, planes, solids)
  L = finite set of labels (markers, annotations, control points)
  R = finite set of shape rules: (LHS → RHS) where LHS and RHS are labeled shapes
  I = initial labeled shape (axiom)
  T = transformation group (translation, rotation, scaling, reflection)
```

**Rule application**: A rule α → β applies to a shape C if a transformed copy of α (under T) can be found as a subshape of C. The rule replaces that subshape with the correspondingly transformed β.

**Key property**: Shape grammars operate by shape recognition (subshape detection), not by symbol matching. This is what distinguishes them from string grammars and makes them inherently geometric.

### 1.2 Types of Shape Grammars

**Parametric shape grammars**: Shapes carry parameters (dimensions, angles, proportions). Rules specify parameter relationships and constraints, not fixed dimensions.

```
Rule: Rectangle(w, h) → Rectangle(w/2, h) + Rectangle(w/2, h)
Constraint: w > 2 * min_room_width
```

**Set grammars**: Operate on sets of shapes rather than individual shapes. Useful for handling collections of building elements.

**Graph grammars**: Extend shape grammars to operate on labeled graphs. Nodes represent spatial entities; edges represent relationships (adjacency, containment, access).

**Weighted shape grammars**: Each rule has a probability weight governing its likelihood of selection. Enable stochastic generation of design variations.

### 1.3 Subshape Detection

The most computationally challenging aspect of shape grammars is detecting whether a shape α is a subshape of shape C under transformations T. This requires:

1. **Maximal line representation**: Represent shapes as sets of maximal line segments (lines that cannot be extended within the shape)
2. **Transformation search**: Find translation, rotation, and scaling that maps α into C
3. **Inclusion test**: Verify that every element of the transformed α lies within C

For rectilinear shapes (axis-aligned rectangles, common in floor plans), subshape detection simplifies to checking whether rectangle corners and edges of α align with those of C.

---

## 2. Shape Grammar Examples

### 2.1 Palladian Villa Grammar (Stiny & Mitchell, 1978)

The foundational example of shape grammars in architecture. Encodes the compositional logic of Andrea Palladio's villas as documented in the Quattro Libri (1570).

**Vocabulary**:
- Rectangular rooms of various proportions (1:1, 1:√2, 1:2, etc.)
- Porticos (loggia) with column orders
- Stairs
- Walls with openings

**Key rules**:

```
Rule 1: Initial grid
  [] → [3x3 grid of cells]

Rule 2: Room proportion assignment
  [cell(w,h)] → [room(w, h, proportion)]
  where proportion ∈ {1:1, 2:3, 1:√2, 3:4, 1:2}

Rule 3: Symmetry enforcement
  [room_left(p)] → [room_left(p) + room_right(p)]
  (right side mirrors left side about central axis)

Rule 4: Portico attachment
  [front_facade] → [front_facade + portico(width, depth, columns)]
  where columns ∈ {4, 6, 8}

Rule 5: Wall articulation
  [wall(room_a, room_b)] → [wall_with_opening(room_a, room_b, opening_type)]
  where opening_type ∈ {door, arch, colonnade}

Rule 6: Room subdivision
  [large_room(w, h)] → [room(w/2, h) | room(w/2, h)]
  Condition: w > 2 * min_room_width

Rule 7: Stair placement
  [cell_at_edge] → [stair(width, run, rise)]
  Condition: adjacent to circulation
```

**Generation process**:
1. Establish 3x3 (or 3x5) grid with bilateral symmetry
2. Assign room proportions following Palladio's preferred ratios
3. Place portico on principal facade
4. Subdivide rooms if needed
5. Place stairs and service rooms
6. Add wall openings connecting rooms
7. Apply facade articulation

**Result**: Generates plans recognizable as Palladian but not copies of existing villas. Demonstrates that style can be encoded computationally.

### 2.2 Prairie House Grammar (Koning & Eizenberg, 1981)

Encodes Frank Lloyd Wright's Prairie style houses (1900-1910).

**Characteristic features encoded**:
- Cruciform or pinwheel plan organization
- Horizontal emphasis (low-pitched hip roofs, banded windows)
- Central fireplace as spatial anchor
- Flowing open-plan living spaces
- Servant spaces (kitchen, service) separated from served spaces (living, dining)

**Key rules**:

```
Rule 1: Establish primary axis
  [site] → [site + primary_axis(direction)]

Rule 2: Cross-axis
  [primary_axis] → [primary_axis + secondary_axis(perpendicular)]

Rule 3: Zone assignment
  [quadrant(NE)] → [living_zone]
  [quadrant(NW)] → [dining_zone]
  [quadrant(SE)] → [service_zone]
  [quadrant(SW)] → [entry_zone]

Rule 4: Fireplace placement
  [axis_intersection] → [fireplace_mass(w, d)]

Rule 5: Roof articulation
  [zone] → [zone + hip_roof(overhang, pitch)]
  pitch: 15-25 degrees (low)
  overhang: 600-1200mm (deep)

Rule 6: Window banding
  [exterior_wall(length)] → [window_band(length * 0.6-0.8, sill_height)]
  sill_height: 600-900mm
```

### 2.3 Musgum Shell Grammar

Encodes the traditional Musgum (Mousgoum) catenary shell houses of Cameroon.

**Vocabulary**:
- Catenary shell profiles of varying height and base diameter
- Door openings with decorative surrounds
- Drainage channels (raised ribs on exterior)
- Compound arrangements (multiple shells connected)

**Key rules**:

```
Rule 1: Shell generation
  [base_circle(r)] → [catenary_shell(r, h)]
  where h = r * aspect_ratio, aspect_ratio ∈ [1.2, 2.0]

Rule 2: Opening placement
  [shell_base] → [shell_base + door_opening(w, h, orientation)]
  orientation: toward compound center or village street

Rule 3: Rib pattern
  [shell_surface] → [shell_surface + ribs(count, profile)]
  count: 8-16 meridional ribs
  profile: raised triangular section

Rule 4: Compound arrangement
  [shell_a, shell_b] → [shell_a + connecting_wall + shell_b]
  Condition: distance(a, b) < max_wall_length

Rule 5: Compound enclosure
  [compound(shells)] → [compound(shells) + perimeter_wall + entry_gate]
```

### 2.4 Facade Grammar Example

A practical grammar for generating facade variations:

```
Rule 1: Bay division
  [facade(W, H)] → [bay(W/n, H)] * n
  where n = floor(W / preferred_bay_width)

Rule 2: Floor division
  [bay(w, H)] → [floor(w, h)] * m
  where m = number_of_floors, h = floor_to_floor_height

Rule 3: Panel type assignment
  [floor(w, h)] → [panel(type, w, h)]
  where type ∈ {solid, glazed, mixed, spandrel}
  type selection based on: floor level, orientation, program behind

Rule 4: Opening placement
  [panel(solid, w, h)] → [panel_with_opening(w, h, opening_w, opening_h, sill)]
  opening_w ∈ [0.3*w, 0.8*w]
  opening_h ∈ [0.4*h, 0.85*h]

Rule 5: Shading device
  [panel_with_opening(south_facing)] → [panel_with_opening + shade(depth, type)]
  type ∈ {horizontal_louver, vertical_fin, egg_crate, perforated_screen}
  depth = f(latitude, cooling_degree_days)

Rule 6: Material assignment
  [panel(type)] → [panel(type, material, color)]
  material ∈ {precast_concrete, metal_panel, curtain_wall, masonry, terracotta}
```

---

## 3. Production Rule Engine Implementation

### 3.1 Rule Engine Architecture

A production rule engine consists of:

```
┌─────────────────────────────────────────┐
│              Rule Engine                │
│                                         │
│  ┌──────────┐  ┌───────────────────┐   │
│  │Working   │  │ Pattern Matching  │   │
│  │Memory    │──│ (Rete Network)    │   │
│  │(Facts)   │  │                   │   │
│  └──────────┘  └───────┬───────────┘   │
│                        │               │
│               ┌────────▼────────┐      │
│               │ Conflict Set    │      │
│               │ (Matched Rules) │      │
│               └────────┬────────┘      │
│                        │               │
│               ┌────────▼────────┐      │
│               │ Conflict        │      │
│               │ Resolution      │      │
│               └────────┬────────┘      │
│                        │               │
│               ┌────────▼────────┐      │
│               │ Rule Execution  │      │
│               │ (Actions)       │      │
│               └─────────────────┘      │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ Rule Base (Production Rules)     │  │
│  │ IF <conditions> THEN <actions>   │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 3.2 Implementation in Python

A minimal production rule engine for AEC:

```python
class Fact:
    """Represents a fact in working memory."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def matches(self, pattern):
        for key, value in pattern.items():
            if callable(value):
                if not value(getattr(self, key, None)):
                    return False
            elif getattr(self, key, None) != value:
                return False
        return True

class Rule:
    """A production rule: conditions → actions."""
    def __init__(self, name, conditions, actions, priority=0, salience=0):
        self.name = name
        self.conditions = conditions  # List of fact patterns
        self.actions = actions        # Callable(engine, matched_facts)
        self.priority = priority
        self.salience = salience
        self.fired = False

    def evaluate(self, facts):
        matched = []
        for pattern in self.conditions:
            matching_facts = [f for f in facts if f.matches(pattern)]
            if not matching_facts:
                return None
            matched.append(matching_facts[0])
        return matched

class RuleEngine:
    """Forward-chaining production rule engine."""
    def __init__(self):
        self.facts = []
        self.rules = []
        self.log = []

    def add_fact(self, **kwargs):
        fact = Fact(**kwargs)
        self.facts.append(fact)
        return fact

    def add_rule(self, name, conditions, actions, priority=0):
        rule = Rule(name, conditions, actions, priority)
        self.rules.append(rule)

    def run(self, max_iterations=1000):
        for iteration in range(max_iterations):
            # Find all rules whose conditions are satisfied
            conflict_set = []
            for rule in self.rules:
                if rule.fired:
                    continue
                matched = rule.evaluate(self.facts)
                if matched is not None:
                    conflict_set.append((rule, matched))

            if not conflict_set:
                break  # No more rules to fire

            # Conflict resolution: highest priority first
            conflict_set.sort(key=lambda x: x[0].priority, reverse=True)
            selected_rule, matched_facts = conflict_set[0]

            # Execute rule actions
            self.log.append(f"Firing: {selected_rule.name}")
            selected_rule.actions(self, matched_facts)
            selected_rule.fired = True

        return self.log
```

### 3.3 Example: Building Code Rule Engine

```python
engine = RuleEngine()

# Add building facts
engine.add_fact(type="building", occupancy="B",
                area=1850, height=23.5, stories=6,
                sprinklered=True)
engine.add_fact(type="floor", level=1, area=1850,
                occupancy="B", exits=3, exit_width_mm=3600)

# Add rules
engine.add_rule(
    name="occupant_load_business",
    conditions=[{"type": "floor", "occupancy": "B"}],
    actions=lambda eng, facts: eng.add_fact(
        type="occupant_load",
        floor=facts[0].level,
        load=int(facts[0].area / 9.3)  # 9.3 m2/person for Business
    ),
    priority=10
)

engine.add_rule(
    name="min_exits_check",
    conditions=[{"type": "occupant_load",
                 "load": lambda x: x is not None}],
    actions=lambda eng, facts: eng.add_fact(
        type="compliance_check",
        rule="min_exits",
        required=2 if facts[0].load <= 500 else (3 if facts[0].load <= 1000 else 4),
        status="PASS"  # Would compare with actual exits
    ),
    priority=5
)

results = engine.run()
```

### 3.4 Rete Algorithm for Efficient Pattern Matching

The Rete algorithm (Forgy, 1982) avoids re-evaluating all rules when a single fact changes:

1. **Alpha network**: Tests single-fact conditions. Each condition creates an alpha node that filters facts. Alpha memories store facts passing each test.
2. **Beta network**: Joins multiple alpha memories to test multi-fact conditions. Beta nodes perform pair-wise joins. Beta memories store partial matches.
3. **Conflict set**: Terminal nodes of the beta network produce complete matches (rules ready to fire).

**Advantage**: When a fact changes, only affected alpha and beta nodes re-evaluate. For large rule sets (hundreds of building code rules), Rete is orders of magnitude faster than naive evaluation.

---

## 4. Decision Table Design

### 4.1 Decision Table Structure

Decision tables compactly represent complex conditional logic:

```
┌─────────────────────────────────────────────────────────────┐
│ FIRE RESISTANCE RATING DECISION TABLE (IBC Table 601)       │
├──────────────────────┬──────────────────────────────────────┤
│ Conditions           │ Construction Type                     │
│                      │  IA    IB    IIA   IIB   IIIA  IIIB │
├──────────────────────┼──────────────────────────────────────┤
│ Structural frame     │  3hr   2hr   1hr   0hr   1hr   0hr  │
│ Bearing walls (ext)  │  3hr   2hr   1hr   0hr   2hr   2hr  │
│ Bearing walls (int)  │  3hr   2hr   1hr   0hr   1hr   0hr  │
│ Floor construction   │  2hr   2hr   1hr   0hr   1hr   0hr  │
│ Roof construction    │  1.5hr 1hr   1hr   0hr   1hr   0hr  │
└──────────────────────┴──────────────────────────────────────┘
```

### 4.2 Decision Table Implementation

```python
class DecisionTable:
    """Implements a decision table for rule-based lookups."""

    def __init__(self, conditions, actions, rules):
        self.conditions = conditions  # List of condition names
        self.actions = actions        # List of action names
        self.rules = rules            # List of {condition_values: action_values}

    def evaluate(self, inputs):
        for rule in self.rules:
            match = True
            for cond in self.conditions:
                expected = rule.get(cond)
                actual = inputs.get(cond)
                if expected == "*":  # Wildcard
                    continue
                if callable(expected):
                    if not expected(actual):
                        match = False; break
                elif expected != actual:
                    match = False; break
            if match:
                return {a: rule[a] for a in self.actions}
        return None

# Example: Occupant load factor table
occ_load_table = DecisionTable(
    conditions=["occupancy_type", "use"],
    actions=["load_factor_m2"],
    rules=[
        {"occupancy_type": "A", "use": "fixed_seating", "load_factor_m2": 0.65},
        {"occupancy_type": "A", "use": "standing", "load_factor_m2": 0.46},
        {"occupancy_type": "A", "use": "unconcentrated", "load_factor_m2": 1.4},
        {"occupancy_type": "B", "use": "*", "load_factor_m2": 9.3},
        {"occupancy_type": "E", "use": "classroom", "load_factor_m2": 1.9},
        {"occupancy_type": "M", "use": "ground_floor", "load_factor_m2": 2.8},
        {"occupancy_type": "M", "use": "upper_floor", "load_factor_m2": 5.6},
        {"occupancy_type": "R", "use": "*", "load_factor_m2": 18.6},
        {"occupancy_type": "S", "use": "*", "load_factor_m2": 18.6},
    ]
)
```

---

## 5. Rule Conflict Resolution Strategies

### 5.1 Priority-Based Resolution

Assign explicit priority values to rules. When multiple rules match, the highest priority rule fires first.

**Priority assignment guidelines for AEC**:
- Life safety rules: Priority 100 (always override)
- Structural integrity: Priority 90
- Building code mandatory: Priority 80
- Accessibility requirements: Priority 70
- Energy code: Priority 60
- Zoning requirements: Priority 50
- Project-specific mandatory: Priority 40
- Best practice / rules of thumb: Priority 20
- Aesthetic preferences: Priority 10

### 5.2 Specificity-Based Resolution

More specific rules override general rules:

```
General rule: IF occupancy == "Business" THEN exit_width_factor = 5.0 mm/person
Specific rule: IF occupancy == "Business" AND sprinklered == True THEN exit_width_factor = 3.8 mm/person

The specific rule wins because it matches more conditions.
```

### 5.3 Jurisdictional Hierarchy

Building codes have a hierarchy that must be respected:

```
Federal (ADA, OSHA) — override all
  └── State building code (often based on IBC with amendments)
       └── Local building code (city/county amendments)
            └── Local zoning ordinance
                 └── Project-specific requirements (client brief)
                      └── Design standards (firm standards, best practices)
```

When rules conflict across jurisdictional levels, the higher-level rule prevails, except when the lower level is more restrictive (building codes are minimum standards; local codes may exceed them).

### 5.4 Temporal Resolution

When rules from different code editions conflict:

- Apply the code edition in effect at the time of permit application
- For existing buildings: may apply code at time of original construction for existing elements, current code for new elements
- Track code edition metadata with every rule

### 5.5 Constraint Relaxation

When hard constraints conflict and no solution exists:

1. Identify the minimum set of constraints causing infeasibility
2. Present conflicting constraints to the designer
3. Allow designer to relax selected constraints (with justification)
4. Document all relaxations in the compliance report (variance requests)

---

## 6. Building Code Rule Libraries

### 6.1 IBC Egress Rules

```yaml
# IBC Chapter 10: Means of Egress (2021 edition)

egress_rules:
  occupant_load:
    - condition: "floor has defined occupancy and area"
      action: "occupant_load = floor_area / load_factor[occupancy]"
      reference: "IBC 1004.5"

  number_of_exits:
    - condition: "occupant_load <= 500"
      action: "min_exits = 2"
      reference: "IBC 1006.2.1"
    - condition: "500 < occupant_load <= 1000"
      action: "min_exits = 3"
      reference: "IBC 1006.2.1"
    - condition: "occupant_load > 1000"
      action: "min_exits = 4"
      reference: "IBC 1006.2.1"

  exit_separation:
    - condition: "2 exits required"
      action: "min_separation = diagonal_distance / 2"
      note: "1/3 diagonal if sprinklered"
      reference: "IBC 1007.1.1"

  travel_distance:
    - condition: "occupancy == 'B' AND sprinklered"
      action: "max_travel = 90m (300ft)"
      reference: "IBC 1017.2"
    - condition: "occupancy == 'B' AND NOT sprinklered"
      action: "max_travel = 60m (200ft)"
      reference: "IBC 1017.2"
    - condition: "occupancy == 'R' AND sprinklered"
      action: "max_travel = 75m (250ft)"
      reference: "IBC 1017.2"

  corridor_width:
    - condition: "occupant_load >= 50"
      action: "min_corridor_width = 1120mm (44in)"
      reference: "IBC 1020.2"
    - condition: "occupant_load < 50 AND occupancy != 'I'"
      action: "min_corridor_width = 910mm (36in)"
      reference: "IBC 1020.2"

  stair_width:
    - condition: "occupant_load > 50 AND sprinklered"
      action: "min_stair_width = max(1120mm, occupant_load * 5.1mm)"
      reference: "IBC 1011.2"
    - condition: "occupant_load <= 50"
      action: "min_stair_width = 910mm"
      reference: "IBC 1011.2"

  door_width:
    - condition: "egress door"
      action: "min_clear_width = 815mm (32in)"
      note: "max leaf width 1220mm (48in)"
      reference: "IBC 1010.1.1"

  dead_end_corridor:
    - condition: "sprinklered"
      action: "max_dead_end = 15m (50ft)"
      reference: "IBC 1020.4"
    - condition: "NOT sprinklered"
      action: "max_dead_end = 6m (20ft)"
      reference: "IBC 1020.4"

  common_path:
    - condition: "occupancy in ['B', 'F', 'M', 'S', 'U'] AND sprinklered"
      action: "max_common_path = 30m (100ft)"
      reference: "IBC 1006.2.1"
    - condition: "occupancy == 'R' AND sprinklered"
      action: "max_common_path = 38m (125ft)"
      reference: "IBC 1006.2.1"
```

### 6.2 ADA Accessibility Rules

```yaml
# ADA/ABA Accessibility Guidelines (2010)

accessibility_rules:
  accessible_route:
    - rule: "min_clear_width"
      value: "915mm (36in)"
      reference: "ADA 403.5.1"
    - rule: "passing_space"
      value: "1525mm x 1525mm every 60m"
      reference: "ADA 403.5.3"
    - rule: "max_running_slope"
      value: "1:20 (5%)"
      note: "Greater slope = ramp"
      reference: "ADA 403.3"
    - rule: "max_cross_slope"
      value: "1:48 (2.08%)"
      reference: "ADA 403.3"

  ramps:
    - rule: "max_slope"
      value: "1:12 (8.33%)"
      reference: "ADA 405.2"
    - rule: "max_rise_per_run"
      value: "760mm (30in)"
      reference: "ADA 405.6"
    - rule: "min_width"
      value: "915mm (36in) clear between handrails"
      reference: "ADA 405.5"
    - rule: "landing_length"
      value: "1525mm (60in) min"
      reference: "ADA 405.7"
    - rule: "handrails"
      value: "both sides, 865-965mm (34-38in) height"
      reference: "ADA 405.8"

  doors:
    - rule: "min_clear_width"
      value: "815mm (32in) clear"
      reference: "ADA 404.2.3"
    - rule: "maneuvering_clearance_pull_side"
      value: "1525mm depth, 460mm latch side"
      reference: "ADA 404.2.4"
    - rule: "maneuvering_clearance_push_side"
      value: "1220mm depth, 305mm latch side"
      reference: "ADA 404.2.4"
    - rule: "threshold_height"
      value: "max 13mm (0.5in)"
      reference: "ADA 404.2.5"
    - rule: "hardware"
      value: "operable with one hand, no tight grasping or twisting"
      reference: "ADA 404.2.7"

  turning_space:
    - rule: "circular"
      value: "1525mm (60in) diameter"
      reference: "ADA 304.3.1"
    - rule: "t_shaped"
      value: "1525mm x 1525mm with 915mm arms"
      reference: "ADA 304.3.2"

  reach_ranges:
    - rule: "forward_unobstructed"
      value: "380-1220mm (15-48in)"
      reference: "ADA 308.2"
    - rule: "side_unobstructed"
      value: "380-1220mm (15-48in)"
      reference: "ADA 308.3"

  toilet_rooms:
    - rule: "wheelchair_accessible_stall_size"
      value: "1525mm x 1525mm (60x60in) min"
      reference: "ADA 604.8.1.1"
    - rule: "water_closet_centerline"
      value: "455-460mm (18in) from side wall"
      reference: "ADA 604.2"
    - rule: "grab_bars"
      value: "side: 1065mm long, 305mm from rear wall; rear: 915mm long"
      reference: "ADA 604.5"
    - rule: "lavatory_knee_clearance"
      value: "685mm (27in) min height, 205mm (8in) min depth"
      reference: "ADA 606.2"
```

### 6.3 Fire Code Rules

```yaml
# Fire safety rules (IBC-based)

fire_safety_rules:
  construction_type:
    - condition: "type_IA"
      structural_frame: "3hr"
      bearing_walls_ext: "3hr"
      floor: "2hr"
      roof: "1.5hr"
    - condition: "type_IIA"
      structural_frame: "1hr"
      bearing_walls_ext: "1hr"
      floor: "1hr"
      roof: "1hr"

  fire_area_limits:
    - condition: "type_IIA, occupancy_B, sprinklered"
      max_area: "3700 m2 per floor (with sprinkler increase)"
      max_height: "55m"
      max_stories: "12"
      reference: "IBC Table 506.2"

  fire_barriers:
    - condition: "occupancy_separation_required"
      action: "provide fire barrier between occupancies"
      ratings:
        - "B to M: 1hr (sprinklered), 2hr (unsprinklered)"
        - "B to R: 2hr"
        - "B to S: 1hr (sprinklered)"
      reference: "IBC Table 508.4"

  fire_walls:
    - condition: "building exceeds allowable area"
      action: "divide with fire walls to create separate buildings"
      min_rating: "2hr for all types except IA (3hr)"
      reference: "IBC 706"

  corridor_fire_rating:
    - condition: "occupancy_B, sprinklered"
      rating: "0hr (no rating required)"
      reference: "IBC Table 1020.1"
    - condition: "occupancy_R, sprinklered"
      rating: "0.5hr"
      reference: "IBC Table 1020.1"
    - condition: "occupancy_I, sprinklered"
      rating: "1hr"
      reference: "IBC Table 1020.1"

  sprinkler_coverage:
    - condition: "light_hazard"
      max_area_per_head: "18.6 m2 (200 ft2)"
      max_spacing: "4.6m (15ft)"
    - condition: "ordinary_hazard_1"
      max_area_per_head: "12.1 m2 (130 ft2)"
      max_spacing: "4.6m (15ft)"
```

---

## 7. Rule Testing and Validation

### 7.1 Test Case Design for Building Code Rules

Every rule in the library should have associated test cases:

```python
class RuleTest:
    def __init__(self, name, inputs, expected_output, rule_ref):
        self.name = name
        self.inputs = inputs
        self.expected = expected_output
        self.rule_ref = rule_ref

# Test cases for occupant load calculation
tests = [
    RuleTest(
        "business_occupant_load",
        {"occupancy": "B", "area_m2": 930},
        {"occupant_load": 100},
        "IBC 1004.5"
    ),
    RuleTest(
        "assembly_fixed_seating",
        {"occupancy": "A", "use": "fixed_seating", "seats": 350},
        {"occupant_load": 350},
        "IBC 1004.4"
    ),
    RuleTest(
        "educational_classroom",
        {"occupancy": "E", "use": "classroom", "area_m2": 75},
        {"occupant_load": 39},
        "IBC 1004.5"
    ),
]
```

### 7.2 Validation Against Known Projects

Validate the rule engine by running it against real projects with known compliance outcomes:

1. Model a completed, code-compliant building in the rule engine
2. Run all applicable rules
3. Verify that all checks pass
4. Intentionally introduce violations (reduce exit width, increase travel distance)
5. Verify that the rule engine correctly detects each violation
6. Compare rule engine output with the original code review comments

### 7.3 Edge Case Testing

Test boundary conditions and edge cases:

- Occupant load exactly at threshold (500, 1000)
- Travel distance exactly at limit
- Mixed-occupancy buildings (most complex code interactions)
- Existing buildings with grandfather clause
- Additions and alterations (partial compliance)
- Performance-based alternatives (when prescriptive rules do not apply)

### 7.4 Regression Testing

When rules are updated (new code edition, local amendments):

1. Run all existing test cases against updated rules
2. Identify which tests now fail (expected, due to changed requirements)
3. Update expected values for changed requirements
4. Add new test cases for new rules
5. Verify backward compatibility where required (existing buildings under old code)

---

## 8. Maintenance of Rule Sets

### 8.1 Code Update Tracking

Building codes are updated on a regular cycle (IBC every 3 years: 2018, 2021, 2024):

- Track code edition in every rule's metadata
- When new edition is published, create a new rule set version
- Maintain old versions for projects permitted under previous editions
- Document all changes between editions (IBC publishes a "Significant Changes" document)

### 8.2 Rule Metadata Schema

```yaml
rule:
  id: "IBC-2021-1006.2.1-001"
  code: "IBC"
  edition: "2021"
  section: "1006.2.1"
  title: "Minimum Number of Exits"
  category: "egress"
  type: "prescriptive"
  jurisdiction: "federal"
  effective_date: "2021-01-01"
  supersedes: "IBC-2018-1006.2.1-001"
  conditions:
    - variable: "occupant_load"
      operator: ">"
      value: 500
  actions:
    - variable: "min_exits"
      value: 3
  exceptions:
    - "IBC 1006.2.1 Exception 1: ..."
  notes: "Applies to each floor, not to total building"
  test_cases: ["test_001", "test_002", "test_003"]
  last_validated: "2024-03-15"
  validated_by: "JSmith"
```

### 8.3 Local Amendment Management

Local jurisdictions amend the model code. Managing local amendments requires:

1. **Base code**: IBC (or applicable model code) as the foundation rule set
2. **Amendment overlay**: Local amendments stored as modifications to base rules
3. **Composite rule set**: Base + amendments = jurisdiction-specific rule set
4. **Amendment tracking**: Each amendment references the section it modifies, the jurisdiction, and the effective date

```python
class JurisdictionRuleSet:
    def __init__(self, base_code, jurisdiction):
        self.base = base_code
        self.amendments = load_amendments(jurisdiction)
        self.composite = self.merge()

    def merge(self):
        rules = dict(self.base.rules)
        for amendment in self.amendments:
            if amendment.action == "modify":
                rules[amendment.section] = amendment.modified_rule
            elif amendment.action == "add":
                rules[amendment.section] = amendment.new_rule
            elif amendment.action == "delete":
                del rules[amendment.section]
        return rules
```

### 8.4 Rule Deprecation and Versioning

- Use semantic versioning for rule sets: MAJOR.MINOR.PATCH
- MAJOR: New code edition (2018 → 2021)
- MINOR: Local amendment added or modified
- PATCH: Bug fix in rule logic (no change in intent)
- Deprecated rules are never deleted; they are marked as superseded with a reference to the replacement
- All rule changes are logged with timestamps and rationale

### 8.5 Quality Assurance for Rule Libraries

- **Peer review**: Every rule change reviewed by a licensed professional
- **Cross-reference check**: Verify that rules reference the correct code section and edition
- **Consistency check**: Ensure no contradictions between rules (e.g., two rules specifying different exit widths for the same condition)
- **Completeness check**: Verify that all applicable code sections are represented
- **Automated testing**: Run full test suite after every change
- **Annual audit**: Review entire rule set against current code text annually
