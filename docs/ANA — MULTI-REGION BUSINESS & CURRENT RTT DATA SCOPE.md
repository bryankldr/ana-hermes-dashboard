# ANA — MULTI-REGION BUSINESS & CURRENT RTT DATA SCOPE

This directive extends the SIMOGE Business Intelligence and Spatial Intelligence architecture.

The current database contains data primarily from:

```text
DIVRE Jawa Timur
└── KPH Banyuwangi Barat
```

This is only the currently available dataset.

It must NOT become the assumed organizational scope of ANA.

The system is designed to eventually contain:

```text
DIVRE / REGIONAL
├── Jawa Timur
│   ├── KPH
|   |   ├── BKPH
|   |   |    ├── RPH
|   |   |        ├── TPG
        ├── BKPH
|   |       ├── RPH
|   |           ├── TPG
|   |
│   ├── KPH
│   └── ...
│
├── Jawa Tengah
│   ├── KPH
│   ├── KPH
│   └── ...
│
└── Jawa Barat
    ├── KPH
    ├── KPH
    └── ...
```

ANA must therefore be designed from the beginning as a **multi-region, multi-KPH business and spatial intelligence agent**.

---

# 1. SEPARATE BUSINESS DOMAIN FROM CURRENT DATA

The organizational hierarchy is global business knowledge.

The currently populated records are only a subset of that hierarchy.

Never infer:

```text
Banyuwangi Barat = entire system
```

Instead:

```text
Business Domain
    ↓
All supported regions
    ↓
All supported KPH
    ↓
Current available data
```

If only Banyuwangi Barat has data, ANA should understand:

> The business domain is broader than the currently populated dataset.

---

# 2. ORGANIZATIONAL HIERARCHY

Model the organizational hierarchy generically:

```text
DIVRE / REGIONAL
    ↓
KPH
    ↓
BKPH
    ↓
RPH
    ↓
TPG
    ↓
Penyadap
    ↓
Andil
    ↓
Petak

```

Do not hard-code:

```text
Jawa Timur
Banyuwangi Barat
```

into generic business logic.

They are instances of the hierarchy.

---

# 3. DATA SCOPE

ANA must have a concept called:

```text
DATA_SCOPE
```

The default scope is:

```text
CURRENT_RTT_YEAR
```

where:

```text
CURRENT_RTT_YEAR = current calendar year
```

Do not hard-code a specific year.

For example:

```text
2026 → tahun_rtt = 2026
2027 → tahun_rtt = 2027
2028 → tahun_rtt = 2028
```

---

# 4. DEFAULT PETAK SCOPE

By default, spatial/business processing must operate only on:

```text
petak.tahun_rtt = CURRENT_RTT_YEAR
```

or the actual equivalent field/relationship discovered in the database.

The exact implementation must be verified against the actual schema.

The principle is:

```text
DEFAULT:
only process Petak belonging to the current RTT year.
```

---

# 5. IMPORTANT DISTINCTION

Do not confuse:

```text
current year
```

with:

```text
tahun_rtt
```

The system must explicitly determine how `tahun_rtt` is represented and related to Petak.

The default filter must be based on the actual business field:

```text
tahun_rtt
```

not merely:

```text
date_created
```

unless the business implementation explicitly establishes that relationship.

---

# 6. GLOBAL DEFAULT FILTER

All business and spatial queries involving Petak should apply the current RTT scope by default.

Conceptually:

```text
SELECT ...
FROM petak
WHERE tahun_rtt = CURRENT_RTT_YEAR
```

Do not blindly use this exact SQL.

Adapt it to the actual schema.

The important rule is:

```text
DEFAULT PETAK SCOPE
=
Petak with tahun_rtt equal to the current year.
```

---

# 7. SCOPE INHERITANCE

The default scope should propagate through related entities.

Conceptually:

```text
Current RTT Petak
      │
      ├── Andil
      │
      ├── Penyadap
      │
      └── Aktivitas
```

When ANA asks:

> "Berapa penyadap di petak ini?"

the relevant Petak must already belong to the current RTT scope.

When ANA asks:

> "Tampilkan aktivitas pada petak ini."

the query must preserve the Petak context.

Do not accidentally mix records from unrelated RTT years.

---

# 8. EXPLICIT HISTORICAL QUERIES

The default is current RTT year.

However, ANA must be able to answer historical questions when explicitly requested.

Examples:

```text
"Bagaimana kondisi petak tahun 2025?"
```

or:

```text
"Tampilkan RTT 2024."
```

In those cases, ANA may change the temporal scope explicitly.

The change should be visible in the reasoning/context.

Conceptually:

```text
DEFAULT
tahun_rtt = CURRENT_YEAR

EXPLICIT
tahun_rtt = requested_year
```

Do not silently switch years.

---

# 9. SPATIAL MAP DEFAULT

When displaying Petak on the map:

```text
SPATIAL MAP
    ↓
Petak Layer
    ↓
DEFAULT FILTER
tahun_rtt = CURRENT_RTT_YEAR
```

Therefore the default map should not render historical RTT Petak unless explicitly requested.

---

# 10. ORGANIZATIONAL FILTERS

ANA must support hierarchical scope filters:

```text
All Regions
    ↓
Selected Region
    ↓
Selected KPH
    ↓
Selected BKPH
    ↓
Selected RPH
    ↓
Selected TPG
    ↓
Selected Petak
```

These filters must compose with the RTT filter.

Example:

```text
Region = Jawa Timur
AND
KPH = Banyuwangi Barat
AND
tahun_rtt = CURRENT_RTT_YEAR
```

Another example:

```text
Region = Jawa Tengah
AND
KPH = X
AND
tahun_rtt = CURRENT_RTT_YEAR
```

The implementation must be generic.

---

# 11. EMPTY DATA IS NOT INVALID BUSINESS KNOWLEDGE

If ANA receives:

```text
Region = Jawa Barat
```

but the current database does not yet contain records for that region, ANA must distinguish:

```text
Region exists in business hierarchy
```

from:

```text
No current data available
```

Correct response conceptually:

> Jawa Barat merupakan bagian dari cakupan organisasi, tetapi belum terdapat data RTT tahun berjalan pada dataset yang tersedia.

Do not respond:

> Jawa Barat tidak ada.

---

# 12. CURRENT DATA AVAILABILITY

ANA should be able to determine:

```text
which regions have data
which KPH have data
which RTT years exist
which Petak belong to current RTT
```

This should be derived from the database.

Do not hard-code availability.

---

# 13. DATA SCOPE TOOL

Create a semantic capability equivalent to:

```text
get_current_data_scope()
```

It should expose:

```text
current_year
current_rtt_year
available_regions
available_kph
available_bkph
available_rph
available_tpg
```

Only expose values that can be reliably determined from the actual data.

---

# 14. CONTEXTUAL SCOPE

ANA must always know the active scope.

For example:

```text
GLOBAL
```

or:

```text
Region:
Jawa Timur

KPH:
Banyuwangi Barat

RTT:
2026
```

or:

```text
Region:
Jawa Tengah

KPH:
X

RTT:
2026
```

This scope should be available to the spatial reasoning layer.

---

# 15. MAP STATE

The map state should include the active business scope:

```text
map
├── center
├── zoom
├── bounds
├── layers
├── selected_feature
├── filters
└── business_scope
     ├── region
     ├── kph
     ├── bkph
     ├── rph
     ├── tpg
     └── tahun_rtt
```

This allows ANA to understand statements such as:

> "Tampilkan yang lain di sini."

in the correct business context.

---

# 16. PERFORMANCE

Do not send all regions and all historical Petak to the LLM.

Use database-side filtering.

Preferred flow:

```text
User
 ↓
ANA determines scope
 ↓
Database query
 ↓
Current RTT records
 ↓
Spatial result
 ↓
MapLibre
```

Do not perform current-year filtering inside the LLM after retrieving a huge dataset.

---

# 17. BUSINESS KNOWLEDGE VS DATA KNOWLEDGE

Maintain this distinction:

```text
BUSINESS KNOWLEDGE
"What is a KPH?"
"What is an RTT?"
"What is a Petak?"

DATA KNOWLEDGE
"Which KPH currently has data?"
"Which Petak have tahun_rtt = 2026?"

SPATIAL KNOWLEDGE
"Where is this Petak?"
"What is its polygon?"
"What objects intersect it?"
```

ANA must use all three layers.

---

# 18. FUTURE DATA EXPANSION

The architecture must work when data changes from:

```text
Current:
Jawa Timur
└── Banyuwangi Barat
```

to:

```text
Future:
Jawa Timur
├── KPH A
├── KPH B
└── Banyuwangi Barat

Jawa Tengah
├── KPH C
└── KPH D

Jawa Barat
├── KPH E
└── KPH F
```

No code change should be required merely because a new KPH is added.

New organizational data must be discovered from the database.

---

# 19. YEAR ROLLOVER

The system must automatically adapt to a new year.

Never implement:

```text
tahun_rtt = 2026
```

as permanent business logic.

Use:

```text
tahun_rtt = current year
```

with the current date supplied by the runtime/system.

If a new year begins, the default scope must naturally change.

---

# 20. VALIDATION

Test at minimum:

```text
Test 1:
Current year returns only current RTT Petak.

Test 2:
Historical RTT is excluded by default.

Test 3:
Explicit historical query can override the default scope.

Test 4:
Region filters work.

Test 5:
KPH filters work.

Test 6:
Region + KPH + RTT filters compose correctly.

Test 7:
A region with no data is distinguished from a nonexistent region.

Test 8:
Map displays only the active RTT scope by default.

Test 9:
Selecting a polygon preserves its organizational and RTT context.

Test 10:
Adding a new KPH requires no hard-coded application change.
```

---

# FINAL PRINCIPLE

ANA must understand:

```text
BUSINESS SCOPE
≠
CURRENT DATA AVAILABILITY
≠
CURRENT MAP VIEW
```

These are three different concepts.

The business domain is global.

The database may currently contain only a subset.

The map displays only the currently active spatial scope.

The default temporal scope is:

```text
tahun_rtt = current year
```

unless the user explicitly requests another RTT year.


1. Schema discovery
       ↓
2. Business entity mapping
       ↓
3. RTT/year mapping
       ↓
4. Spatial geometry mapping
       ↓
5. Read-only semantic queries
       ↓
6. Map integration