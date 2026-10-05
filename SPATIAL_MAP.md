ANA — Spatial Map & MapLibre MCP Implementation Directive
ROLE
You are ANA, an autonomous development agent built on top of Hermes Agent.
You are responsible for developing, maintaining, and continuously improving your own dashboard and its supporting infrastructure.
The dashboard is not merely a chat interface. It is ANA's operational interface.
One of the existing dashboard modules is:
SPATIAL MAP
The current SPATIAL MAP panel already exists and currently uses an Esri basemap.
Your task is to evolve this existing SPATIAL MAP into an agent-controllable, extensible geospatial workspace using MapLibre and the CodeStorm-Hub/maplibre_mcp MCP implementation.
Do not unnecessarily rebuild the existing dashboard.
First inspect the existing implementation and preserve working functionality.

PRIMARY OBJECTIVE
Transform the existing:
SPATIAL MAP
└── Esri Basemap
into:
SPATIAL MAP
├── MapLibre rendering engine
├── Existing Esri basemap capability
├── Map layers
├── GeoJSON/vector data
├── Feature selection
├── Feature highlighting
├── Camera control
├── Layer visibility control
├── Spatial filtering
├── Viewport/bounds calculation
├── Map state
├── Map interaction state
└── ANA agent control
ANA must eventually be able to understand the current state of the map and manipulate the map through tools rather than relying on manual operator interaction.

IMPORTANT ARCHITECTURAL PRINCIPLE
Do NOT make Hermes/ANA directly manipulate frontend implementation details.
ANA should operate through semantic map capabilities.
Bad:
map.flyTo(...)
map.setFilter(...)
document.querySelector(...)
Preferred:
map_get_state()
map_set_view(...)
map_fit_bounds(...)
map_select_feature(...)
map_highlight_features(...)
map_toggle_layer(...)
map_set_filter(...)
map_clear_selection()
The implementation should abstract frontend details behind a map-control interface.

EXISTING DASHBOARD
Before modifying anything:
    1. Inspect the existing ana-hermes-agent project.
    2. Identify the dashboard application.
    3. Identify the SPATIAL MAP implementation.
    4. Identify the current Esri basemap integration.
    5. Identify the frontend framework.
    6. Identify state-management architecture.
    7. Identify existing API/WebSocket/event infrastructure.
    8. Identify whether a map abstraction already exists.
    9. Identify existing MCP configuration.
    10. Identify the Hermes configuration used by ANA.
Do not assume the framework or architecture.
Inspect the repository first.

MAPLIBRE MCP
Use:
CodeStorm-Hub/maplibre_mcp
as the primary MapLibre MCP foundation.
Repository:
https://github.com/CodeStorm-Hub/maplibre_mcp
Do not create a duplicate implementation of functionality that this MCP already provides.
First determine:
    • available tools
    • tool names
    • tool arguments
    • transport mechanism
    • installation mechanism
    • runtime requirements
    • supported MapLibre functionality
    • documentation/specification tools
    • viewport tools
    • PMTiles support
    • Martin support
    • PostGIS/MVT support
    • Flutter/Dart support
    • style-related tools
Use the repository's current documentation rather than relying on assumptions.

MCP INTEGRATION
Integrate the MapLibre MCP into ANA/Hermes according to Hermes' actual MCP configuration mechanism.
Do not invent configuration formats.
Inspect the existing Hermes installation and determine the correct configuration location.
After configuration:
    1. Start the MCP server.
    2. Verify connectivity.
    3. Verify that Hermes discovers the MCP.
    4. Enumerate available tools.
    5. Test at least one safe/read-only tool.
    6. Confirm that the MCP does not interfere with existing ANA tools.
Document the resulting configuration.

SPATIAL MAP ABSTRACTION
Create a clean internal abstraction between ANA and the frontend map.
Conceptually:
ANA
 │
 │ semantic commands
 ▼
Map Control Interface
 │
 ├── MapLibre MCP
 └── Dashboard Map Adapter
          │
          ▼
       MapLibre
          │
          ▼
    SPATIAL MAP
The exact implementation is determined after repository inspection.
Do not blindly copy this diagram into code.

REQUIRED MAP CAPABILITIES
The architecture should support the following capabilities.
1. Map State
ANA should be able to obtain:
map_get_state()
State should ideally include:
center
zoom
bearing
pitch
bounds
active_basemap
visible_layers
selected_feature
highlighted_features
active_filter
viewport
Only include values actually supported by the implementation.

2. Camera Control
Support semantic operations equivalent to:
map_set_center(latitude, longitude)
map_set_zoom(zoom)
map_set_view(center, zoom, bearing, pitch)
map_fit_bounds(bounds)
map_reset_view()
The exact tool design may differ depending on the MCP and frontend architecture.

3. Layer Control
ANA should eventually be able to reason about layers:
map_get_layers()
map_toggle_layer(layer_id, visible)
map_set_layer_visibility(layer_id, visible)
map_set_layer_opacity(layer_id, opacity)
Do not expose unnecessary low-level APIs.

4. Feature Selection
Support:
map_select_feature(feature_id)
map_clear_selection()
map_get_selected_feature()
Selection should be synchronized between:
Map
↕
Dashboard state
↕
ANA

5. Feature Highlighting
Support highlighting of one or multiple spatial objects:
map_highlight_feature(feature_id)
map_highlight_features(feature_ids)
map_clear_highlights()
The visual treatment should be configurable.
Do not hard-code business-specific colors unless the existing dashboard design system already defines them.

6. Spatial Filtering
The map should eventually support semantic filtering:
map_set_filter(...)
map_clear_filter(...)
For example:
show only active features
show only selected region
show only features matching a property
show only polygons belonging to a specific administrative unit
Keep filtering logic separate from rendering logic.

BASEMAP REQUIREMENT
The current dashboard uses an Esri basemap.
Do NOT remove the Esri basemap simply because MapLibre is introduced.
Instead, investigate how the current Esri source is implemented and determine whether it can be represented cleanly within the MapLibre architecture.
The desired architecture should allow future basemap switching:
SPATIAL MAP
│
├── Esri
├── OpenStreetMap
├── Satellite
├── Terrain
└── Other compatible sources
The active basemap should become part of map state.
If licensing, attribution, token, or technical constraints exist, document them.
Never remove required attribution.

DATA ARCHITECTURE
Separate:
DATA
from:
MAP RENDERING
The map should not become the business-data backend.
Conceptually:
Business/Data Layer
        │
        ▼
GeoJSON / Vector Tiles / MVT / API
        │
        ▼
MapLibre
        │
        ▼
SPATIAL MAP
This will allow ANA to later connect the map to arbitrary projects.
Do not hard-code SIMOGE-specific schemas into the generic MapLibre layer.

ANA SEMANTIC CONTROL
The ultimate goal is that ANA can understand natural language instructions such as:
"Zoom ke area ini."

"Tampilkan layer petak."

"Sembunyikan layer penyadap."

"Fokuskan peta ke feature ini."

"Highlight semua feature hasil query."

"Reset tampilan peta."

"Tampilkan hanya objek yang memenuhi filter ini."
ANA should translate these into structured tool operations.
Do not implement natural-language parsing manually if Hermes' agent/tool calling mechanism already handles this.

DASHBOARD ↔ AGENT SYNCHRONIZATION
The map must work in both directions.
Operator → Map
Operator clicks feature
        ↓
MapLibre
        ↓
Dashboard state
        ↓
ANA can observe state
ANA → Map
ANA calls tool
        ↓
Map Control
        ↓
Dashboard state
        ↓
MapLibre
        ↓
Visual update
The two-way synchronization is mandatory for the long-term architecture.

MAP EVENT MODEL
Inspect the existing application and determine the appropriate event mechanism.
Potential events include:
MAP_READY
MAP_MOVED
MAP_ZOOM_CHANGED
MAP_CLICK
MAP_FEATURE_SELECTED
MAP_FEATURE_HOVERED
MAP_LAYER_CHANGED
MAP_VIEW_CHANGED
MAP_STYLE_CHANGED
MAP_FILTER_CHANGED
Only implement events that are useful and compatible with the actual application.
Avoid unnecessary event traffic.

AGENT SAFETY
Map-control tools should distinguish between:
Read operations
Examples:
get map state
get layers
get selected feature
get viewport
and:
Mutating operations
Examples:
change camera
toggle layer
change filter
select feature
change style
Potentially destructive operations must require appropriate confirmation if they can modify persistent data rather than merely visual state.
Pure visual operations such as zooming or highlighting do not require operator confirmation.

GENERIC DESIGN
Do not make the MapLibre integration specific to one business.
The architecture must support:
Project A
Project B
Project C
SIMOGE
future projects
The map layer should know about geospatial objects.
The business layer should know what those objects mean.
For example:
Generic:

feature_id
geometry
properties
layer_id

Business:

petak
penyadap
aktivitas
regional
KPH
BKPH
RPH
TPG
Do not mix the two unnecessarily.

DEVELOPMENT PROCESS
Follow this sequence.
PHASE 1 — DISCOVERY
Inspect:
ana-hermes-agent/
Find:
    • dashboard source
    • SPATIAL MAP component
    • Esri integration
    • frontend framework
    • state management
    • server/backend
    • MCP configuration
    • Hermes configuration
    • existing agent communication mechanism
Produce a short architecture report before making substantial changes.

PHASE 2 — MCP INSTALLATION
Install/configure:
CodeStorm-Hub/maplibre_mcp
using its current documented method.
Verify:
Hermes
   ↓
MCP
   ↓
MapLibre MCP
works correctly.

PHASE 3 — MAP ADAPTER
Create or extend a map abstraction layer.
The adapter should isolate:
ANA
from:
MapLibre implementation
Do not put MCP-specific logic throughout UI components.

PHASE 4 — MAP STATE
Implement a canonical map state.
The frontend should have one authoritative representation of:
center
zoom
bearing
pitch
bounds
layers
selection
highlight
filter
basemap
Avoid duplicated state.

PHASE 5 — CONTROL
Implement the minimum viable semantic controls:
get state
set view
fit bounds
select feature
highlight feature
toggle layer
clear selection
clear highlights
Test every capability independently.

PHASE 6 — DASHBOARD INTEGRATION
Integrate the controls into the existing:
SPATIAL MAP
without breaking:
    • existing layout
    • Esri basemap
    • responsive behavior
    • existing HUD
    • existing widgets
    • existing agent chat

PHASE 7 — AGENT TEST
Perform real end-to-end tests.
Examples:
Test 1:
"Show me the current map state."

Test 2:
"Zoom to this coordinate."

Test 3:
"Fit the map to these bounds."

Test 4:
"Highlight this feature."

Test 5:
"Hide this layer."

Test 6:
"Reset the map."
Verify that the actual map visibly changes.
Do not consider the implementation complete merely because the MCP tool returns successfully.
The visual result must be verified.

UI/UX REQUIREMENTS
The SPATIAL MAP should remain visually consistent with ANA's existing dashboard.
Do not replace the existing visual language.
Map controls should feel native to the dashboard.
Avoid exposing technical MCP concepts to normal operators.
The operator should see:
MAP
Layers
Basemap
Zoom
Search
Selection
Filters
not:
MCP
tool call
JSON-RPC
MCP server
Technical diagnostics may exist in developer/debug mode.

OBSERVABILITY
Create useful logs for:
MCP connection
tool invocation
map command
map state change
frontend map event
errors
Avoid logging sensitive data unnecessarily.
Include correlation IDs where practical.

ERROR HANDLING
If:
MapLibre MCP unavailable
the dashboard must not completely fail.
The SPATIAL MAP should remain usable manually whenever possible.
If an agent command fails:
ANA
 ↓
Tool failure
 ↓
Human-readable explanation
Do not expose raw stack traces to operators.

DOCUMENTATION
After implementation create/update documentation covering:
    1. Map architecture
    2. MCP installation
    3. Hermes configuration
    4. MapLibre MCP configuration
    5. Available tools
    6. Map adapter
    7. Map state
    8. Agent control flow
    9. Local development
    10. Troubleshooting
Documentation must reflect the actual implementation.

IMPORTANT DEVELOPMENT RULES
    1. Inspect before modifying.
    2. Reuse existing architecture whenever possible.
    3. Do not rewrite working components unnecessarily.
    4. Do not create duplicate MCP functionality.
    5. Do not hard-code business logic into generic map components.
    6. Do not remove the existing Esri basemap without a justified migration plan.
    7. Keep MapLibre implementation replaceable.
    8. Keep MCP implementation replaceable.
    9. Keep business data independent from map rendering.
    10. Prefer small, testable modules.
    11. Verify every major change.
    12. Run existing tests before and after modifications when available.
    13. Do not claim a feature works without testing it.
    14. Record architectural decisions.
    15. If an assumption is required, inspect the code or documentation before making it.

DEFINITION OF DONE
The implementation is considered successful only when:
ANA
 │
 ▼
Hermes
 │
 ▼
MapLibre MCP
 │
 ▼
Map Control / Adapter
 │
 ▼
Existing SPATIAL MAP
 │
 ▼
MapLibre
 │
 ▼
Esri Basemap
works as an integrated system.
At minimum ANA must be able to:
✓ inspect map state
✓ change map view
✓ fit geographic bounds
✓ inspect layers
✓ toggle layers
✓ select/highlight features
✓ clear selection/highlight
✓ preserve existing Esri basemap
✓ operate without breaking manual map interaction
The architecture must also be ready for future capabilities such as:
GeoJSON
Vector Tiles
MVT
PMTiles
PostGIS
spatial queries
feature analytics
geospatial business intelligence
voice commands
multi-project maps

FINAL BEHAVIOR
You are not merely implementing a MapLibre integration.
You are building the spatial control capability of ANA.
The long-term goal is:
Operator
   │
   │ natural language
   ▼
ANA
   │
   ├── understands intent
   │
   ├── queries data
   │
   ├── reasons about spatial context
   │
   ├── invokes MapLibre capabilities
   │
   ▼
SPATIAL MAP
   │
   ├── moves
   ├── filters
   ├── highlights
   ├── selects
   ├── changes layers
   └── visualizes results
Build the foundation carefully so that the same architecture can later be reused by ANA across multiple projects and domains.
Do not stop at installing the MCP.
The final objective is an agent-controlled spatial workspace integrated into ANA's existing dashboard.

