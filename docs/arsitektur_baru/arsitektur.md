Ya. Dan menurut saya itu justru arsitektur yang paling tepat untuk tujuan ana-hermes-dashboard.

Yang Anda inginkan sebenarnya bukan membuat agent baru di dashboard, tetapi:

ana-hermes-dashboard = Web UI untuk satu instance/profile Hermes, yaitu ANNA.

Dengan begitu, arsitekturnya harus sedekat mungkin dengan Hermes Desktop pada jalur agent execution.

Arsitektur target
                    ┌──────────────────────────────┐
                    │      Browser / Web UI        │
                    │                              │
                    │  Chat • Voice • Map • KPI    │
                    │  ──────────────────────────  │
                    │       ANNA Dashboard         │
                    └──────────────┬───────────────┘
                                   │
                            WebSocket / RPC
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │       Hermes Gateway         │
                    │                              │
                    │  profile = anna               │
                    │  session routing             │
                    │  approval / policy           │
                    │  event streaming              │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │       Agent Runtime          │
                    │                              │
                    │  system prompt               │
                    │  persona                      │
                    │  memory                       │
                    │  skills                       │
                    │  tools                        │
                    │  provider                     │
                    │  tool loop                    │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
                 LLM/API       Tools          Memory

Bukan lagi:

Browser
   │
   ▼
server.py
   │
   ▼
spawn `hermes chat`
   │
   ▼
CLI
   │
   ▼
Agent

Itulah sumber utama rasa kurang responsif dan kurang efisien yang Anda rasakan.

Yang sebaiknya dipertahankan dari ana-hermes-dashboard

Jangan membuang bagian dashboard yang sudah Anda bangun.

ana-hermes-dashboard tetap memiliki:

Chat UI
Voice input
TTS
Spatial Map
chart/KPI
Kanban
Vault integration UI
visualisasi tool execution
kontrol MapLibre
business context dari Dashboard Business Data Engine

Tetapi agent execution dipindahkan kembali ke Hermes.

Jadi pembagiannya menjadi sangat jelas:

┌──────────────────── ANNA WEB DASHBOARD ────────────────────┐
│                                                            │
│  UI / Visualization / Interaction                          │
│                                                            │
│  Chat     Voice     Map     Chart     KPI     TTS          │
│                                                            │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           │ RPC / Events
                           ▼
┌──────────────────────── HERMES ────────────────────────────┐
│                         ANNA                               │
│                                                            │
│  Session                                                   │
│  Memory                                                    │
│  Persona                                                   │
│  Skills                                                    │
│  Tools                                                     │
│  Provider                                                  │
│  Tool execution                                            │
│  Approval                                                  │
│  Context                                                   │
│                                                            │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
                  LLM / External Tools

Ini jauh lebih sesuai dengan prinsip yang sebelumnya Anda tetapkan:

Dashboard owns data, Anna owns interpretation.

Ada satu hal penting

Saya tidak menyarankan langsung meng-embed run_agent.py ke server.py.

Opsi 2 tadi terlihat menarik:

server.py
   └── run_agent.py

tetapi sebenarnya membuat dashboard menjadi bagian dari Hermes runtime.

Itu membuat coupling sangat tinggi.

Lebih baik:

Browser
   │
   ▼
ana-hermes-dashboard
   │
   │ RPC / WebSocket
   ▼
Hermes Gateway
   │
   ▼
ANNA Agent Runtime

Dengan demikian Hermes tetap menjadi source of truth untuk agent lifecycle.

Bahkan session seharusnya tidak lagi dikelola dashboard

Saat ini:

Browser
   │
   ├── localStorage ana_session
   │
   ▼
server.py
   │
   ├── _session_get()
   ├── _session_set()
   └── --resume SID

Target:

Browser
   │
   │ session key
   ▼
Hermes Gateway
   │
   ▼
state.db
   │
   ▼
persistent ANNA session

Browser hanya perlu mengetahui identifier sesi untuk UI.

Tidak perlu memahami:

Hermes sid
--resume
session lifecycle
agent state
provider state

Itu semua urusan Hermes.

Efeknya terhadap latency

Sekarang setiap pertanyaan kira-kira:

HTTP
 ↓
server
 ↓
spawn Python/CLI
 ↓
load Hermes
 ↓
load profile
 ↓
load persona
 ↓
restore session
 ↓
initialize agent
 ↓
provider
 ↓
LLM

Sedangkan target:

WebSocket/RPC
 ↓
Gateway
 ↓
existing ANNA agent
 ↓
provider
 ↓
LLM

Jadi bagian yang tidak perlu diulang setiap turn hilang.

Yang paling penting bukan hanya menghemat beberapa ratus milidetik. Anda juga menghilangkan cold-start behavior dan membuat lifecycle agent benar-benar persistent.

Streaming juga harus berubah

Saat ini dashboard melakukan translasi:

Hermes CLI
     │
     │ JSONL
     ▼
runtime.py
     │
     │ translate
     ▼
NDJSON
     │
     ▼
Browser

Ini sebenarnya layer yang tidak perlu.

Target:

Hermes Gateway
      │
      │ native events
      ▼
 WebSocket
      │
      ▼
 Browser

Misalnya event:

{
  "type": "delta",
  "session": "anna-main",
  "content": "Berdasarkan produksi..."
}

atau:

{
  "type": "tool_use",
  "tool": "spatial_map",
  "input": {...}
}

Dashboard tinggal merender.

Tidak perlu menjadi adapter Hermes CLI.

single-flight juga bisa dihilangkan

Sekarang:

running = true

Request A ───────────────► ANNA
Request B ──X 409
Request C ──X 409

Hermes desktop:

Session A ─────────► ANNA
Session B ─────────► ANNA
Session C ─────────► ANNA

Untuk dashboard Anda bahkan bisa membuat:

ANNA
 │
 ├── Session: Bryan
 │
 ├── Session: Analysis
 │
 ├── Session: Produksi
 │
 └── Session: Meeting

tetapi hanya expose profile anna.

Jadi:

profiles available internally:
    default
    anna
    ...
    
dashboard:
    └── ANNA only

User web tidak perlu mengetahui profile lain.

Saya bahkan akan menyederhanakan server.py

Saat ini server.py terlalu banyak mengetahui Hermes:

server.py
 ├── session
 ├── RUN_LOCK
 ├── spawn
 ├── timeout
 ├── command routing
 ├── event translation
 └── agent lifecycle

Target:

server.py
 ├── authentication
 ├── dashboard API
 ├── business-data API
 ├── WebSocket
 └── static UI

Sedangkan:

Hermes
 ├── session
 ├── agent lifecycle
 ├── provider
 ├── memory
 ├── skills
 ├── tools
 ├── tool loop
 ├── approval
 └── streaming events

Itu separation yang jauh lebih sehat.

Yang paling menarik: Spatial Map tetap bisa menjadi "mata" ANNA

Ini penting untuk desain Anda.

Misalnya user berkata:

"Tampilkan petak bongkor di BKPH X."

Flow:

User
 │
 ▼
Browser
 │
 ▼
ANNA
 │
 ├── memahami intent
 │
 ├── memanggil dashboard/map capability
 │
 ▼
Dashboard
 │
 ├── query Business Data Engine
 ├── filter petak
 ├── render polygon
 └── zoom map
 │
 ▼
event → ANNA
 │
 ▼
"Berikut petak bongkor..."

Jadi Hermes tidak perlu mengetahui DOM atau MapLibre secara langsung.

ANNA memiliki tool/capability, sedangkan dashboard menyediakan implementasinya.

Contohnya secara konseptual:

ANNA
 └── tool: dashboard_map
       ├── filter
       ├── select
       ├── zoom
       ├── highlight
       └── clear

Dashboard yang menjalankan capability tersebut.

Ini sangat cocok dengan konsep Anda bahwa ANNA adalah business intelligence assistant dengan voice, bukan sekadar chatbot.

Target arsitektur saya

Saya akan mengarahkan proyek ke model ini:

                       INTERNET / LAN
                            │
                            ▼
                 ┌──────────────────────┐
                 │  ana-hermes-dashboard │
                 │                      │
                 │       Web UI         │
                 └──────────┬───────────┘
                            │
                     WebSocket / RPC
                            │
                            ▼
                 ┌──────────────────────┐
                 │    Hermes Gateway   │
                 │                      │
                 │      ANNA only       │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │    Agent Runtime    │
                 │                      │
                 │ Persona              │
                 │ Memory               │
                 │ Skills               │
                 │ Tools                │
                 │ Provider             │
                 │ Sessions             │
                 └──────────┬───────────┘
                            │
             ┌──────────────┼───────────────┐
             ▼              ▼               ▼
           LLM          Obsidian       Dashboard Tools
                                          │
                          ┌───────────────┼──────────────┐
                          ▼               ▼              ▼
                       MapLibre          KPI         Business DB

Kesimpulannya: ya, ana-hermes-dashboard sebaiknya diubah menjadi Web UI client untuk Hermes Gateway, bukan lagi menjalankan Hermes CLI per request.

Dan saya akan memilih Opsi 1, bukan embed runtime.

Langkah berikutnya yang paling tepat adalah memeriksa implementasi Hermes yang terpasang di mesin Anda: bagaimana Gateway Desktop berkomunikasi dengan run_agent.py, endpoint/socket JSON-RPC yang sebenarnya, event schema, dan lifecycle session. Setelah itu kita bisa membuat migration plan runtime.py → Hermes Gateway client tanpa merusak UI dashboard yang sekarang.