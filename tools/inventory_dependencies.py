#!/usr/bin/env python3
"""Record embedded Paperclip dependency JAR hashes and included notice files."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('artifact', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
records = []
with zipfile.ZipFile(args.artifact) as outer:
    for name in sorted(outer.namelist()):
        if not name.startswith('META-INF/libraries/') or not name.endswith('.jar'):
            continue
        data = outer.read(name)
        with zipfile.ZipFile(io.BytesIO(data)) as inner:
            notices = []
            for item in inner.namelist():
                base = item.rsplit('/', 1)[-1].lower()
                if not item.endswith('/') and (base.startswith(('license', 'licence', 'notice', 'copying'))):
                    notices.append(item)
        records.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'embedded_notices': notices})
result = {'artifact': args.artifact.name, 'artifact_sha256': hashlib.sha256(args.artifact.read_bytes()).hexdigest(),
          'scope': 'Embedded dependency JARs and notice filenames; absence of a filename is not a license conclusion.',
          'dependencies': records}
args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
print(f'Recorded {len(records)} embedded dependency JARs in {args.output}')
