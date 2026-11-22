"""Export the declarations of the whole proof from its published build cache.

Usage (from this folder, after fetch_cache.py):

    RH_PROOF=/path/to/riemann-hypothesis python3 -I run_export.py [--workers N] [--batch M]

RH_PROOF is a checkout of the proof; it is used only to select its Lean toolchain.

The cache holds one compressed archive per module (4.94 GB in total). Unpacked
they take about 99 GB, so they are never all on disk at once: modules are
unpacked in batches into `tmp/`, their declarations are written to
`out/part_XXXX.tsv` by ExportModules.lean, and the batch is deleted.

Finished batches are skipped, so the script can be re-run after an interruption.
"""
import concurrent.futures
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# A checkout of the proof; used only to pick its Lean toolchain (set RH_PROOF to its path).
PROOF = os.environ.get('RH_PROOF', os.path.join(HERE, '..', '..', '..', 'riemann-hypothesis'))


def opt(name, default):
    if name in sys.argv:
        return int(sys.argv[sys.argv.index(name) + 1])
    return default


def tool(name):
    lean = subprocess.check_output(['elan', 'which', 'lean'], cwd=PROOF, text=True).strip()
    return os.path.join(os.path.dirname(lean), name)


def run_batch(index, rows, leantar, lean):
    part = os.path.join(HERE, 'out', f'part_{index:04d}.tsv')
    if os.path.exists(part):
        return index, len(rows), 'skipped'
    tmp = os.path.join(HERE, 'tmp', f'batch_{index:04d}')
    shutil.rmtree(tmp, ignore_errors=True)
    jobs, listing, dirs = [], [], set()
    for name, dep_hash, artifact, digest in rows:
        archive = os.path.join(HERE, 'cache', 'artifacts', artifact)
        with open(archive, 'rb') as fh:
            if hashlib.file_digest(fh, 'sha256').hexdigest() != digest:
                raise ValueError(f'checksum mismatch for {name}')
        rel = name.split('.')
        lib = os.path.join(tmp, 'lib', *rel[:-1])
        ir = os.path.join(tmp, 'ir', *rel[:-1])
        dirs.update((lib, ir))
        jobs.append({'file': archive, 'hash': dep_hash, 'base': [lib, ir]})
        listing.append(f'{name}\t{os.path.join(lib, rel[-1])}.olean')
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    env = dict(os.environ, RUST_MIN_STACK='8388608')
    subprocess.run([leantar, '--jobs', '4', '-f', '-x', '-j', '-'], input=json.dumps(jobs),
                   text=True, env=env, check=True, stdout=subprocess.DEVNULL)
    list_file = os.path.join(tmp, 'list.txt')
    with open(list_file, 'w') as fh:
        fh.write('\n'.join(listing) + '\n')
    res = subprocess.run([lean, '--run', os.path.join(HERE, 'ExportModules.lean'), list_file,
                          part + '.partial'], capture_output=True, text=True, cwd=PROOF)
    shutil.rmtree(tmp, ignore_errors=True)
    if res.returncode != 0 or f'{len(rows)} modules exported, 0 failed' not in res.stdout:
        raise RuntimeError(f'batch {index}: {res.stdout[-300:]} {res.stderr[-600:]}')
    os.replace(part + '.partial', part)
    return index, len(rows), 'done'


def main():
    workers, size = opt('--workers', 4), opt('--batch', 3000)
    with gzip.open(os.path.join(HERE, 'modules.jsonl.gz')) as fh:
        rows = [json.loads(line) for line in fh.read().splitlines()[1:]]
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    leantar, lean = tool('leantar'), tool('lean')
    batches = [rows[i:i + size] for i in range(0, len(rows), size)]
    print(f'{len(rows)} modules in {len(batches)} batches, {workers} at a time', flush=True)
    done = 0
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(run_batch, i, b, leantar, lean) for i, b in enumerate(batches)]
        for f in concurrent.futures.as_completed(futures):
            index, n, status = f.result()
            done += n
            print(f'batch {index:4d} {status}: {done}/{len(rows)} modules', flush=True)


if __name__ == '__main__':
    main()
