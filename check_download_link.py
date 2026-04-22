# Test script to check if download link exists in index.html

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

if '从电脑上下载' in content:
    print('Download link found in index.html!')
    # Find the exact line
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        if '从电脑上下载' in line:
            print('Line', i, ':', line.strip())
else:
    print('Download link NOT found in index.html!')

print('\nFile size:', len(content), 'bytes')
