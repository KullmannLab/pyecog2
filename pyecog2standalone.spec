# -*- mode: python ; coding: utf-8 -*-


block_cipher = None

files2add = [('pyecog2/pyecog2/icons/*.png','pyecog2/icons'),
	     ('pyecog2/pyecog2/HelperHints.md','pyecog2')]

a = Analysis(['pyecog2/pyecog2/main.py'],
             pathex=['/home/mfpleite/PycharmProjects'],
             binaries=[],
             datas=files2add,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='pyecog2standalone',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='pyecog2standalone')
