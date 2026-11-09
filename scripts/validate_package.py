"""Validate distributable files and generated YAML without contacting equipment."""
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'custom_components/pzp_web'


class ExampleLoader(yaml.SafeLoader):
    pass


ExampleLoader.add_constructor('!secret', lambda loader, node: 'EXAMPLE_SECRET')
ExampleLoader.add_constructor('!include', lambda loader, node: loader.construct_scalar(node))


def validate():
    manifest = json.loads((COMPONENT / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['domain'] == 'pzp_web'
    assert manifest['codeowners'] and manifest['issue_tracker']
    assert len(list((ROOT / 'custom_components').iterdir())) == 1
    files = [p for p in ROOT.rglob('*') if p.is_file()
             and not any(part in {'.git', '__pycache__', '.venv', 'node_modules', 'dist'} for part in p.relative_to(ROOT).parts)]
    for path in files:
        if path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        if path.suffix == '.json':
            json.loads(path.read_text(encoding='utf-8'))
        if path.suffix in {'.yaml', '.yml'}:
            yaml.load(path.read_text(encoding='utf-8'), Loader=ExampleLoader)
        if path.suffix in {'.js', '.mjs'}:
            subprocess.run(['node', '--check', str(path)], check=True)
        if path.suffix in {'.py', '.js', '.json', '.md', '.yaml', '.yml', '.mjs'}:
            text = path.read_text(encoding='utf-8')
            # Public examples use documentation-only addresses, never real household data.
            assert not re.search(r'192\.168\.\d+\.\d+|(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', text), path
            assert not re.search(r'(?:github_pat_|ghp_)[A-Za-z0-9_]{20,}|(?m:^-----BEGIN [A-Z ]*PRIVATE KEY-----$)', text), path
            assert not re.search(r'\b01[A-HJKMNP-TV-Z0-9]{24}\b', text), path
    cards = ['pzp-schedule-card.js', 'pzp-history-card.js', 'pzp-admin-card.js', 'pzp-card-utils.js']
    assert all((COMPONENT / 'www' / name).is_file() for name in cards)
    assert (COMPONENT / 'brand/icon.png').is_file()
    assert (ROOT / 'LICENSE').is_file()
    hub = yaml.load((ROOT / 'examples/modbus/pzp_modbus.yaml').read_text(encoding='utf-8'), Loader=ExampleLoader)
    assert hub[0]['host'] == 'EXAMPLE_SECRET'
    templates = yaml.safe_load((ROOT / 'examples/modbus/pzp_template.yaml').read_text(encoding='utf-8'))
    assert templates and hub[0]['type'] == 'tcp'
    print(f'PASS: {len(files)} public files, JSON/YAML/Python/JavaScript, local-data checks and HACS payload')


if __name__ == '__main__':
    validate()
