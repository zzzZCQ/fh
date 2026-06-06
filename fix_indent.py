
with open(r'd:\fh\services.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 修复 indentation issue: lines 331-432 have wrong indentation (should be inside try block)
# They currently have 4 spaces, should have 8
for i in range(330, 432):
    if i &lt; len(lines):
        line = lines[i]
        if line.startswith('    '):
            # Add another 4 spaces (total 8)
            lines[i] = '    ' + line

with open(r'd:\fh\services.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Indentation fixed')
