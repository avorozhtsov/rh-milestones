"""Download the published build cache of the proof: one compressed archive per module.

Usage (from this folder):

    python3 -I fetch_cache.py

Writes modules.jsonl.gz (the list of modules with checksums) and
cache/artifacts/*.ltar, 4.94 GB in total. Needs curl. Files already present are
kept. The archives are verified against the checksums later, by run_export.py.

The cache is the one the community mirror of the proof publishes for commit
e50d098 (the proof as published, plus one added file). See verification/CACHE.md
in https://github.com/leanprover-community/riemann-hypothesis .
"""
import gzip
import hashlib
import json
import os
import subprocess
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 'https://rh-cache.taucetiproject.org'
REVISION = 'e50d09817ad81469f737e8f637561e6ccf86c670'
MANIFEST_SHA256 = '292caa386a620d935cfc736b56fcceaab9fe7073086693b62e899c1ee4725f04'
REPO = 'leanprover-community/riemann-hypothesis'


def main():
    manifest = os.path.join(HERE, 'modules.jsonl.gz')
    if not os.path.exists(manifest):
        request = urllib.request.Request(f'{BASE}/bootstrap/{REVISION}/modules.jsonl.gz',
                                         headers={'User-Agent': 'curl/8'})
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != MANIFEST_SHA256:
            raise SystemExit('manifest checksum mismatch')
        with open(manifest, 'wb') as fh:
            fh.write(data)
    with gzip.open(manifest) as fh:
        rows = [json.loads(line) for line in fh.read().splitlines()[1:]]
    folder = os.path.join(HERE, 'cache', 'artifacts')
    os.makedirs(folder, exist_ok=True)
    have = set(os.listdir(folder))
    todo = sorted({row[2] for row in rows} - have)
    print(f'{len(rows)} modules, {len(todo)} archives to download')
    if not todo:
        return
    config = os.path.join(HERE, 'cache', 'curl.cfg')
    with open(config, 'w') as fh:
        for name in todo:
            fh.write(f'url = "{BASE}/artifacts/{REPO}/{name[:-5]}.art"\n'
                     f'output = "{os.path.join(folder, name)}"\n')
    subprocess.run(['curl', '-s', '--parallel', '--parallel-max', '200', '--retry', '3',
                    '--fail', '-K', config], check=True)
    print('done')


if __name__ == '__main__':
    main()
