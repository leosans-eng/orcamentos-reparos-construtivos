# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [
    ('vicios_construtivos.json', '.'),
    ('icone.ico', '.'),
    ('assets/icons/excel24.png', 'assets/icons'),
    ('assets/icons/excel-preto.png', 'assets/icons'),
    ('assets/modelos/modelo1.png', 'assets/modelos'),
    ('assets/modelos/modelo2.png', 'assets/modelos'),
    ('assets/modelos/modelo3.png', 'assets/modelos'),
    ('assets/modelos/modelo4.png', 'assets/modelos'),
    ('assets/modelos/Modelo 1 - Word.docx', 'assets/modelos'),
    ('assets/modelos/Modelo 3 - Word.docx', 'assets/modelos'),
]
datas += collect_data_files('certifi')


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'atualizacao',
        'app_paths',
        'certifi',
        'num2words',
        'docx',
        'core.formatador_sinapi',
        'core.formatador_sinapi.modelo1',
        'core.formatador_sinapi.modelo2',
        'core.formatador_sinapi.modelo3',
        'core.formatador_sinapi.word_modelo1',
        'core.formatador_sinapi.word_modelo3',
        'windnd',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ORC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icone.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ORC',
)
