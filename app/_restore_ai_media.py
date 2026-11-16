import os, shutil
# Restore the true (truncated) current file, remove bogus reconstruction
cur = r'D:\iNew\app\services\ai_media.py'
bak = r'D:\iNew\app\services\ai_media_backup.py'
if os.path.exists(bak):
    shutil.copy2(bak, cur)
    print('restored', cur, os.path.getsize(cur), 'bytes')
for p in [r'D:\iNew\app\services\ai_media_reconstructed.py',
          r'D:\iNew\app\services\ai_media_reconstructed_v2.py',
          r'D:\iNew\app\services\ai_media_reconstructed_v3.py',
          r'D:\iNew\app\services\ai_media_reconstructed_final.py',
          r'D:\iNew\app\services\ai_media_original_reconstructed.py',
          r'D:\iNew\app\services\ai_media_decompiled.py']:
    if os.path.exists(p):
        os.remove(p)
        print('removed', p)
