import sys
try:
    with open('logs/app.log', 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        for i, line in enumerate(lines[-2000:]):
            if "WhatsApp send failed" in line:
                print("".join(lines[-2000 + i: -2000 + i + 10]))
                sys.exit(0)
except Exception as e:
    print(e)
