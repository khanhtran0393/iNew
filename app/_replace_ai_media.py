import os
import shutil

# Define paths
original_pyc = r'D:\iNew\app\services\__pycache__\ai_media.cpython-313.pyc'
current_file = r'D:\iNew\app\services\ai_media.py'
reconstructed_file = r'D:\iNew\app\services\ai_media_reconstructed_final.py'

print('=== File size check ===')
print(f'Pre-edit .pyc: {os.path.getsize(original_pyc)} bytes')
print(f'Current ai_media.py: {os.path.getsize(current_file)} bytes')
print(f'Reconstructed file: {os.path.getsize(reconstructed_file)} bytes')

# Check if the reconstructed file is ready to replace
if os.path.exists(reconstructed_file):
    print('\n=== Ready to replace ===')
    print('Current file will be backed up...')
    
    # Backup the current file
    backup_path = r'D:\iNew\app\services\ai_media_backup.py'
    shutil.copy2(current_file, backup_path)
    print(f'Backed up current file to: {backup_path}')
    
    # Replace the current file with the reconstructed file
    shutil.copy2(reconstructed_file, current_file)
    print(f'Replaced {current_file} with {reconstructed_file}')
    
    # Verify the new file size
    new_size = os.path.getsize(current_file)
    print(f'New file size: {new_size} bytes')
    print(f'Difference from original .pyc: {os.path.getsize(original_pyc) - new_size} bytes')
    
    print('\n=== Verification ===')
    with open(current_file, 'r', encoding='utf-8') as f:
        content = f.read()
        print(f'File now contains {len(content)} characters')
        print('First 100 chars:', content[:100])
        print('Last 100 chars:', content[-100:])
else:
    print('Reconstructed file not found!')