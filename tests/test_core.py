from pathlib import Path
import sqlite3
import json
import tempfile
import unittest
from unittest.mock import patch
import tomllib
from codex_shared_home import core, cli
from codex_shared_home.configuration import prepare_config,dump_toml

A=r"C:\Users\UserA\.codex"
D=r"D:\CodexShared\home"
MAPS=[{"source":A+r"\worktrees","destination":r"D:\Worktrees","identity_destination":D+r"\worktrees"},
      {"source":A,"destination":D}]

class PathTests(unittest.TestCase):
    def test_long_path_and_boundary(self):
        self.assertEqual(core.map_path("\\\\?\\"+A+r"\sessions\a",MAPS),D+r"\sessions\a")
        self.assertEqual(core.map_path(A+r"-other\sessions",MAPS),A+r"-other\sessions")
    def test_specific_mapping_first(self):
        self.assertEqual(core.map_path(A+r"\worktrees\a",MAPS),r"D:\Worktrees\a")
    def test_aliases_survive_unique_identity_constraints(self):
        rows=[("t","worktree",A+r"\worktrees\a"),("t","worktree",A.replace("\\","/")+"/worktrees/a")]
        result=core.attachment_identity_plan(rows,MAPS)
        self.assertNotEqual(result[0][3],result[1][3])
    def test_identity_collision_stops(self):
        with self.assertRaises(ValueError):core.attachment_identity_plan([("t","x",A),("t","x",A)],MAPS)
    def test_prompt_text_untouched(self):
        text="Do not change "+A
        self.assertEqual(core.map_path(text,MAPS),text)
    def test_global_prompt_history_is_not_rewritten(self):
        original={"electron-persisted-atom-state":{"prompt-history":[A]},
                  "thread-workspace-root-hints":{"t":A},
                  "app-server-projects-migration-by-host":{"local:"+A:True}}
        result=core.transform_global(original,MAPS,A,D)
        self.assertEqual(result["electron-persisted-atom-state"],original["electron-persisted-atom-state"])
        self.assertEqual(result["thread-workspace-root-hints"]["t"],D)
        self.assertIn("local:"+D,result["app-server-projects-migration-by-host"])

class SnapshotTests(unittest.TestCase):
    def test_private_files_not_opened_and_browser_code_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);home=base/"source";home.mkdir()
            (home/"auth.json").write_text("DUMMY_DO_NOT_READ")
            (home/"secrets").mkdir();(home/"secrets/codex_auth.age").write_text("DUMMY_DO_NOT_READ")
            (home/"browser").mkdir();(home/"browser/Cookies").write_text("DUMMY_DO_NOT_READ")
            code=home/"plugins/cache/bundled/browser/version/code.js";code.parent.mkdir(parents=True);code.write_text("/* fixture */")
            original=Path.open
            def guarded(path,*args,**kwargs):
                if core.private_name(path.name):raise AssertionError("Credential-looking file opened")
                return original(path,*args,**kwargs)
            with patch.object(Path,"open",guarded):
                result=core.snapshot_core(home,base/"snapshot")
            self.assertTrue((base/"snapshot"/code.relative_to(home)).is_file())
            self.assertFalse((base/"snapshot/auth.json").exists())
            self.assertEqual(len(result["files"]),1)
    def test_existing_snapshot_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);(base/"source").mkdir();(base/"target").mkdir()
            with self.assertRaises(FileExistsError):core.snapshot_core(base/"source",base/"target")
    def test_paginated_history_database_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);home=base/"source";home.mkdir()
            c=sqlite3.connect(home/"thread_history_1.sqlite");c.execute("CREATE TABLE thread_items(item_id TEXT,item_json TEXT)")
            c.execute("INSERT INTO thread_items VALUES ('i','fixture')");c.commit();c.close()
            result=core.snapshot_core(home,base/"snapshot")
            self.assertEqual(result["database_checks"]["thread_history_1.sqlite"],"ok")
            self.assertEqual(core.digest_file(home/"thread_history_1.sqlite"),core.digest_file(base/"snapshot/thread_history_1.sqlite"))

class MutationTests(unittest.TestCase):
    def test_stale_plan_rolls_back_all_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);c=sqlite3.connect(root/"state_5.sqlite")
            c.execute("CREATE TABLE threads(id TEXT PRIMARY KEY,rollout_path TEXT,cwd TEXT)")
            c.executemany("INSERT INTO threads VALUES (?,?,?)",[("1","a","x"),("2","b","y")]);c.commit();c.close()
            plan=[{"table":"threads","id":"1","field":"cwd","old":"x","new":"new"},
                  {"table":"threads","id":"2","field":"cwd","old":"STALE","new":"new"}]
            with self.assertRaises(RuntimeError):core.apply_thread_plan(root,plan)
            c=sqlite3.connect(root/"state_5.sqlite");self.assertEqual(c.execute("SELECT cwd FROM threads WHERE id='1'").fetchone()[0],"x");c.close()
    def test_missing_candidate_database_refused_without_creating_it(self):
        with tempfile.TemporaryDirectory() as folder:
            candidate=Path(folder)/"candidate";candidate.mkdir()
            with self.assertRaises(FileNotFoundError):core.apply_thread_plan(candidate,[])
            self.assertFalse((candidate/"state_5.sqlite").exists())
    def test_config_preserves_policy_and_custom_servers(self):
        cfg={"model":"example-model","sandbox_mode":"read-only","approval_policy":"on-request",
             "mcp_servers":{"custom":{"command":"example-tool"},"node_repl":{"command":r"C:\Users\UserA\AppData\Local\OpenAI\Codex\runtimes\v\bin\node_repl.exe"}},
             "skills":{"config":[{"path":A+r"\skills\example\SKILL.md","enabled":False}]}}
        settings={"participants":[{"profile":r"C:\Users\UserA"}],"path_mappings":MAPS}
        result=prepare_config(cfg,settings,r"C:\Users\UserA")
        self.assertEqual(result["sandbox_mode"],"read-only")
        self.assertEqual(result["approval_policy"],"on-request")
        self.assertEqual(result["mcp_servers"]["custom"],cfg["mcp_servers"]["custom"])
        self.assertNotIn("node_repl",result["mcp_servers"])
        self.assertEqual(tomllib.loads(dump_toml(result)),result)
        self.assertEqual(cfg["skills"]["config"][0]["path"],A+r"\skills\example\SKILL.md")
    def test_permission_and_auth_overrides_refused(self):
        for pointer in [["sandbox_mode"],["windows","sandbox"],["cli_auth_credentials_store"]]:
            with self.assertRaises(ValueError):
                prepare_config({},{"participants":[],"ordinary_config_overrides":[(pointer,"unsafe")]},r"C:\Users\UserA")
    def test_toml_unicode_and_inline_tables(self):
        obj={"标题":"示例","values":[{"enabled":True,"roots":[D]}]}
        self.assertEqual(tomllib.loads(dump_toml(obj)),obj)
class CliGuardTests(unittest.TestCase):
    def settings(self, root):
        return {"shared_root":str(root),"participants":[{"profile":str(root)}]}
    def invoke_prepare(self, root, apply=False):
        argv=["--settings",str(root/"settings.json"),"prepare-config","--profile",str(root)]
        if apply:argv.append("--apply")
        with patch.object(cli,"load_settings",return_value=self.settings(root)), \
             patch.object(cli,"active_codex_processes",return_value=[]):
            cli.main(argv)
    def test_prepare_config_refuses_redirected_home(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);outside=root/"outside";outside.mkdir()
            home=root/"home"
            try:home.symlink_to(outside,target_is_directory=True)
            except OSError:self.skipTest("directory symlinks unavailable")
            with self.assertRaises(ValueError):self.invoke_prepare(root)
    def test_prepare_config_refuses_redirected_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);home=root/"home";home.mkdir()
            (home/"SHARED-HOME-READY.json").write_text("{}",encoding="utf-8")
            target=root/"outside.toml";target.write_text('model = "fixture"\n',encoding="utf-8")
            config=home/"config.toml"
            try:config.symlink_to(target)
            except OSError:self.skipTest("file symlinks unavailable")
            with self.assertRaises(ValueError):self.invoke_prepare(root,apply=True)
            self.assertEqual(target.read_text(encoding="utf-8"),'model = "fixture"\n')
    def test_windows_drive_roots_and_unc_settings_rejected(self):
        participants=[{"sid":"S-1-5-21-1-2-3-4","profile":r"C:\Users\A","source_home":r"C:\Users\A\.codex"},
                      {"sid":"S-1-5-21-1-2-3-5","profile":r"C:\Users\B","source_home":r"C:\Users\B\.codex"}]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"settings.json"
            for root in ("C:\\",r"\\server\share\Codex"):
                path.write_text(json.dumps({"shared_root":root,"participants":participants}),encoding="utf-8")
                with self.assertRaises(ValueError):core.load_settings(path)

if __name__=="__main__":unittest.main()
