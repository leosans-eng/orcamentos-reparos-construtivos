# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [
    ('vicios_construtivos.json', '.'),
    ('icone.ico', '.'),
    ('assets/icons', 'assets/icons'),
    ('assets/modelos', 'assets/modelos'),
]
datas += collect_data_files('certifi')
datas += collect_data_files('docx')
datas += collect_data_files('tksvg')


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
        'tksvg',
        'windnd',
        'core.formatador_sinapi',
        'core.formatador_sinapi.modelo1',
        'core.formatador_sinapi.modelo2',
        'core.formatador_sinapi.modelo3',
        'core.formatador_sinapi.word_modelo1',
        'core.formatador_sinapi.word_modelo3',
        'core.formatador_sinapi.entrada',
        'core.formatador_sinapi.service',
        'core.sinapi_base',
        'core.sinapi_busca',
        'core.importacao_i9',
        'core.exportacao_planilha_orcamento',
        'core.planilha_sintetica',
        'core.orcamento_customizado',
        'core.composicoes_proprias',
        'core.composicoes_proprias_storage',
        'core.etapas_predefinidas',
        'core.etapas_predefinidas_storage',
        'core.orcamento_storage',
        'core.orcamento_storage_local',
        'core.orcamento_conversao',
        'core.offline_bootstrap',
        'core.composicoes_proprias_storage_local',
        'core.etapas_predefinidas_storage_local',
        'core.api_client',
        'core.api_config',
        'core.api_exceptions',
        'ui.dialogo_login',
        'ui.dialogo_admin_usuarios',
        'ui.recarga_catalogo',
        'ui.orcamento_customizado_modulo',
        'ui.selecao_orcamentos_customizado',
        'core.precarga_catalogos',
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
