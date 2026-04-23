import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add new imports near the top
import_block = """
from database import init_db, migrate_db, get_connection, save_report, fetch_report_row
from geo import photon_search, timeapi_timezone_name
from services.analysis_service import (
    compute_hybrid_big_three, build_blueprint, build_prediction, 
    simulate_palm_analysis, zodiac_sign, moon_sign, ascendant_sign
)
"""
if "from database import" not in content:
    content = content.replace("from flask import Flask, jsonify, render_template, request, session\n", 
                              "from flask import Flask, jsonify, render_template, request, session\n" + import_block)

# Remove the duplicated DB constants and functions
content = re.sub(r'PHOTON_BASE_URL = os\.environ\.get.*?TIMEAPI_BASE_URL = os\.environ\.get.*?\n', '', content, flags=re.DOTALL)

# Remove duplicate DB and geo methods
methods_to_remove = [
    r'def get_connection\(\) -> sqlite3\.Connection:.*?return conn\n',
    r'def http_get_json\(.*?return data if isinstance\(data, dict\) else \{\}\n',
    r'def photon_search\(.*?return out\n',
    r'def timeapi_timezone_name\(.*?return str\(tz\)\.strip\(\) if tz else None\n',
]

for m in methods_to_remove:
    content = re.sub(m, '', content, flags=re.DOTALL)

# Remove the huge block of math, constants, and helper functions (from _deg_to_rad up to compute_life_scores)
# Let's just find the start and end of this block.
# Starts at "def _deg_to_rad(x: float) -> float:"
# Ends before "def openai_guru_reply"
start_str = "def _deg_to_rad(x: float) -> float:"
end_str = "def openai_guru_reply(system: str, user: str) -> Optional[str]:"
start_idx = content.find(start_str)
end_idx = content.find(end_str)

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + "\n\n" + content[end_idx:]

# Remove duplicate save_report and fetch_report_row
start_str2 = "def fetch_report_row(report_id: int) -> Optional[sqlite3.Row]:"
end_str2 = "@app.route(\"/landing\")"
start_idx2 = content.find(start_str2)
end_idx2 = content.find(end_str2)

if start_idx2 != -1 and end_idx2 != -1:
    content = content[:start_idx2] + "\n\n" + content[end_idx2:]

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Refactored app.py successfully!")
