#!/usr/bin/env python3
"""Inspect known projectless chat directories; apply only reviewed, unchanged candidates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import uuid


def load(path):
    return json.loads(path.read_text())


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        json.dump(data, stream, ensure_ascii=False, indent=2)
    temporary.replace(path)


def overlaps(a, b):
    return a == b or a in b.parents or b in a.parents


def database(codex):
    paths = list(codex.glob('state_*.sqlite'))
    paths = [p for p in paths if re.fullmatch(r'state_\d+\.sqlite', p.name)]
    if not paths:
        raise ValueError('No supported local state database; cleanup disabled.')
    path = max(paths, key=lambda p: int(p.stem.split('_')[-1]))
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as con:
        con.execute('PRAGMA query_only=ON')
        # Includes archived chats and child agents. Unknown schema fails closed.
        threads = list(con.execute('SELECT id, cwd, archived FROM threads'))
        projects = [Path(p).expanduser().resolve() for (p,) in con.execute('SELECT path FROM project_roots')]
    return threads, projects


def metadata(path):
    """Never traverse symlinks, read contents, or enter a repository."""
    entries, total, repository = [], 0, False
    def fail(error):
        raise error

    for base, dirs, files in os.walk(path, followlinks=False, onerror=fail):
        if '.git' in dirs or '.git' in files:
            repository = True
        dirs[:] = [d for d in dirs if d != '.git']
        for name in sorted(set(dirs + files)):
            item = Path(base) / name
            s = item.lstat()
            entries.append([str(item.relative_to(path)), s.st_mode, s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns])
            if item.is_file() and not item.is_symlink():
                total += s.st_size
    s = path.lstat()
    stamp = [s.st_dev, s.st_ino, s.st_mtime_ns, sorted(entries)]
    fingerprint = hashlib.sha256(json.dumps(stamp).encode()).hexdigest()
    return {'bytes': total, 'files': [e[0] for e in sorted(entries)], 'fingerprint': fingerprint, 'repository': repository}


def scan(codex, root, inventory):
    threads, projects = database(codex)
    complete = inventory.get('complete') is True
    app_threads = inventory.get('active', []) + inventory.get('archived', [])
    if complete and (not isinstance(inventory.get('active'), list) or not isinstance(inventory.get('archived'), list)
                     or not isinstance(inventory.get('project_roots'), list)):
        raise ValueError('Incomplete application inventory.')
    live_ids = {row[0] for row in threads} | {row['id'] for row in app_threads}
    protected = [Path(row[1]).expanduser().resolve() for row in threads if row[1]]
    protected += [Path(row['cwd']).expanduser().resolve() for row in app_threads if row.get('cwd')]
    protected += projects + [Path(p).expanduser().resolve() for p in inventory.get('project_roots', [])]
    protected.append(Path.cwd().resolve())
    state_path = codex / 'chat-cleanup/ownership.json'
    known = load(state_path) if state_path.exists() else {}
    global_state = load(codex / '.codex-global-state.json')
    mapping = global_state['thread-projectless-output-directories']
    if not isinstance(mapping, dict) or not isinstance(known, dict):
        raise ValueError('Unsupported projectless ownership schema.')
    for tid, output in mapping.items():
        path = Path(output).expanduser()
        if path.name == 'outputs' and path.is_absolute():
            owners = known.setdefault(str(path.parent), [])
            if tid not in owners:
                owners.append(tid)
    directories = set(root.glob('????-??-??/*'))
    visual = codex / 'visualizations'
    for original, owners in list(known.items()):
        for tid in owners:
            # UUID validation prevents metadata from injecting arbitrary paths.
            uuid.UUID(tid)
            for path in visual.glob('????/??/??/' + tid):
                known.setdefault(str(path), [])
                if tid not in known[str(path)]:
                    known[str(path)].append(tid)
    directories |= {Path(p) for p in known}
    rows = []
    for path in sorted(directories):
        if not path.exists() and not path.is_symlink():
            continue
        # Only exact generated-directory shapes are eligible; never resolve away a symlink.
        workspace = path.parent.parent == root and re.fullmatch(r'\d{4}-\d{2}-\d{2}', path.parent.name)
        try:
            parts = path.relative_to(visual).parts
            visualization = len(parts) == 4 and all(re.fullmatch(pattern, part) for pattern, part in zip(
                [r'\d{4}', r'\d{2}', r'\d{2}', r'[0-9a-f-]{36}'], parts))
        except ValueError:
            visualization = False
        if not (workspace or visualization):
            continue
        if not path.is_dir() or path.is_symlink() or path.resolve() != path:
            rows.append({'path': str(path), 'status': 'protected', 'reason': 'symlink or non-directory'})
            continue
        owners = known.get(str(path), [])
        if live_ids.intersection(owners) or any(overlaps(path, p) for p in protected):
            rows.append({'path': str(path), 'owners': owners, 'status': 'protected', 'reason': 'existing/archived chat, current directory, or project reference'})
            continue
        info = metadata(path)
        status = 'eligible' if owners and complete and not info['repository'] else 'unverified'
        reason = ('no current references; explicit projectless ownership' if status == 'eligible' else
                  'repository present' if info['repository'] else 'ownership unknown' if not owners else 'complete application inventory required')
        rows.append(dict(path=str(path), owners=owners, status=status, reason=reason, **info))
    save(state_path, known)
    return {'created_at': time.time(), 'codex_home': str(codex), 'root': str(root),
            'inventory_hash': hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(),
            'rows': rows, 'candidates': [r['path'] for r in rows if r['status'] == 'eligible']}


def apply(report, codex, root, inventory):
    if sys.platform != 'darwin':
        raise ValueError('Only scanning is supported on this operating system.')
    if not inventory.get('complete') or time.time() - report['created_at'] > 300:
        raise ValueError('Refresh the complete application inventory and scan before cleanup (5 minute limit).')
    current = scan(codex, root, inventory)
    if any(report[k] != current[k] for k in ['codex_home', 'root', 'inventory_hash']):
        raise ValueError('Report context changed; rescan.')
    old = {r['path']: r for r in report['rows'] if r['status'] == 'eligible'}
    new = {r['path']: r for r in current['rows'] if r['status'] == 'eligible'}
    selected = report['candidates']
    # Validate the whole batch before moving the first directory.
    for p in selected:
        if p not in old or p not in new or old[p]['fingerprint'] != new[p]['fingerprint']:
            raise ValueError('Candidate changed or is now referenced; rescan: ' + p)
    if not selected:
        return {'moved': [], 'bytes_moved': 0}
    trash = Path.home() / '.Trash'
    if not trash.is_dir() or trash.is_symlink():
        raise ValueError('macOS Trash is not available; no permanent-delete fallback.')
    results = []
    for p in selected:
        # Recheck database and filesystem immediately before each atomic move.
        fresh = {r['path']: r for r in scan(codex, root, inventory)['rows'] if r['status'] == 'eligible'}
        if p not in fresh or fresh[p]['fingerprint'] != old[p]['fingerprint']:
            raise ValueError('Candidate changed; previous moves remain in Trash: ' + p)
        target = trash / ('codex-chat-' + uuid.uuid4().hex + '-' + Path(p).name)
        os.rename(p, target)
        if Path(p).exists() or not target.is_dir():
            raise ValueError('Could not verify Trash move: ' + p)
        results.append({'original': p, 'trash': str(target), 'bytes': old[p]['bytes']})
        # Persist each successful move even if a later candidate is denied.
        save(codex / 'chat-cleanup/last-cleanup.json', {'moved': results})
    return {'moved': results, 'bytes_moved': sum(r['bytes'] for r in results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--apply-report', type=Path)
    args = parser.parse_args()
    codex = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser().resolve()
    root = (Path.home() / 'Documents/Codex').resolve()
    inventory = load(args.inventory) if args.inventory else {}
    if args.apply_report:
        result = apply(load(args.apply_report), codex, root, inventory)
    else:
        result = scan(codex, root, inventory)
        if args.report:
            save(args.report, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as error:
        print('Cleanup stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
