import sys
try:
    with open('logs/app.log', 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    start_idx = -1
    for i, line in enumerate(lines):
        if "saved to database" in line:
            start_idx = i
            
    if start_idx != -1:
        print("".join(lines[start_idx:start_idx+50]))
    else:
        print("Could not find 'saved to database' in log.")
except Exception as e:
    print(f"Error reading log: {e}")
