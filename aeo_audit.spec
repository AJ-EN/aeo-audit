# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

def safe_collect(package_name):
    try:
        return collect_data_files(package_name)
    except Exception:
        return []

datas = [
    ('aeo_audit/templates', 'aeo_audit/templates'),
    ('aeo_audit/config.yaml', 'aeo_audit'),
    ('aeo_audit/benchmarks/percentiles_v1.json', 'aeo_audit/benchmarks'),
]

datas += safe_collect('mf2py')
datas += safe_collect('extruct')
datas += safe_collect('weasyprint')
datas += safe_collect('openapi_spec_validator')
datas += safe_collect('openapi_schema_validator')
datas += safe_collect('jsonschema')
datas += safe_collect('jsonschema_specifications')

a = Analysis(
    ['aeo_audit/cli.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'playwright.async_api',
        'playwright._impl._api_structures',
        'extruct',
        'openapi_spec_validator',
        'jsonschema',
        'cryptography',
        'jose',
        'dns',
        'weasyprint',
        'jinja2',
        'rich',
        'click',
        'yaml',
        'aeo_audit.checks.discovery',
        'aeo_audit.checks.identity',
        'aeo_audit.checks.capabilities',
        'aeo_audit.checks.commerce',
        'aeo_audit.checks.trust',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='aeo-audit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
