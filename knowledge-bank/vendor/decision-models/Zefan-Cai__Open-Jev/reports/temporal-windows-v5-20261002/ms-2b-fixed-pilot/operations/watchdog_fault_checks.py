import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
spec=importlib.util.spec_from_file_location('watchdog',Path(__file__).with_name('watchdog.py'))
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
identity={'pid':123,'start_ticks':456,'uid':1000}
class WatcherFaults(unittest.TestCase):
 def test_dead_pid_race_and_changed_birth_are_not_signaled(self):
  other={'pid':124,'start_ticks':457,'uid':1000}
  with patch.object(w,'members',return_value=[identity,other]),patch.object(w,'process_identity',create=True,side_effect=[identity,{**other,'start_ticks':999}]),patch.object(w.os,'getsid',return_value=123),patch.object(w.os,'kill',side_effect=ProcessLookupError) as kill:
   w.signal_members(identity,15)
   kill.assert_called_once_with(123,15)
 def test_drain_cleans_residual_session_after_normal_leader_exit(self):
  with patch.object(w,'signal_members') as signal_members,patch.object(w,'members',side_effect=[[identity],[],[]]),patch.object(w.time,'sleep'):
   self.assertTrue(w.drain(identity))
   signal_members.assert_called_once_with(identity,w.signal.SIGTERM)
 def run_case(self,interrupted,cleanup):
  import scripts.temporal_pilot_lease as lease_module
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);lease=root/'lease.json'
   lease.write_text(json.dumps({'status':'running','controller_stamp':'frozen','process_identity':identity}))
   child=Mock(pid=123,returncode=-15 if interrupted else 0)
   if interrupted:child.poll.side_effect=KeyboardInterrupt
   else:child.poll.return_value=0
   request={'source_directory':str(Path.cwd()),'log':str(root/'log'),'command':['fixture-only'],'gpu_uuid':'GPU-fixture','lease':str(lease),'controller_stamp':'frozen','watchdog_receipt':str(root/'receipt.json')}
   with patch.object(w.subprocess,'Popen',return_value=child),patch.object(lease_module,'process_identity',return_value=identity),patch.object(w,'drain',return_value=cleanup) as drain,patch.object(w,'members',return_value=[]),patch.object(w.signal,'pthread_sigmask'):
    code=w.run(request)
    drain.assert_called_once_with(identity)
   return code,json.loads(lease.read_text())
 def test_interruption_always_drains_owned_session_in_finally(self):
  code,lease=self.run_case(True,True)
  self.assertEqual(code,1);self.assertEqual(lease['pilot_exit_status'],'interrupted');self.assertTrue(lease['session_cleanup_confirmed'])
 def test_remaining_session_never_reports_success(self):
  code,lease=self.run_case(False,False)
  self.assertEqual(code,1);self.assertEqual(lease['pilot_exit_status'],'failed');self.assertFalse(lease['session_cleanup_confirmed'])
 def test_real_sigterm_during_finally_does_not_abandon_cleanup(self):
  program='''
import importlib.util,json,os,signal,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
import scripts.temporal_pilot_lease as lease_module
signal.pthread_sigmask(signal.SIG_UNBLOCK,{signal.SIGTERM,signal.SIGINT})
spec=importlib.util.spec_from_file_location('watchdog',WATCHDOG_PATH)
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
identity={'pid':123,'start_ticks':456,'uid':1000}
signal.signal(signal.SIGTERM,w.interrupted)
def drain(identity):
 os.kill(os.getpid(),signal.SIGTERM)
 return True
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);lease=root/'lease.json'
 lease.write_text(json.dumps({'status':'running','controller_stamp':'frozen','process_identity':identity}))
 child=Mock(pid=123,returncode=0);child.poll.return_value=0
 request={'source_directory':str(Path.cwd()),'log':str(root/'log'),'command':['fixture-only'],'gpu_uuid':'GPU-fixture','lease':str(lease),'controller_stamp':'frozen','watchdog_receipt':str(root/'receipt.json')}
 with patch.object(w.subprocess,'Popen',return_value=child),patch.object(lease_module,'process_identity',return_value=identity),patch.object(w,'drain',side_effect=drain),patch.object(w,'members',return_value=[]):
  assert w.run(request)==0
 assert json.loads((root/'receipt.json').read_text())['session_cleanup_confirmed']
 assert json.loads(lease.read_text())['pilot_exit_status']=='complete'
'''.replace('WATCHDOG_PATH',repr(str(Path(__file__).with_name('watchdog.py').resolve())))
  result=subprocess.run([sys.executable,'-c',program],capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=='__main__':unittest.main()
