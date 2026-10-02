import os
import sys

# Add subdirectories to Python path for seamless imports
base_dir = os.path.dirname(os.path.abspath(__file__))
kurti_platform_dir = os.path.join(base_dir, "web_scrapping", "kurti_trend_platform")
frontend_dir = os.path.join(kurti_platform_dir, "frontend")

for p in [base_dir, kurti_platform_dir, frontend_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Execute the main Streamlit platform entry point
app_path = os.path.join(frontend_dir, "app.py")
with open(app_path, "r", encoding="utf-8") as f:
    code = compile(f.read(), app_path, "exec")
    exec(code, globals())
