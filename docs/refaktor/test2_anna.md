YOU: tampilkan di peta, petak yang kurang efektif saja
⚡ skill_view({"name": "simoge-business"}) → ok
⚡ tool_search({"queries": ["simoge petak query", "spatial map show", "ana chart show"]}) → ok
⚡ skill_view() → ok · {"success": true, "name": "simoge-business", "description": "Use for SIMOGE queries (petak, penyadap, produksi) or map d
⚡ tool_search() → ok · {"queries": ["simoge petak query", "spatial map show", "ana chart show"], "total_available": 16, "results": [{"query": "
⚡ execute_code({"code": "from hermes_tools import terminal\nimport json\nr = terminal(\"PYTHONPATH=/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts python3 -c \\\"from ana_simoge_tool import list_templates; print(list_templates())\\\"\")\nprint(r)\n"}) → ok
⚡ execute_code() → error · {"status": "error", "error": "BLOCKED: execute_code runs arbitrary local Python (including subprocess calls that bypass 
⚡ terminal({"command": "PYTHONPATH=/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts python3 -c \"from ana_simoge_tool import list_templates; print(list_templates())\""}) → ok
⚡ terminal() → error · {"output": "/usr/bin/bash: line 4: cd: ./home/bryankldr/PROYEK_2026: No such file or directory", "exit_code": 126, "erro
⚡ terminal({"command": "pwd; ls /home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts/ | head -20", "workdir": "/home/bryankldr/PROYEK_2026/ana-hermes-dashboard"}) → ok
⚡ terminal() → ok · {"output": "/home/bryankldr/PROYEK_2026/ana-hermes-dashboard\nana_chart_tool.py\nana_kpi.py\nana_simoge_tool.py\nmap_bri
⚡ read_file({"limit": 200, "offset": 1, "path": "/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts/simoge_db.py"}) → ok
⚡ read_file() → ok · {"content": "1|#!/usr/bin/env python3\n2|\"\"\"\n3|SIMOGE read-only MariaDB executor + verified business query templates
⚡ read_file({"limit": 300, "offset": 200, "path": "/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts/simoge_db.py"}) → ok
⚡ read_file() → ok · {"content": "200|def petak_with_geometry(tahun, limit=1000, **kw):\n201|    \"\"\"Petak RTT + geometry. Join via kode_ev
⚡ read_file({"limit": 120, "offset": 1, "path": "/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts/ana_simoge_tool.py"}) → ok
⚡ read_file({"limit": 120, "offset": 1, "path": "/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts/map_bridge.py"}) → ok
⚡ read_file({"limit": 120, "offset": 1, "path": "/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts/ana_chart_tool.py"}) → ok
⚡ read_file() → ok · {"content": "1|#!/usr/bin/env python3\n2|\"\"\"\n3|ANA-Tool wrapper: exposes simoge-business templates as a callable too
⚡ read_file() → ok · {"content": "1|#!/usr/bin/env python3\n2|\"\"\"\n3|Map Bridge for ANA HUD Dashboard.\n4|Pushes MapLibre commands to the 
⚡ read_file() → ok · {"content": "1|#!/usr/bin/env python3\n2|\"\"\"\n3|ANA chart tool — kontrol panel chart di dalam SPATIAL MAP.\n4|\n5|ANN
⚡ read_file({"limit": 160, "offset": 120, "path": "/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts/ana_simoge_tool.py"}) → ok
⚡ read_file() → ok · {"content": "120|    \n121|    if template == \"drum_flow\":\n122|        counts = {}\n123|        for r in result[\"row
⚡ read_file({"limit": 400, "offset": 500, "path": "/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts/simoge_db.py"}) → ok
⚡ read_file() → ok · {"content": "500|        LEFT JOIN (\n501|            SELECT kode_evapot, COUNT(*) cnt FROM getah_aktivitas_sadap\n502| 
⚡ read_file({"limit": 200, "offset": 900, "path": "/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/scripts/simoge_db.py"}) → ok
⚡ read_file() → ok · {"content": "900|\n901|@template(\"produksi_year_to_date\")\n902|def produksi_year_to_date(tahun: int, bulan: int, day: 
⚡ search_files({"limit": 20, "output_mode": "content", "path": "/home/bryankldr/PROYEK_2026/ana-hermes-dashboard", "pattern": "show_on_map"}) → ok
⚡ search_files() → ok · {"total_count": 20, "matches_format": "path-grouped: each file path on its own line, followed by indented '<line>: <cont