"""Extract all error/traceback/crash lines from the most recent call session."""
import sys

with open('logs/app.log', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Find the most recent inbound call
last_call_idx = -1
for i, line in enumerate(lines):
    if 'Inbound call' in line:
        last_call_idx = i

if last_call_idx == -1:
    print("No inbound calls found in log")
    sys.exit(1)

# Print everything from the last inbound call to end of file
call_lines = lines[last_call_idx:]
print(f"--- Last call starts at line {last_call_idx + 1} ({len(call_lines)} lines) ---")
for line in call_lines:
    # Print all lines (not just errors) so we can see the full flow
    print(line.rstrip())
