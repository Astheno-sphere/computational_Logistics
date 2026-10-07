"""CPU watcher that drains only the registered pilot's session and birth identities."""
import json,os,signal,subprocess,sys,time
from pathlib import Path


def members(identity):
 result=[]
 for directory in Path('/proc').iterdir():
  if not directory.name.isdigit():continue
  try:
   fields=(directory/'stat').read_text().rsplit(')',1)[1].split()
   uid=directory.stat().st_uid
   if fields[0]!='Z' and int(fields[3])==identity['pid'] and uid==identity['uid'] and int(fields[19])>=identity['start_ticks']:
    result.append({'pid':int(directory.name),'start_ticks':int(fields[19]),'uid':uid})
  except (OSError,ValueError):continue
 return result


def signal_members(identity,signum):
 for member in members(identity):
  try:
   if process_identity(member['pid'])==member and os.getsid(member['pid'])==identity['pid']:
    os.kill(member['pid'],signum)
  except (ProcessLookupError,FileNotFoundError,ValueError):continue


def drain(identity):
 for signum,seconds in ((signal.SIGTERM,5),(signal.SIGKILL,5)):
  signal_members(identity,signum)
  deadline=time.monotonic()+seconds
  while members(identity) and time.monotonic()<deadline:time.sleep(0.1)
  if not members(identity):return True
 return False


def interrupted(signum,frame):
 raise InterruptedError('Watchdog interrupted by signal '+str(signum))


def run(request):
 global process_identity
 sys.path.insert(0,request['source_directory'])
 from scripts.temporal_pilot_lease import locked_lease,process_identity,write_lease
 started=time.monotonic()
 child=identity=None
 timed_out=False
 error=None
 cleanup=False
 try:
  with Path(request['log']).open('x') as log:
   child=subprocess.Popen(request['command'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'CUDA_VISIBLE_DEVICES':request['gpu_uuid']})
   identity=process_identity(child.pid)
   while child.poll() is None and time.monotonic()-started<300:time.sleep(0.5)
   timed_out=child.poll() is None
 except BaseException as failure:
  error=type(failure).__name__+': '+str(failure)
 finally:
  signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGTERM,signal.SIGINT})
  if child is not None:
   if identity is None:
    try:identity=process_identity(child.pid)
    except (OSError,ValueError):pass
   if identity is not None:cleanup=drain(identity)
   else:cleanup=child.poll() is not None
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:cleanup=False
  code=child.returncode if child is not None else None
  with locked_lease(request['lease']) as lease_path:
   lease=json.loads(lease_path.read_text())
   if lease.get('controller_stamp')==request['controller_stamp'] and identity is not None and lease.get('process_identity')==identity:
    lease['pilot_exit_status']='timeout' if timed_out else 'interrupted' if error else 'complete' if code==0 and cleanup else 'failed'
    lease['pilot_returncode']=code
    lease['session_cleanup_confirmed']=cleanup
    lease['remaining_session_members']=members(identity)
    if lease['status']=='running':lease['status']='timeout' if timed_out else 'exited'
    write_lease(lease_path,lease)
  receipt={'returncode':code,'timeout':timed_out,'error':error,'session_cleanup_confirmed':cleanup,'wall_seconds':time.monotonic()-started,'process_identity':identity}
  Path(request['watchdog_receipt']).write_text(json.dumps(receipt,indent=2)+'\n')
  print(json.dumps(receipt))
 return 0 if code==0 and cleanup and not timed_out and not error else 1


if __name__=='__main__':
 for signum in (signal.SIGTERM,signal.SIGINT):signal.signal(signum,interrupted)
 raise SystemExit(run(json.loads(Path(sys.argv[1]).read_text())))
