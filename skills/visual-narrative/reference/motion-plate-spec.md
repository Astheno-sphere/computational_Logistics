# Motion plate spec: a mechanism and a city on one shared clock

Reverse-engineered from one 30 s, 720×900, 30 fps reference video ("Which streets need trees first?",
a simulated heat-wave day over New York). Method: a 1 fps contact sheet plus two full-resolution frames,
then pixel measurement. **Measured** = read from pixels. **Inferred** = judged by eye or from the
video's own caption; verify before relying on it.

Our rule still applies (`../SKILL.md`): borrow the *method*, never the artwork, handle, data or
trade dress. This file records structure and behaviour. The measured hex values are in the `ref`
column so a theme can reproduce the look; `ours` is the default.

## 1. Page: one idea, two scales, one clock (measured, 720×900 = our plate at ½ scale)

| Band | y (px) | What it holds |
|---|---|---|
| Hero A: mechanism | 20–300 | one street cross-section, full content width, no frame; clock + air temperature chip top-left; legend top-right |
| Value labels | 308–322 | three tracked caps labels, each value coloured by the shared ramp |
| Hero B: city | 338–640 | the same quantity on the whole map; place/date label top-left; scale bar bottom-left; legend bottom-right |
| Hairline rule | 666–669 | full content width |
| Kicker | 680–692 | caps, wide tracking, accent colour |
| Headline | 702–727 | caps bold, one word in the accent; cap height 25 px |
| Deck | 742–780 | two lines, sentence case, pitch 21 px |
| Method note | 791–813 | two lines, small, low contrast, pitch 13 px |
| Handle | 872–883 | bottom-left, small |

Margins: 34 px left and right (4.7 % of width); content spans x 34–685. The rule, headline,
deck and both heroes share that one column. Vertical gaps: rule→kicker 11, kicker→headline 10,
headline→deck 15, deck→note 11, note→handle ≈ 60. Hero A : Hero B ≈ 280 : 302, so the two scales get
near-equal weight; text takes the bottom 26 %.

At our 1440×1800 plate multiply every number by 2 (margin 68, rule at y 1332, headline cap height 50).

## 2. Type (inferred by eye; open-licence faces on Google Fonts)

| Role | Face | Setting |
|---|---|---|
| Kicker, headline, hero labels, legends | Montserrat, SemiBold to Bold (geometric, wide caps) | caps; kicker ≈ 14 px with ≈ 0.12 em tracking; headline ≈ 36 px, tracking ≈ +0.01 em; labels ≈ 14 px, ≈ 0.06 em |
| Deck, method note, handle | Inter, Regular (neutral grotesque) | deck ≈ 17–18 px; note ≈ 10–11 px; handle ≈ 11 px |

Two families only: a wide geometric caps face for everything that *labels*, a neutral grotesque for
everything that *explains*. Never bold body text; hierarchy comes from size, case, tracking and colour.

## 3. Colour (measured)

| Token | ref (video) | ours (default) | Use |
|---|---|---|---|
| ground | `#331C22` warm aubergine | `INK #10161B` | page; the ground is warm, never black |
| text | `#F4E4DC` cream | `PAPER #E8E1CF` | headline; deck one step down (≈ `#DCC4C4`) |
| note | `#8C7474` | PAPER at 55 % | method note, scale bar, handle ≈ `#C4ACAC` |
| accent | `#F4A43C` amber | `ACCENT #FF5B3A` | the one headline word, the kicker, the hot end of the ramp |
| cold | `#305E6D` steel teal | quiet blue-grey | "nothing happening" state |
| neutral mid | `#ABB9B1` | desaturated PAPER | midpoint of the diverging ramp |
| warm | `#EACDA8` → `#EC9B4C` → `#DE513E` | | hot side |
| green | `#7C9C6C` sage | | the intervention (tree); the only green on the page |
| slab | `#D4C4BC` | | structure lines (floors, kerb) |

### Colour behaviour (the part that carries the idea)
1. **One diverging ramp for the whole page**, cold teal → pale neutral → amber → red, used by the
   section, the map, the legends *and the numbers in the labels*. "ASPHALT 65 °C" is red because 65 is red
   on the ramp; "UNDER TREE 31 °C" is cream because 31 is near neutral.
2. **Cold is quiet, hot is loud.** At night the whole map is one flat teal and the flow lines nearly
   vanish; at 14:00 the same frame is saturated orange with bright red streaks. Saturation is the clock.
3. **The ramp midpoint is a light neutral, not white**, so on a dark ground neither tail glows by
   accident. Hot values are the only warm-saturated pixels, so the eye goes there.
4. **Two sibling legends, each stating its variable and unit** ("SECTION SURFACE °C 25→70", "MAP: SURFACE
   MINUS AIR, °C −6→+30"). The map ramp is a *difference* (so it can be diverging); the section is absolute.
5. **Accent used once per layer:** one headline word, the kicker, and the hot end of the data. No third use.

## 4. Motion grammar (measured from the contact sheet; 1 s of video ≈ 48 min of model time)

1. **A full day in 30 s**, 05:22 → 04:34, looping at the cool pre-dawn state so the loop seam is invisible.
2. **Clock + air temperature chip** and a **sun-arc dot** top-left of Hero A: the only chrome that moves
   every frame, and the reader's anchor.
3. **Flow made visible.** Both heroes carry thin cream streamlines: turbulent vortices in the section,
   a diagonal wind hatch over the map. Inferred technique: particle trails or line-integral convolution at
   low alpha, advected by the simulated field. Equivalent for us: agent trails (deck.gl TripsLayer) and
   edge flow density.
4. **Two-act structure.** Act 1 (≈ 05:00–20:30) the system heats up at city scale. Act 2 (≈ 21:00 to the
   end) the *same* map zooms to street scale and shows the **answer** as bright white marks
   (top 1 % priority streets) while the heat has drained away. The cause is shown first, the decision last.
5. **One simulated variable, one slider.** The only thing that changes is time; geography, framing and
   layout stay fixed within each act. No camera shake, no transitions other than the single zoom.

## 5. Mapping to our work

| Their element | Our equivalent |
|---|---|
| Street cross-section (mechanism at human scale) | a kerb and loading-bay section: van, cyclist, pedestrian, delivery window, emissions field |
| City map of the same quantity | Molde / Kristiansund network from `osm-network`, edges coloured by load or CO₂ |
| Day clock (05:22 → 04:34) | a delivery shift (`vrp-solve` route replay) or the pathway years 2025 → 2050 |
| Shared ramp | traffic load or CO₂ relative to 2025, diverging around "no change" |
| Priority streets in white at the end | the pinch-point corridors (plate 01) or the robust packages (A3) |
| Wind/heat flow lines | agent trails and edge flow density |
| Sage-green intervention | the policy lever, drawn once |

## 6. Gaps and risks
- **Fonts are inferred.** Confirm by rendering Montserrat/Inter and overlaying a frame before we claim a match.
- **Pixel numbers are from a compressed 720 px video**, so colours near edges are anti-aliased; the table uses
  the dominant clean pixels only, ±4 per channel.
- **Rendering cost is the real gap.** Their section is a 2D buoyant Navier-Stokes solve and the map a 30 m
  surface-energy simulation; we do not have an equivalent field solver. We can match layout, type, colour
  behaviour and two-act motion today; the vortex realism needs a solver or a particle-advection stand-in.
- **The caption's claims** (Landsat 8/9, Navier-Stokes) are the author's and are not verified here.
