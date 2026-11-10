import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('cleanup', Path(__file__).resolve().parents[1]/'scripts/cleanup.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve()
        self.codex = self.home/'.codex'
        self.root = self.home/'Documents/Codex'
        self.codex.mkdir()
        (self.home/'.Trash').mkdir()
        self.db = self.codex/'state_5.sqlite'
        with sqlite3.connect(self.db) as c:
            c.executescript('CREATE TABLE threads(id TEXT,cwd TEXT,archived INTEGER); CREATE TABLE project_roots(path TEXT);')
        self.mapping = {}
        self.inventory = {'complete': True, 'active': [], 'archived': [], 'project_roots': []}
        self.patcher = patch.object(m.Path, 'home', return_value=self.home)
        self.patcher.start()
        self.cwd_patch = patch.object(m.Path, 'cwd', return_value=self.home/'runner')
        self.cwd_patch.start()
        self.addCleanup(self.cwd_patch.stop)
        self.platform = patch.object(m.sys, 'platform', 'darwin')
        self.platform.start()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.platform.stop)

    def folder(self, name, known=True):
        tid = str(uuid.uuid4())
        p = self.root/'2026-01-01'/name
        (p/'work').mkdir(parents=True)
        (p/'work/file.txt').write_text('example')
        if known:
            self.mapping[tid] = str(p/'outputs')
        (self.codex/'.codex-global-state.json').write_text(json.dumps({'thread-projectless-output-directories':self.mapping}))
        return p, tid

    def scan(self):
        return m.scan(self.codex, self.root, self.inventory)

    def row(self, report, path):
        return next(r for r in report['rows'] if r['path']==str(path))

    def test_absent_owned_directory_is_eligible_and_trash_move(self):
        p, _ = self.folder('deleted')
        r = self.scan()
        self.assertEqual(r['candidates'], [str(p)])
        result = m.apply(r,self.codex,self.root,self.inventory)
        self.assertFalse(p.exists())
        self.assertEqual(Path(result['moved'][0]['trash'],'work/file.txt').read_text(),'example')
        self.assertEqual(result['bytes_moved'],7)

    def test_active_archived_shared_and_app_only_references_are_protected(self):
        for archived in [0,1]:
            p, tid = self.folder('active-'+str(archived))
            with sqlite3.connect(self.db) as c:
                c.execute('INSERT INTO threads VALUES(?,?,?)',(tid,str(p),archived))
            self.assertEqual(self.row(self.scan(),p)['status'],'protected')
        p, _ = self.folder('shared')
        with sqlite3.connect(self.db) as c:
            c.execute('INSERT INTO threads VALUES(?,?,0)',('another-chat',str(p/'work')))
        self.assertEqual(self.row(self.scan(),p)['status'],'protected')
        p, tid = self.folder('app-only')
        self.inventory['archived'].append({'id':tid})
        self.assertEqual(self.row(self.scan(),p)['status'],'protected')

    def test_unknown_repository_symlink_and_project_are_not_candidates(self):
        unknown,_ = self.folder('unknown',known=False)
        repo,_ = self.folder('repo')
        (repo/'.git').mkdir()
        project,_ = self.folder('project')
        self.inventory['project_roots'].append(str(project/'work'))
        external = self.home/'external'
        external.mkdir()
        link = self.root/'2026-01-01/link'
        link.symlink_to(external,target_is_directory=True)
        r=self.scan()
        self.assertEqual(r['candidates'],[])
        self.assertEqual(self.row(r,unknown)['status'],'unverified')
        self.assertEqual(self.row(r,repo)['status'],'unverified')
        self.assertEqual(self.row(r,link)['status'],'protected')

    def test_historical_ownership_survives_app_metadata_removal(self):
        p,_=self.folder('old')
        self.scan()
        (self.codex/'.codex-global-state.json').write_text(json.dumps({'thread-projectless-output-directories':{}}))
        self.assertEqual(self.scan()['candidates'],[str(p)])

    def test_missing_inventory_cannot_clean(self):
        p,_=self.folder('old')
        self.inventory={}
        self.assertEqual(self.scan()['candidates'],[])

    def test_changed_file_new_reference_and_forged_path_stop_cleanup(self):
        p,tid=self.folder('changed')
        r=self.scan()
        (p/'work/file.txt').write_text('changed')
        with self.assertRaises(ValueError):m.apply(r,self.codex,self.root,self.inventory)
        r=self.scan()
        with sqlite3.connect(self.db) as c:c.execute('INSERT INTO threads VALUES(?,?,0)',(tid,str(p)))
        with self.assertRaises(ValueError):m.apply(r,self.codex,self.root,self.inventory)
        self.assertTrue(p.exists())
        r=self.scan()
        r['candidates']=[str(self.home)]
        with self.assertRaises(ValueError):m.apply(r,self.codex,self.root,self.inventory)
        self.assertTrue(self.home.exists())

    def test_empty_selection_does_not_require_trash(self):
        self.folder('unknown',known=False)
        r=self.scan()
        (self.home/'.Trash').rmdir()
        self.assertEqual(m.apply(r,self.codex,self.root,self.inventory)['moved'],[])

    def test_visualization_owner_and_protected_current_directory(self):
        p,tid=self.folder('visual')
        v=self.codex/'visualizations/2026/01/01'/tid
        v.mkdir(parents=True)
        (v/'plot.png').write_bytes(b'png')
        self.assertEqual(set(self.scan()['candidates']),{str(p),str(v)})
        with patch.object(m.Path,'cwd',return_value=p):
            self.assertEqual(self.row(self.scan(),p)['status'],'protected')

if __name__=='__main__':unittest.main(verbosity=2)
