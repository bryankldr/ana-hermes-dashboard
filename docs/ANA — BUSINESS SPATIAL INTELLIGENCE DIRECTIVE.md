# ANA — BUSINESS SPATIAL INTELLIGENCE DIRECTIVE

You have successfully implemented MapLibre MCP integration and can control the existing SPATIAL MAP.

Your next objective is to evolve from a map-controlling agent into a **business-aware spatial intelligence agent**.

The existing dashboard contains:

```text
SPATIAL MAP
└── Esri Basemap
```

Business data is stored in MySQL.

The goal is for you to understand the business domain, database structure, spatial entities, relationships, and map state well enough to perform accurate spatial reasoning and map navigation.

---

## CORE PRINCIPLE

Never guess geographic information.

Never infer a polygon's location from an identifier.

Never invent coordinates.

Never approximate a business entity when an exact database lookup is possible.

The authoritative flow must be:

```text
User Intent
    ↓
Business Understanding
    ↓
Entity Resolution
    ↓
Database Query
    ↓
Exact Spatial Record
    ↓
Spatial Reasoning
    ↓
Map Control
    ↓
Visual Verification
```

---

# 1. DISCOVER THE DATABASE

Inspect the MySQL database and build a machine-readable understanding of:

* tables
* columns
* primary keys
* foreign keys
* indexes
* relationships
* geometry fields
* business identifiers
* administrative hierarchy
* temporal fields
* status fields

Do not expose the entire raw database schema to the LLM on every request.

Create a compact semantic representation.

---

# 2. BUILD BUSINESS KNOWLEDGE

Create a Business Knowledge layer that explains:

* entity meanings
* business terminology
* entity relationships
* hierarchy
* identifiers
* status meanings
* spatial relationships
* temporal concepts

Separate business knowledge from database implementation details.

For example:

```text
Business concept
    ↓
Business entity
    ↓
Database representation
```

Do not make the LLM dependent on raw table names alone.

---

# 3. BUILD A SPATIAL ENTITY REGISTRY

Create a registry describing every spatially relevant entity.

Each entity should define, where applicable:

```text
entity
business meaning
identifier
database source
geometry source
geometry type
display layer
selection behavior
highlight behavior
zoom behavior
detail query
```

Example:

```text
Petak
 ├── identifier
 ├── attributes
 ├── polygon
 ├── centroid
 ├── bounds
 ├── map layer
 └── detail query
```

---

# 4. POLYGON-FIRST DESIGN

Treat polygons as first-class business objects.

For polygon entities, support:

```text
resolve polygon
get exact geometry
get centroid
get bounds
calculate/obtain area
select polygon
highlight polygon
fit map to polygon
query objects inside polygon
query neighboring polygons
```

When the user requests:

```text
"Fokus ke petak X"
```

perform:

```text
resolve exact petak
        ↓
retrieve exact polygon
        ↓
select feature
        ↓
highlight feature
        ↓
fitBounds
        ↓
verify visual result
```

Do not merely fly to a centroid unless no polygon geometry is available.

---

# 5. DATABASE IS SOURCE OF TRUTH

For business facts:

```text
MySQL = authoritative source
```

For spatial rendering:

```text
MapLibre = rendering layer
```

For agent reasoning:

```text
ANA = semantic reasoning layer
```

Never treat the visual map as the authoritative source for business facts.

---

# 6. CREATE A DATABASE ACCESS ABSTRACTION

Do not allow business reasoning to depend directly on arbitrary SQL generation.

Create semantic operations such as:

```text
resolve_entity
find_petak
find_rph
find_tpg
find_penyadap
find_aktivitas
get_polygon
get_feature_relationships
```

Translate these operations to SQL internally.

Use parameterized queries.

Do not construct unsafe SQL from raw user text.

---

# 7. SPATIAL OPERATIONS

Support spatial reasoning such as:

```text
point in polygon
polygon intersection
polygon containment
polygon adjacency
distance between objects
objects within polygon
objects within radius
polygon bounds
polygon centroid
```

Use the database's spatial capabilities where appropriate.

Do not perform expensive geometry processing in the LLM.

---

# 8. MAP STATE

Maintain a canonical observable map state.

It should contain, where supported:

```text
center
zoom
bearing
pitch
bounds
basemap
visible layers
selected feature
highlighted features
filters
active spatial context
```

ANA must be able to inspect this state before answering context-dependent spatial questions.

---

# 9. CONTEXTUAL REFERENCES

Resolve references such as:

```text
"petak ini"
"yang ini"
"di sebelahnya"
"area tersebut"
"yang tadi"
"polygon yang dipilih"
```

using current map state and conversation context.

Resolution priority:

```text
Current selected feature
        ↓
Current highlighted feature
        ↓
Current spatial context
        ↓
Conversation context
        ↓
Database entity resolution
```

If ambiguity remains, ask a concise clarification rather than guessing.

---

# 10. MAP NAVIGATION

Use the appropriate navigation operation.

For points:

```text
flyTo / center
```

For polygons:

```text
fitBounds
```

For collections:

```text
fitBounds(collection bounds)
```

For hierarchical areas:

```text
fitBounds(area bounds)
```

Avoid arbitrary zoom values when actual geometry bounds are available.

---

# 11. VISUAL VERIFICATION

After a map-control operation, verify that:

```text
command succeeded
map state changed as expected
target feature is visible
selected/highlighted feature is correct
```

Do not report success solely because an MCP call returned successfully.

---

# 12. BUSINESS + SPATIAL QUERY

Support compound reasoning.

Example:

```text
"tampilkan petak yang belum memiliki penyadap"
```

Interpret as:

```text
Business query
    +
Spatial visualization
```

Process:

```text
identify Petak
      ↓
query Petak
      ↓
identify associated Penyadap
      ↓
filter Petak without Penyadap
      ↓
obtain geometries
      ↓
render/highlight
      ↓
fit bounds
```

The exact query strategy must be determined from the actual schema.

---

# 13. DO NOT MIX DATA AND RENDERING

Maintain this separation:

```text
Business/Data Layer
        ↓
Spatial Intelligence Layer
        ↓
Map Control Layer
        ↓
MapLibre
```

Do not embed business rules directly inside MapLibre components.

Do not embed database queries directly inside visual components.

---

# 14. PERFORMANCE

The system must remain responsive.

Do not send large polygon collections through the LLM.

Do not repeatedly transfer full GeoJSON unnecessarily.

Prefer:

```text
metadata
IDs
bounds
vector tiles
MVT
PMTiles
spatial indexes
```

for large datasets.

Retrieve exact geometry when required for:

```text
selection
inspection
highlighting
detail
analysis
```

---

# 15. MAP CACHE

Where appropriate, maintain a lightweight cache for:

```text
recently resolved entities
recently selected polygons
recent map context
frequently accessed administrative areas
```

Do not allow stale cached business facts to override authoritative database data.

Clearly distinguish:

```text
cached spatial metadata
```

from:

```text
authoritative business data
```

---

# 16. CREATE SPATIAL TOOLS

Design semantic tools around business intent.

Examples:

```text
resolve_spatial_entity
get_spatial_entity
get_polygon_geometry
get_polygon_bounds
get_polygon_context
find_features_in_polygon
find_nearby_features
find_neighboring_polygons
```

Map-control tools remain separate:

```text
map_get_state
map_set_view
map_fit_bounds
map_select_feature
map_highlight_features
map_toggle_layer
```

---

# 17. AGENT REASONING

For every spatial request, reason in this order:

```text
1. What business entity is being referenced?
2. What identifier identifies it?
3. Where is the authoritative data?
4. Does it have geometry?
5. What spatial operation is required?
6. What map operation represents the result?
7. What visual state should result?
8. Did the map actually reach the intended state?
```

Do not skip entity resolution.

---

# 18. MULTI-PROJECT DESIGN

Do not hard-code one business domain into the generic spatial engine.

Separate:

```text
Generic Spatial Intelligence
```

from:

```text
Business Domain Knowledge
```

This allows ANA to work on other projects while retaining the same spatial architecture.

---

# 19. DOCUMENTATION

Create documentation describing:

```text
Business entities
Database mapping
Spatial entity registry
Spatial query architecture
Map state
Map control
MCP integration
Caching
Performance strategy
Error handling
```

Documentation must represent the actual implementation.

---

# 20. SUCCESS CRITERIA

The implementation is successful when ANA can accurately handle interactions such as:

```text
"Fokus ke petak X."
```

```text
"Tampilkan polygon ini."
```

```text
"Petak apa yang sedang saya lihat?"
```

```text
"Apa yang ada di dalam polygon ini?"
```

```text
"Tampilkan petak di sekitar polygon ini."
```

```text
"Highlight semua petak yang memenuhi kondisi tersebut."
```

```text
"Berapa penyadap di area ini?"
```

```text
"Tampilkan aktivitas di polygon yang sedang dipilih."
```

For each request:

```text
Business meaning
        ↓
Exact database record
        ↓
Exact spatial geometry
        ↓
Spatial reasoning
        ↓
MapLibre control
        ↓
Visual verification
```

must remain deterministic and traceable.

---

# FINAL OBJECTIVE

Do not build merely a chatbot that can control a map.

Build ANA into a:

**Business-Aware Spatial Intelligence Agent**

capable of understanding:

```text
business
   +
database
   +
geospatial entities
   +
geometry
   +
map state
   +
operator intent
```

and translating them into accurate spatial actions.

The map is the visual interface.

MySQL is the business data source.

MapLibre is the rendering engine.

MCP is the control interface.

ANA is the reasoning and orchestration layer.

ANA tidak perlu "melihat gambar peta" lalu menebak. Ia bisa:

current selected polygon
        ↓
exact feature ID
        ↓
exact polygon geometry
        ↓
MySQL spatial query
        ↓
count penyadap
        ↓
MapLibre highlight
        ↓
jawaban