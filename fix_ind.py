with open('fast_sniper.py', 'r') as f:
    lines = f.readlines()

for i in range(178, 228):
    if lines[i].strip():
        lines[i] = "    " + lines[i]

with open('fast_sniper.py', 'w') as f:
    f.writelines(lines)
