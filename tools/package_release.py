#!/usr/bin/env python3
"""Package the current YunqiMC source and already-built server artifact."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
ARTIFACT = DIST / 'yunqimc-server-1.21.11-0.1.0-alpha.1.jar'
SOURCE = DIST / 'YunqiMC-0.1.0-alpha.1-source.zip'
PAPER = 'c5eb0790f199da6c38d0a650e1e5cd5415b28185'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def member(name, data):
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o755 if name == 'gradlew' else 0o644) << 16
    return info, data

def main():
    if not ARTIFACT.is_file():
        raise SystemExit('Build and stage the YunqiMC Paperclip JAR in dist first.')
    raw = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT)
    names = sorted(set(raw.decode('utf8').split('\0')) - {''})
    contents = [(name.replace('\\', '/'), (ROOT / name).read_bytes()) for name in names if (ROOT / name).is_file()]
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT))
    manifest = {'yunqimc_version': '0.1.0-alpha.1', 'minecraft_version': '1.21.11',
                'paper_commit': PAPER, 'git_head': head, 'working_tree_dirty': dirty,
                'server_jar_sha256': sha(ARTIFACT.read_bytes()),
                'source_sha256': {name: sha(data) for name, data in contents}}
    with zipfile.ZipFile(SOURCE, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for name, data in contents:
            out.writestr(*member(name, data))
        out.writestr(*member('yunqimc-source-manifest.json', (json.dumps(manifest, indent=2) + '\n').encode('utf8')))
    with zipfile.ZipFile(SOURCE) as check:
        if check.testzip() is not None:
            raise RuntimeError('Source archive integrity check failed')
    for name in ('使用说明.md', '验证记录.md', 'architecture.md', 'benchmark.md'):
        shutil.copy2(ROOT / 'docs' / name, DIST / name)
    for name in ('LICENSE', 'NOTICE.md'):
        shutil.copy2(ROOT / name, DIST / name)
    shutil.copytree(ROOT / 'licenses', DIST / 'licenses', dirs_exist_ok=True)
    with (DIST / 'SHA256SUMS.txt').open('w', encoding='utf8', newline='\n') as out:
        for path in (ARTIFACT, SOURCE):
            out.write(sha(path.read_bytes()) + '  ' + path.name + '\n')
    print(f'Packaged {len(contents)} source files; source Git HEAD {head}; dirty={dirty}')
    print(f'JAR SHA256 {manifest["server_jar_sha256"]}')
    print(f'Source ZIP SHA256 {sha(SOURCE.read_bytes())}')

if __name__ == '__main__':
    main()
