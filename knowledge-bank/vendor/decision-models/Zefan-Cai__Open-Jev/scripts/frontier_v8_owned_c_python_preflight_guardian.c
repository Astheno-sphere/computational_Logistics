#define _GNU_SOURCE
#include "frontier_v8_owned_c_python_preflight_protocol.h"

/* This literal executes only newly captured worker/request bytes. */
static const char pp_bootstrap[] =
"import os,sys,json,hashlib,fcntl,errno,stat,time\n"
"r=list(sys.argv); called=False; report=-1; nonce=''; seq=3\n"
"def duplicate(pairs):\n"
" d={}\n"
" for k,v in pairs:\n"
"  if k in d: raise ValueError('duplicate')\n"
"  d[k]=v\n"
" return d\n"
"def st(s): return [s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns]\n"
"def capture(fd,limit):\n"
" before=os.fstat(fd); body=b''\n"
" try:\n"
"  if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=limit: raise ValueError('size')\n"
"  while len(body)<=limit:\n"
"   part=os.read(fd,min(65536,limit+1-len(body)))\n"
"   if not part: break\n"
"   body+=part\n"
"  after=os.fstat(fd)\n"
" finally:\n"
"  result=os.close(fd)\n"
"  try: fcntl.fcntl(fd,fcntl.F_GETFD); raise ValueError('close')\n"
"  except OSError as e:\n"
"   if e.errno!=errno.EBADF: raise\n"
"   bad=e.errno; bad_exception=type(e).__name__\n"
" if st(before)!=st(after) or len(body)!=before.st_size or len(body)>limit: raise ValueError('drift')\n"
" return body,dict(fd=fd,sha256=hashlib.sha256(body).hexdigest(),length=len(body),before=st(before),after=st(after),close_return=result,badfd_result=None,badfd_exception=bad_exception,badfd_errno=bad)\n"
"try:\n"
" if len(r)!=13 or r[1]!='PP_BOOT1': raise ValueError('argument')\n"
" sf,rf,command,report=map(int,r[2:6]); nonce=r[8]\n"
" wb,w=capture(sf,1048576); rb,q=capture(rf,65536)\n"
" code='bootstrap_worker_hash'\n"
" if w['sha256']!=r[6]: raise ValueError(code)\n"
" code='bootstrap_request_hash'\n"
" if q['sha256']!=r[7]: raise ValueError(code)\n"
" code='bootstrap_request_json'\n"
" request=json.loads(rb.decode('utf8'),object_pairs_hook=duplicate,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))\n"
" t0=int(r[10]); orig=list(sys.orig_argv) if hasattr(sys,'orig_argv') else None\n"
" literal=orig[5] if orig is not None and len(orig)>5 and orig[4]=='-c' else None\n"
" startup=dict(schema_version=1,nonce=nonce,case=r[9],input_kind=r[11],python_version_expected=list(map(int,r[12].split('.'))),command_fd=command,report_fd=report,t0_ns=t0,deadlines=dict(work_ns=t0+20000000000,cleanup_ns=t0+25000000000,terminal_ns=t0+28000000000,total_ns=t0+30000000000,expiry_ns=t0+35000000000),captured=dict(worker=w,request=q),initial_argv=r,orig_argv=orig,bootstrap_sha256=hashlib.sha256(literal.encode()).hexdigest() if literal is not None else None,logical_file='frontier_v8_python_runtime_preflight.py',logical_arguments=['frontier_v8_python_runtime_preflight.py',r[9],nonce,r[11]])\n"
" code='worker_validation'; ns={'__name__':'frontier_v8_readonly_worker','__file__':startup['logical_file']}\n"
" exec(compile(wb,startup['logical_file'],'exec'),ns,ns)\n"
" called=True; os._exit(ns['bridge_entry'](request,startup))\n"
"except BaseException:\n"
" if not called and report>=0 and len(nonce)==64:\n"
"  try:\n"
"   message=('PP1 P %s %d ERROR %d %s\\n'%(nonce,seq,time.monotonic_ns(),locals().get('code','bootstrap_capture'))).encode('ascii')\n"
"   deadline=int(r[10])+20000000000\n"
"   while True:\n"
"    if time.monotonic_ns()>=deadline: break\n"
"    try:\n"
"     if os.write(report,message)!=len(message): break\n"
"     break\n"
"    except BlockingIOError: time.sleep(.001)\n"
"  except BaseException: pass\n"
" os._exit(70)\n"
"os._exit(70)\n";

static const char *pp_stage(int stage) {
    static const char *v[]={"initial","preexec","exec","startup","check","armed","primary","terminal","negative"};
    return stage>=0 && stage<9?v[stage]:"negative";
}
static void pp_fail(struct pp_context *r,const char *op,int err,int known,int result) {
    if(!r->error.observed) {
        r->error.observed=1; r->error.err=err; r->error.known=known; r->error.result=result;
        r->error.at=r->last; snprintf(r->error.stage,sizeof(r->error.stage),"%s",pp_stage(r->stage));
        snprintf(r->error.op,sizeof(r->error.op),"%s",op);
    }
}
static int64_t pp_now(struct pp_context *r) {
    struct timespec t; int result;
    errno=0; result=clock_gettime(CLOCK_MONOTONIC,&t);
    if(result || t.tv_sec<0 || t.tv_nsec<0 || t.tv_nsec>=PP_NS || t.tv_sec>(INT64_MAX-t.tv_nsec)/PP_NS) {
        pp_fail(r,"clock_gettime",errno,1,result); return -1;
    }
    int64_t n=(int64_t)t.tv_sec*PP_NS+t.tv_nsec;
    if(n<=0 || n<r->last) { pp_fail(r,"monotonic_clock",0,0,0); return -1; }
    r->last=n; return n;
}
static int pp_time(struct pp_context *r,int64_t deadline) {
    int64_t n=pp_now(r);
    if(n<0 || n>=deadline) { pp_fail(r,"deadline",0,0,0); return 0; }
    return 1;
}
static int pp_hash(const char *s) {
    if(strlen(s)!=64) return 0;
    for(int i=0;i<64;i++) if(!((s[i]>='0' && s[i]<='9') || (s[i]>='a' && s[i]<='f'))) return 0;
    return 1;
}
static int pp_uint(const char *s,uint64_t limit,uint64_t *value) {
    char *end; unsigned long long n;
    if(!*s || (*s=='0' && s[1])) return 0;
    for(const char *p=s;*p;p++) if(*p<'0' || *p>'9') return 0;
    errno=0; n=strtoull(s,&end,10);
    if(errno || *end || n>limit) return 0;
    *value=(uint64_t)n;
    return 1;
}
static struct pp_product pp_stat(struct stat s) {
    struct pp_product p={(uint64_t)s.st_dev,(uint64_t)s.st_ino,(uint64_t)s.st_mode,(uint64_t)s.st_size,
        (int64_t)s.st_mtim.tv_sec*PP_NS+s.st_mtim.tv_nsec,
        (int64_t)s.st_ctim.tv_sec*PP_NS+s.st_ctim.tv_nsec}; return p;
}
static int pp_same_product(struct pp_product a,struct pp_product b) {
    return a.dev==b.dev && a.ino==b.ino && a.mode==b.mode && a.size==b.size && a.mtime==b.mtime && a.ctime==b.ctime;
}
static int pp_file(struct pp_context *r,const char *path,int cap,int executable,int label,struct pp_product *product) {
    char canonical[PATH_MAX]; struct stat s; int fd,rc;
    if(!realpath(path,canonical) || strcmp(path,canonical)) { pp_fail(r,"canonical_input",errno,0,0); return 0; }
    errno=0; fd=open(path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    if(fd<0) { pp_fail(r,"open_input",errno,1,fd); return 0; }
    r->fd[label]=fd; errno=0; rc=fstat(fd,&s);
    if(rc || !S_ISREG(s.st_mode) || s.st_size<=0 || s.st_size>cap || (executable && !(s.st_mode&0111))) {
        pp_fail(r,"fstat_input",errno,1,rc); return 0;
    }
    *product=pp_stat(s); return 1;
}
static int pp_read_file(struct pp_context *r,const char *path,char *body,size_t capacity,size_t *length) {
    int fd; ssize_t n; size_t used=0; int close_rc,close_errno;
    errno=0; fd=open(path,O_RDONLY|O_CLOEXEC);
    if(fd<0) { pp_fail(r,"open_proc",errno,1,fd); return 0; }
    while(used<capacity) {
        errno=0; n=read(fd,body+used,capacity-used);
        if(n<0) { int e=errno; close(fd); pp_fail(r,"read_proc",e,1,(int)n); return 0; }
        if(!n) break;
        used+=(size_t)n;
    }
    errno=0; close_rc=close(fd); close_errno=errno;
    if(close_rc || used==capacity) { pp_fail(r,"close_or_capacity_proc",close_errno,1,close_rc); return 0; }
    body[used]=0; *length=used; return 1;
}
static int pp_identity(struct pp_context *r,int pid,struct pp_identity *id) {
    char path[64],body[8193],status[8193],boot[65],*q,*end; size_t length; struct stat s;
    memset(id,0,sizeof(*id)); snprintf(path,sizeof(path),"/proc/%d/stat",pid);
    if(!pp_read_file(r,path,body,sizeof(body)-1,&length)) return 0;
    q=strrchr(body,')');
    if(!q || q[1]!=' ') { pp_fail(r,"proc_stat_format",0,0,0); return 0; }
    q+=2; char *tokens[20]; int nt=0;
    while(*q && nt<20) { tokens[nt++]=q; end=strchr(q,' '); if(!end) break; *end=0; q=end+1; }
    uint64_t parent,birth;
    if(nt!=20 || strlen(tokens[0])!=1 || !pp_uint(tokens[1],INT_MAX,&parent) || !pp_uint(tokens[19],UINT64_MAX,&birth)) {
        pp_fail(r,"proc_stat_fields",0,0,0); return 0;
    }
    snprintf(path,sizeof(path),"/proc/%d/status",pid);
    if(!pp_read_file(r,path,status,sizeof(status)-1,&length)) return 0;
    q=strstr(status,"\nUid:"); unsigned int uid,euid,suid,fuid; int consumed=0;
    if(!q || sscanf(q,"\nUid:\t%u\t%u\t%u\t%u%n",&uid,&euid,&suid,&fuid,&consumed)!=4 || q[consumed]!='\n') {
        pp_fail(r,"proc_uid_fields",0,0,0); return 0;
    }
    if(!pp_read_file(r,"/proc/sys/kernel/random/boot_id",boot,sizeof(boot)-1,&length) || length!=37 || boot[36]!='\n') {
        pp_fail(r,"boot_id",0,0,0); return 0;
    }
    boot[36]=0; snprintf(path,sizeof(path),"/proc/%d/exe",pid); errno=0;
    if(stat(path,&s)) { pp_fail(r,"proc_exe_stat",errno,1,-1); return 0; }
    id->known=1; id->pid=pid; id->ppid=(int)parent; id->birth=birth; id->uid=uid; id->euid=euid;
    id->state=tokens[0][0]; memcpy(id->boot,boot,37); id->product=pp_stat(s); return 1;
}
static int pp_same_identity(struct pp_identity a,struct pp_identity b,int product) {
    return a.known && b.known && a.pid==b.pid && a.ppid==b.ppid && a.uid==b.uid && a.euid==b.euid &&
        a.birth==b.birth && !strcmp(a.boot,b.boot) && (!product || pp_same_product(a.product,b.product));
}
static int pp_close_one(struct pp_context *r,int label,int evidence) {
    if(r->ncloses==PP_ROWS) { pp_fail(r,"close_ledger_capacity",0,0,0); return 0; }
    struct pp_close *row=&r->closes[r->ncloses++]; memset(row,0,sizeof(*row));
    row->owner=r->role; row->label=label; row->generation=1; row->fd=r->fd[label]; row->evidence=evidence;
    r->fd[label]=-1;
    if(row->fd<0) { row->evidence=PP_ABSENT; return 1; }
    row->close.at=pp_now(r); row->close.attempted=1; errno=0;
    row->close.result=close(row->fd); row->close.err=errno;
    row->badfd.at=pp_now(r); row->badfd.attempted=1; errno=0;
    row->badfd.result=fcntl(row->fd,F_GETFD); row->badfd.err=errno;
    if(label==PP_PIDFD) { r->handle_close=row->close; r->handle_badfd=row->badfd; }
    if(row->close.result || row->badfd.result!=-1 || row->badfd.err!=EBADF) {
        pp_fail(r,"once_close_EBADF",row->close.result?row->close.err:row->badfd.err,1,row->close.result); return 0;
    }
    return 1;
}
static int pp_flags(struct pp_context *r,int label,int inherited) {
    if(r->nflags==PP_ROWS) { pp_fail(r,"flags_capacity",0,0,0); return 0; }
    struct pp_flags *row=&r->flags[r->nflags++]; memset(row,0,sizeof(*row));
    row->owner=r->role; row->label=label; row->generation=1; row->fd=r->fd[label];
    row->before.at=pp_now(r); row->before.attempted=1; errno=0; row->before.result=fcntl(row->fd,F_GETFD); row->before.err=errno;
    if(row->before.result<0) { pp_fail(r,"F_GETFD",row->before.err,1,row->before.result); return 0; }
    row->set.at=pp_now(r); row->set.attempted=1; errno=0;
    row->set.result=fcntl(row->fd,F_SETFD,inherited?row->before.result&~FD_CLOEXEC:row->before.result|FD_CLOEXEC); row->set.err=errno;
    row->after.at=pp_now(r); row->after.attempted=1; errno=0; row->after.result=fcntl(row->fd,F_GETFD); row->after.err=errno;
    row->getfl.at=pp_now(r); row->getfl.attempted=1; errno=0; row->getfl.result=fcntl(row->fd,F_GETFL); row->getfl.err=errno;
    if(row->set.result || row->after.result<0 || !!(row->after.result&FD_CLOEXEC)==inherited || row->getfl.result<0 ||
       (label>=PP_COMMAND_R && label<=PP_ERROR_W && !(row->getfl.result&O_NONBLOCK))) {
        pp_fail(r,"FD_inheritance_flags",row->after.err,1,row->after.result); return 0;
    }
    return 1;
}
static int pp_poll(struct pp_context *r,int fd,short events,int64_t deadline,const char *purpose,int log) {
    struct pollfd p={fd,events,0}; int rc,e; int64_t now=pp_now(r);
    if(now<0 || now>=deadline) { pp_fail(r,"poll_deadline",0,0,0); return -1; }
    int64_t ms=(deadline-now+999999)/1000000; if(ms>50) ms=50;
    errno=0; rc=poll(&p,1,(int)ms); e=errno;
    if(log && r->npolls<PP_ROWS) {
        struct pp_poll *row=&r->polls[r->npolls++]; row->fd=fd; row->result=rc; row->revents=p.revents; row->err=e;
        row->at=now; snprintf(row->purpose,sizeof(row->purpose),"%s",purpose);
    }
    if(rc<0 || (p.revents&POLLNVAL)) { pp_fail(r,"poll",e,1,rc); return -1; }
    return rc?p.revents:0;
}
static int pp_write_control(struct pp_context *r,int fd,const char *kind,const char *payload,int64_t deadline) {
    char line[PP_CONTROL_MAX+1]; int64_t at=pp_now(r);
    int seq=r->sendseq+1; int size=snprintf(line,sizeof(line),"PP1 %s %s %d %s %" PRId64 "%s%s\n",pp_role(r->role),r->nonce,seq,kind,at,*payload?" ":"",payload);
    if(r->error.observed || size<=0 || size>PP_CONTROL_MAX || size>r->pipebuf || !pp_time(r,deadline)) {
        pp_fail(r,"control_size_or_deadline",0,0,0); return 0;
    }
    r->sendseq=seq; /* One logical control attempt, no resend after a positive partial result. */
    while(pp_time(r,deadline)) {
        errno=0; ssize_t n=write(fd,line,(size_t)size); int e=errno;
        if(n==size) {
            if(r->npackets==PP_ROWS) { pp_fail(r,"packet_capacity",0,0,0); return 0; }
            struct pp_packet *row=&r->packets[r->npackets++]; memset(row,0,sizeof(*row));
            row->role=r->role; row->outgoing=1; row->seq=seq; row->at=at; row->observed=r->last;
            snprintf(row->kind,sizeof(row->kind),"%s",kind); snprintf(row->payload,sizeof(row->payload),"%s",payload); row->length=-1;
            return 1;
        }
        if(n<0 && e==EAGAIN) { if(pp_poll(r,fd,POLLOUT,deadline,"control_write",0)<0) return 0; continue; }
        pp_fail(r,"control_write",e,1,(int)n); return 0;
    }
    return 0;
}
static int pp_read_control(struct pp_context *r,int fd,int expected_role,const char *expected_kind,int64_t deadline,struct pp_packet **packet) {
    char line[PP_CONTROL_MAX+1]; size_t used=0;
    while(pp_time(r,deadline)) {
        errno=0; ssize_t n=read(fd,line+used,1); int e=errno;
        if(n==1) { if(line[used++]=='\n') break; if(used==PP_CONTROL_MAX) { pp_fail(r,"control_capacity",0,0,0); return 0; } continue; }
        if(n<0 && e==EAGAIN) { if(pp_poll(r,fd,POLLIN,deadline,"control_read",0)<0) return 0; continue; }
        pp_fail(r,n==0?"early_report_EOF":"control_read",e,1,(int)n); return 0;
    }
    if(!used || line[used-1]!='\n') return 0;
    line[--used]=0;
    if(pp_now(r)<0) return 0;
    if(!used || line[0]==' ' || line[used-1]==' ' || strstr(line,"  ")) { pp_fail(r,"control_spacing",0,0,0); return 0; }
    for(size_t k=0;k<used;k++) if((unsigned char)line[k]<32 || (unsigned char)line[k]>126) { pp_fail(r,"control_ASCII",0,0,0); return 0; }
    char *tokens[6],*q=line;
    for(int k=0;k<6;k++) { tokens[k]=q; char *end=strchr(q,' '); if(k<5 && !end) { pp_fail(r,"control_header",0,0,0); return 0; } if(end) { *end=0; q=end+1; } else q=NULL; }
    uint64_t seq,at;
    if(strcmp(tokens[0],"PP1") || strcmp(tokens[1],pp_role(expected_role)) || strcmp(tokens[2],r->nonce) ||
       !pp_uint(tokens[3],INT_MAX,&seq) || seq!=(uint64_t)r->recvseq+1 || !pp_uint(tokens[5],INT64_MAX,&at) || at<(uint64_t)r->t0 || at>(uint64_t)r->last) {
        pp_fail(r,"control_binding",0,0,0); return 0;
    }
    if(strcmp(tokens[4],expected_kind) && strcmp(tokens[4],"ERROR")) { pp_fail(r,"control_order",0,0,0); return 0; }
    if(r->npackets==PP_ROWS || strlen(tokens[4])>=24 || (q && strlen(q)>=400)) { pp_fail(r,"packet_capacity",0,0,0); return 0; }
    struct pp_packet *row=&r->packets[r->npackets++]; memset(row,0,sizeof(*row));
    row->role=expected_role; row->seq=(int)seq; row->at=(int64_t)at; row->observed=r->last; row->length=-1;
    snprintf(row->kind,sizeof(row->kind),"%s",tokens[4]); snprintf(row->payload,sizeof(row->payload),"%s",q?q:"");
    r->recvseq=(int)seq; *packet=row;
    if(!strcmp(row->kind,"ERROR")) { pp_fail(r,row->payload,0,0,0); return 0; }
    return 1;
}

static int pp_empty(struct pp_context *r,struct pp_packet *packet) {
    if(*packet->payload) { pp_fail(r,"unexpected_control_payload",0,0,0); return 0; }
    return 1;
}
static void pp_child(struct pp_context *r) {
    static const int labels[]={PP_COMMAND_W,PP_REPORT_R,PP_ERROR_R,PP_STDIN,PP_STDOUT,PP_STDERR};
    char payload[400]; size_t used=0; struct pp_packet *packet;
    struct rlimit core={0,0},cpu={20,21}; int core_result,cpu_result,core_errno,cpu_errno;
    r->role=PP_X; r->stage=1; r->ncloses=0; r->npackets=0; r->sendseq=0; r->recvseq=0;
    for(int k=0;k<6;k++) {
        int label=labels[k];
        if(label>=PP_STDIN) {
            r->fd[label]=label-PP_STDIN; errno=0; int flags=fcntl(r->fd[label],F_GETFD);
            if(flags<0 && errno==EBADF) r->fd[label]=-1;
            else if(flags<0) { pp_fail(r,"original_stdio_F_GETFD",errno,1,flags); _exit(71); }
        }
        if(!pp_close_one(r,label,PP_EXPLICIT)) _exit(71);
        struct pp_close *row=&r->closes[k];
        int n=snprintf(payload+used,sizeof(payload)-used,"%s%d %d %d %d %d %d",k?" ":"",row->fd,row->evidence,
            row->close.attempted?row->close.result:PP_UNATTEMPTED,row->close.attempted?row->close.err:PP_UNATTEMPTED,
            row->badfd.attempted?row->badfd.result:PP_UNATTEMPTED,row->badfd.attempted?row->badfd.err:PP_UNATTEMPTED);
        if(n<0 || (size_t)n>=sizeof(payload)-used) _exit(71);
        used+=(size_t)n;
    }
    errno=0; core_result=setrlimit(RLIMIT_CORE,&core); core_errno=errno;
    errno=0; cpu_result=setrlimit(RLIMIT_CPU,&cpu); cpu_errno=errno;
    if(core_result || cpu_result) _exit(71);
    int n=snprintf(payload+used,sizeof(payload)-used," %d %d %d %d",core_result,core_errno,cpu_result,cpu_errno);
    if(n<0 || (size_t)n>=sizeof(payload)-used || !pp_write_control(r,r->fd[PP_REPORT_W],"PRE_READY",payload,r->work)) _exit(71);
    if(!pp_read_control(r,r->fd[PP_COMMAND_R],PP_G,"GO",r->work,&packet) || !pp_empty(r,packet)) _exit(71);
    if(r->fault==1 && !pp_close_one(r,PP_INTERPRETER,PP_EXPLICIT)) _exit(71);
    r->stage=2;
    if(!pp_write_control(r,r->fd[PP_REPORT_W],"EXEC_ENTER","",r->work) || !pp_time(r,r->work)) _exit(71);
    char nonceenv[96]; snprintf(nonceenv,sizeof(nonceenv),"OPEN_JEV_NONCE=%s",r->nonce);
    char *env[]={"PATH=/usr/bin:/bin","LANG=C.UTF-8","LC_ALL=C.UTF-8",nonceenv,
        "CUDA_VISIBLE_DEVICES=","NVIDIA_VISIBLE_DEVICES=none","PIP_CONFIG_FILE=/dev/null",NULL};
    int (*exec_signature)(int,char *const[],char *const[])=fexecve;
    errno=0; int result=exec_signature(r->fault==1?r->closes[r->ncloses-1].fd:r->fd[PP_INTERPRETER],r->python_argv,env); int e=errno;
    int record[6]={result,e,PP_UNATTEMPTED,PP_UNATTEMPTED,PP_UNATTEMPTED,PP_UNATTEMPTED};
    if(r->fault==1) {
        struct pp_close *row=&r->closes[r->ncloses-1];
        record[2]=row->close.result; record[3]=row->close.err; record[4]=row->badfd.result; record[5]=row->badfd.err;
    }
    /* Returned exec failure has one small atomic error record, never a retry. */
    if(pp_time(r,r->work)) {
        errno=0; ssize_t written=write(r->fd[PP_ERROR_W],record,sizeof(record));
        (void)written;
    }
    _exit(71);
}
static int pp_pre_ready(struct pp_context *r,struct pp_packet *packet) {
    static const int labels[]={PP_COMMAND_W,PP_REPORT_R,PP_ERROR_R,PP_STDIN,PP_STDOUT,PP_STDERR};
    const char *p=packet->payload; char *end; long fields[40];
    for(int k=0;k<40;k++) {
        errno=0; fields[k]=strtol(p,&end,10);
        if(errno || end==p || fields[k]<INT32_MIN || fields[k]>INT32_MAX || (k<39?*end!=' ':*end!=0)) {
            pp_fail(r,"PRE_READY_close_payload",0,0,0); return 0;
        }
        p=end+(k<39);
    }
    for(int k=0;k<6;k++) {
        if(r->ncloses==PP_ROWS) { pp_fail(r,"close_capacity",0,0,0); return 0; }
        long *v=&fields[k*6]; struct pp_close *row=&r->closes[r->ncloses++]; memset(row,0,sizeof(*row));
        row->owner=PP_X; row->label=labels[k]; row->generation=1; row->fd=(int)v[0]; row->evidence=(int)v[1];
        if(row->evidence==PP_ABSENT) {
            if(row->fd!=-1 || v[2]!=PP_UNATTEMPTED || v[3]!=PP_UNATTEMPTED || v[4]!=PP_UNATTEMPTED || v[5]!=PP_UNATTEMPTED || k<3) {
                pp_fail(r,"PRE_READY_absent",0,0,0); return 0;
            }
        } else if(row->evidence==PP_EXPLICIT && row->fd>=0 && v[2]==0 && v[3]==0 && v[4]==-1 && v[5]==EBADF) {
            row->close.attempted=row->badfd.attempted=1;
            row->close.result=(int)v[2]; row->close.err=(int)v[3]; row->badfd.result=(int)v[4]; row->badfd.err=(int)v[5];
            /* Exact child syscall results returned; individual syscall clock not returned. */
        } else { pp_fail(r,"PRE_READY_close_EBADF",0,0,0); return 0; }
    }
    if(fields[36] || fields[37] || fields[38] || fields[39]) { pp_fail(r,"PRE_READY_rlimit",0,0,0); return 0; }
    r->rlimits_reported=1; r->core_result=(int)fields[36]; r->core_errno=(int)fields[37];
    r->cpu_result=(int)fields[38]; r->cpu_errno=(int)fields[39];
    return 1;
}
static int pp_exec_error(struct pp_context *r) {
    int record[6]; size_t used=0;
    while(pp_time(r,r->work)) {
        errno=0; ssize_t n=read(r->fd[PP_ERROR_R],(unsigned char *)record+used,sizeof(record)-used); int e=errno;
        if(n>0) {
            used+=(size_t)n;
            if(used==sizeof(record)) {
                r->exec_attempted=r->exec_attempted_known=1;
                r->exec_returned=1; r->exec_known=1; r->exec_result=record[0]; r->exec_err=record[1];
                if(r->fault==1 && r->ncloses<PP_ROWS) {
                    struct pp_close *row=&r->closes[r->ncloses++]; memset(row,0,sizeof(*row));
                    row->owner=PP_X; row->label=PP_INTERPRETER; row->generation=1;
                    row->fd=r->original[PP_INTERPRETER]; row->evidence=PP_EXPLICIT;
                    row->close.attempted=row->badfd.attempted=1;
                    row->close.result=record[2]; row->close.err=record[3]; row->badfd.result=record[4]; row->badfd.err=record[5];
                }
                pp_fail(r,"fexecve_return",record[1],1,record[0]); return 0;
            }
            continue;
        }
        if(!n) {
            if(used) { pp_fail(r,"truncated_exec_error",0,0,0); return 0; }
            r->error_eof=pp_now(r); return 1;
        }
        if(e==EAGAIN) { if(pp_poll(r,r->fd[PP_ERROR_R],POLLIN,r->work,"exec_error",0)<0) return 0; continue; }
        pp_fail(r,"exec_error_read",e,1,(int)n); return 0;
    }
    return 0;
}
static int pp_ready(struct pp_context *r,struct pp_packet *packet) {
    char fields[13][65]; const char *p=packet->payload;
    for(int k=0;k<13;k++) {
        const char *end=strchr(p,' '); size_t size=end?(size_t)(end-p):strlen(p);
        if(!size || size>=sizeof(fields[k]) || (k<12?!end:end!=NULL)) { pp_fail(r,"READY_payload",0,0,0); return 0; }
        memcpy(fields[k],p,size); fields[k][size]=0; p=end?end+1:p+size;
    }
    uint64_t n[11];
    for(int k=0;k<11;k++) if(!pp_uint(fields[k],k==4?UINT64_MAX:UINT32_MAX,&n[k])) { pp_fail(r,"READY_integer",0,0,0); return 0; }
    if(n[0]!=(uint64_t)r->child || n[1]!=(uint64_t)r->ids[0].pid || n[2]!=r->ids[0].uid || n[3]!=r->ids[0].euid || n[4]!=r->ids[1].birth ||
       n[5]!=(uint64_t)r->version[0] || n[6]!=(uint64_t)r->version[1] || n[7]!=(uint64_t)r->version[2] || n[8]!=1 || n[9]!=1 || n[10]!=1 ||
       strcmp(fields[11],r->argv[7]) || strcmp(fields[12],r->argv[8])) { pp_fail(r,"READY_binding",0,0,0); return 0; }
    if(!pp_identity(r,r->child,&r->ids[2]) || !pp_same_identity(r->ids[1],r->ids[2],0) ||
       !pp_same_product(r->ids[2].product,r->interpreter) || pp_same_product(r->ids[1].product,r->ids[2].product)) {
        pp_fail(r,"Python_product_transition",0,0,0); return 0;
    }
    char path[64]; snprintf(path,sizeof(path),"/proc/%d/cmdline",r->child);
    r->kernel_argv=malloc(65537); if(!r->kernel_argv) { pp_fail(r,"argv_memory",errno,0,0); return 0; }
    if(!pp_read_file(r,path,r->kernel_argv,65536,&r->kernel_argv_len) || !r->kernel_argv_len || r->kernel_argv[r->kernel_argv_len-1]) {
        pp_fail(r,"kernel_python_argv",0,0,0); return 0;
    }
    size_t offset=0;
    for(int k=0;k<18;k++) {
        size_t length=strlen(r->python_argv[k]);
        if(offset+length+1>r->kernel_argv_len || memcmp(r->kernel_argv+offset,r->python_argv[k],length+1)) {
            pp_fail(r,"kernel_python_argv_binding",0,0,0); return 0;
        }
        offset+=length+1;
    }
    if(offset!=r->kernel_argv_len) { pp_fail(r,"kernel_python_argv_extra",0,0,0); return 0; }
    return 1;
}
static int pp_data(struct pp_context *r,struct pp_packet *packet) {
    char *space=strchr(packet->payload,' '); uint64_t length;
    if(!space || strchr(space+1,' ') || (size_t)(space-packet->payload)>=24) { pp_fail(r,"DATA_header",0,0,0); return 0; }
    char count[24]; memcpy(count,packet->payload,(size_t)(space-packet->payload)); count[space-packet->payload]=0;
    if(!pp_uint(count,PP_BODY_MAX,&length) || !length || !pp_hash(space+1)) { pp_fail(r,"DATA_length_hash",0,0,0); return 0; }
    r->body_declared=(int)length; memcpy(r->body_sha,space+1,65); packet->length=(int)length; memcpy(packet->sha,space+1,65);
    while(r->body_len<(size_t)r->body_declared && pp_time(r,r->work)) {
        errno=0; ssize_t n=read(r->fd[PP_REPORT_R],r->body+r->body_len,(size_t)r->body_declared-r->body_len); int e=errno;
        if(n>0) { r->body_len+=(size_t)n; continue; }
        if(n<0 && e==EAGAIN) { if(pp_poll(r,r->fd[PP_REPORT_R],POLLIN,r->work,"DATA_read",0)<0) return 0; continue; }
        pp_fail(r,n==0?"truncated_DATA_EOF":"DATA_read",e,1,(int)n); return 0;
    }
    r->body_complete=r->body_len==(size_t)r->body_declared;
    return r->body_complete;
}
static int pp_eof(struct pp_context *r,int64_t deadline) {
    unsigned char b;
    while(pp_time(r,deadline)) {
        errno=0; ssize_t n=read(r->fd[PP_REPORT_R],&b,1); int e=errno;
        if(!n) {
            if(r->ncloses==PP_ROWS) { pp_fail(r,"EOF_ledger_capacity",0,0,0); return 0; }
            struct pp_close *row=&r->closes[r->ncloses++]; memset(row,0,sizeof(*row));
            row->owner=PP_P; row->label=PP_REPORT_W; row->generation=1; row->fd=atoi(r->python_fdargs[3]); row->evidence=PP_PARENT_EOF;
            return 1;
        }
        if(n<0 && e==EAGAIN) { if(pp_poll(r,r->fd[PP_REPORT_R],POLLIN,deadline,"report_EOF",0)<0) return 0; continue; }
        pp_fail(r,n>0?"unexpected_report_tail":"report_EOF_read",e,1,(int)n); return 0;
    }
    return 0;
}
static int pp_terminal(struct pp_context *r,int64_t deadline) {
    while(pp_time(r,deadline)) {
        if(r->npolls==PP_ROWS) { pp_fail(r,"terminal_poll_capacity",0,0,0); return 0; }
        int revents=pp_poll(r,r->fd[PP_PIDFD],POLLIN,deadline,"terminal",1);
        if(revents<0) return 0;
        if(revents&POLLIN) return 1;
        if(revents && !(revents&POLLIN)) { pp_fail(r,"terminal_poll_events",0,1,revents); return 0; }
    }
    return 0;
}
static int pp_reap(struct pp_context *r,int64_t deadline) {
    while(pp_time(r,deadline)) {
        int status; r->wait_attempts++; errno=0; int pid=(int)waitpid(r->child,&status,WNOHANG); int e=errno;
        r->wait_at=r->last; r->wait_pid=pid; r->wait_err=e; r->wait_known=1;
        if(pid==r->child) { r->wait_status=status; return 1; }
        if(pid<0 || pid>0) { pp_fail(r,"waitpid",e,1,pid); return 0; }
        if(pp_poll(r,r->fd[PP_PIDFD],POLLIN,deadline,"reap_progress",0)<0) return 0;
    }
    return 0;
}

static int pp_pipe(struct pp_context *r,int read_label,int write_label) {
    int pair[2]; errno=0; int result=pipe2(pair,O_NONBLOCK|O_CLOEXEC);
    if(result) { pp_fail(r,"pipe2",errno,1,result); return 0; }
    r->fd[read_label]=pair[0]; r->fd[write_label]=pair[1];
    errno=0; long bound=fpathconf(pair[1],_PC_PIPE_BUF);
    if(bound<PP_CONTROL_MAX || bound>INT_MAX) { pp_fail(r,"PIPE_BUF",errno,0,0); return 0; }
    if(!r->pipebuf || bound<r->pipebuf) r->pipebuf=(int)bound;
    return 1;
}
static int pp_sigpipe(struct pp_context *r) {
    struct sigaction sa,actual; memset(&sa,0,sizeof(sa)); sa.sa_handler=SIG_IGN;
    if(sigemptyset(&sa.sa_mask)) { pp_fail(r,"sigemptyset",errno,1,-1); return 0; }
    r->sigpipe_set.at=pp_now(r); r->sigpipe_set.attempted=1; errno=0;
    r->sigpipe_set.result=sigaction(SIGPIPE,&sa,NULL); r->sigpipe_set.err=errno;
    r->sigpipe_get.at=pp_now(r); r->sigpipe_get.attempted=1; errno=0;
    r->sigpipe_get.result=sigaction(SIGPIPE,NULL,&actual); r->sigpipe_get.err=errno;
    r->sigpipe_ignored=!r->sigpipe_get.result && actual.sa_handler==SIG_IGN;
    if(r->sigpipe_set.result || r->sigpipe_get.result || !r->sigpipe_ignored) { pp_fail(r,"SIGPIPE_local",errno,0,0); return 0; }
    return 1;
}
static int pp_handle(struct pp_context *r) {
    char path[64],body[8193]; size_t length; long (*syscall_signature)(long,...)=syscall;
    r->open.at=pp_now(r); r->open.attempted=1; errno=0;
    long result=syscall_signature(SYS_pidfd_open,(long)r->child,0UL); r->open.err=errno;
    if(result<0 || result>INT_MAX) { r->open.result=(int)result; pp_fail(r,"pidfd_open",r->open.err,1,(int)result); return 0; }
    r->open.result=(int)result; r->fd[PP_PIDFD]=(int)result; r->original[PP_PIDFD]=(int)result; r->signal_fd=(int)result;
    r->handle_flags.at=pp_now(r); r->handle_flags.attempted=1; errno=0;
    r->handle_flags.result=fcntl((int)result,F_GETFD); r->handle_flags.err=errno;
    if(r->handle_flags.result<0 || !(r->handle_flags.result&FD_CLOEXEC)) { pp_fail(r,"pidfd_flags",r->handle_flags.err,1,r->handle_flags.result); return 0; }
    snprintf(path,sizeof(path),"/proc/self/fdinfo/%d",(int)result);
    if(!pp_read_file(r,path,body,sizeof(body)-1,&length)) return 0;
    char *p=strstr(body,"\nPid:\t"); int pid,n=0;
    if(!p || sscanf(p,"\nPid:\t%d%n",&pid,&n)!=1 || p[n]!='\n' || pid!=r->child) { pp_fail(r,"pidfd_fdinfo",0,0,0); return 0; }
    r->fdinfo_pid=pid;
    if(!pp_time(r,r->work)) return 0;
    struct pollfd probe={(int)result,POLLIN,0}; errno=0; int rc=poll(&probe,1,0); int e=errno;
    struct pp_poll *row=&r->polls[r->npolls++]; row->fd=(int)result; row->result=rc; row->revents=probe.revents; row->err=e;
    row->at=r->last; snprintf(row->purpose,sizeof(row->purpose),"initial_live");
    if(rc || probe.revents) { pp_fail(r,"pidfd_initial_live",e,1,rc); return 0; }
    return 1;
}
static int pp_live(struct pp_context *r) {
    if(!pp_time(r,r->work) || !pp_identity(r,r->child,&r->ids[3]) || !pp_same_identity(r->ids[2],r->ids[3],1) ||
       r->ids[3].state=='Z' || r->ids[3].state=='X') { pp_fail(r,"pre_action_identity",0,0,0); return 0; }
    struct pollfd p={r->fd[PP_PIDFD],POLLIN,0}; errno=0; int rc=poll(&p,1,0); int e=errno;
    if(r->npolls==PP_ROWS) { pp_fail(r,"live_poll_capacity",0,0,0); return 0; }
    struct pp_poll *row=&r->polls[r->npolls++]; row->fd=p.fd; row->result=rc; row->revents=p.revents; row->err=e;
    row->at=r->last; snprintf(row->purpose,sizeof(row->purpose),"pre_action_live");
    if(rc || p.revents) { pp_fail(r,"pre_action_pidfd_live",e,1,rc); return 0; }
    return pp_time(r,r->work);
}
static void pp_entry_rows(struct pp_context *r) {
    static const int labels[]={PP_INTERPRETER,PP_ERROR_W};
    for(int k=0;k<2;k++) {
        if(r->ncloses==PP_ROWS) { pp_fail(r,"entry_ledger_capacity",0,0,0); return; }
        struct pp_close *row=&r->closes[r->ncloses++]; memset(row,0,sizeof(*row));
        row->owner=PP_X; row->label=labels[k]; row->generation=1; row->fd=r->original[labels[k]]; row->evidence=PP_EXEC_CLOSED;
        /* Joint transition/EOF and preexec CLOEXEC, never a CPython vacancy F_GETFD. */
    }
}
static void pp_run(struct pp_context *r) {
    struct pp_packet *packet;
    /* Original G stdio must precede every managed/proc input acquisition. */
    for(int fd=0;fd<3;fd++) {
        errno=0; int flags=fcntl(fd,F_GETFD); int e=errno;
        if(flags<0) { pp_fail(r,"original_G_stdio_F_GETFD",e,1,flags); return; }
    }
    if(!pp_sigpipe(r) || !pp_identity(r,(int)getpid(),&r->ids[0])) return;
    r->guardian=r->ids[0].product; r->guardian_known=1;
    if(r->ids[0].uid!=r->ids[0].euid) { pp_fail(r,"equal_UID_required",0,0,0); return; }
    if(!pp_file(r,r->argv[3],134217728,1,PP_INTERPRETER,&r->interpreter)) return;
    r->interpreter_known=1;
    if(!pp_file(r,r->argv[4],1048576,0,PP_WORKER,&r->worker) || !pp_file(r,r->argv[5],65536,0,PP_REQUEST,&r->request) ||
       !pp_pipe(r,PP_COMMAND_R,PP_COMMAND_W) || !pp_pipe(r,PP_REPORT_R,PP_REPORT_W) || !pp_pipe(r,PP_ERROR_R,PP_ERROR_W)) return;
    for(int label=0;label<=PP_ERROR_W;label++) if(!pp_flags(r,label,label==PP_WORKER || label==PP_REQUEST || label==PP_COMMAND_R || label==PP_REPORT_W)) return;
    for(int label=0;label<PP_FDS;label++) r->original[label]=r->fd[label];
    static const int inherited[]={PP_WORKER,PP_REQUEST,PP_COMMAND_R,PP_REPORT_W};
    for(int k=0;k<4;k++) snprintf(r->python_fdargs[k],sizeof(r->python_fdargs[k]),"%d",r->fd[inherited[k]]);
    snprintf(r->t0arg,sizeof(r->t0arg),"%" PRId64,r->t0);
    memcpy(r->bootstrap_worker_hash,r->argv[7],65);
    if(r->fault==2) r->bootstrap_worker_hash[0]=r->bootstrap_worker_hash[0]=='0'?'1':'0';
    char *args[]={r->argv[3],"-B","-I","-S","-c",(char *)pp_bootstrap,"PP_BOOT1",r->python_fdargs[0],r->python_fdargs[1],
        r->python_fdargs[2],r->python_fdargs[3],r->bootstrap_worker_hash,r->argv[8],r->nonce,r->argv[1],r->t0arg,r->argv[10],r->argv[9],NULL};
    memcpy(r->python_argv,args,sizeof(args));
    if(!pp_time(r,r->work)) return;
    errno=0; int child=(int)fork();
    if(child<0) { pp_fail(r,"fork",errno,1,child); return; }
    if(!child) pp_child(r);
    r->child=child; r->stage=1;
    if(!pp_identity(r,child,&r->ids[1])) return;
    if(r->ids[1].ppid!=r->ids[0].pid || r->ids[1].uid!=r->ids[0].uid ||
       r->ids[1].euid!=r->ids[0].euid || strcmp(r->ids[1].boot,r->ids[0].boot) || !pp_same_product(r->ids[1].product,r->guardian)) {
        pp_fail(r,"preexec_ownership_binding",0,0,0); return;
    }
    if(!pp_handle(r)) return;
    static const int parent_close[]={PP_COMMAND_R,PP_REPORT_W,PP_ERROR_W,PP_INTERPRETER,PP_WORKER,PP_REQUEST};
    for(int k=0;k<6;k++) if(!pp_close_one(r,parent_close[k],PP_EXPLICIT)) return;
    if(!pp_read_control(r,r->fd[PP_REPORT_R],PP_X,"PRE_READY",r->work,&packet) || !pp_pre_ready(r,packet)) return;
    r->times[0]=r->last;
    if(!pp_write_control(r,r->fd[PP_COMMAND_W],"GO","",r->work)) return;
    r->times[1]=r->last; r->stage=2;
    if(!pp_read_control(r,r->fd[PP_REPORT_R],PP_X,"EXEC_ENTER",r->work,&packet) || !pp_empty(r,packet)) return;
    r->enter=packet->at;
    if(!pp_exec_error(r)) return;
    r->stage=3;
    if(!pp_read_control(r,r->fd[PP_REPORT_R],PP_P,"READY",r->work,&packet) || !pp_ready(r,packet)) return;
    r->exec_attempted=r->exec_attempted_known=1; r->exec_returned=0;
    r->times[2]=r->last; pp_entry_rows(r);
    if(r->error.observed || !pp_close_one(r,PP_ERROR_R,PP_EXPLICIT)) return;
    r->stage=4;
    if(!pp_write_control(r,r->fd[PP_COMMAND_W],"CHECK","",r->work) ||
       !pp_read_control(r,r->fd[PP_REPORT_R],PP_P,"DATA",r->work,&packet) || !pp_data(r,packet)) return;
    r->times[3]=r->last;
    if(!pp_read_control(r,r->fd[PP_REPORT_R],PP_P,"ARM",r->work,&packet) || !pp_empty(r,packet)) return;
    r->times[4]=r->last; r->stage=5;
    if(!pp_identity(r,r->child,&r->ids[3])) return;
    if(!pp_same_identity(r->ids[2],r->ids[3],1)) {
        pp_fail(r,"pre_ARM_identity_binding",0,0,0); return;
    }
    if(!pp_write_control(r,r->fd[PP_COMMAND_W],"ARM_ACK","",r->work) ||
       !pp_read_control(r,r->fd[PP_REPORT_R],PP_P,"ACK",r->work,&packet) || !pp_empty(r,packet)) return;
    r->times[5]=r->last;
    if(!pp_live(r)) return;
    r->stage=6; r->times[6]=r->last;
    if(r->loss) {
        long (*signal_signature)(long,...)=syscall;
        r->signal_consumed=1; r->signal_attempts=1; r->signal_at=r->last;
        errno=0; long result=signal_signature(SYS_pidfd_send_signal,(long)r->fd[PP_PIDFD],(long)SIGKILL,(siginfo_t *)NULL,0UL);
        r->signal_result=(int)result; r->signal_err=errno; r->signal_known=1;
        if(result!=0) { pp_fail(r,"pidfd_send_signal",r->signal_err,1,(int)result); return; }
    } else {
        if(!pp_write_control(r,r->fd[PP_COMMAND_W],"FINISH","",r->work) ||
           !pp_read_control(r,r->fd[PP_REPORT_R],PP_P,"FINISH_ACK",r->cleanup,&packet) || !pp_empty(r,packet)) return;
    }
    r->stage=7;
    if(!pp_eof(r,r->cleanup) || !pp_terminal(r,r->cleanup)) return;
    r->times[7]=r->last;
    if(!pp_reap(r,r->terminal)) return;
    r->times[8]=r->last;
    if(r->wait_status!=(r->loss?SIGKILL:0)) { pp_fail(r,"raw_wait_status",0,1,r->wait_status); return; }
    if(r->ncloses<PP_ROWS) {
        struct pp_close *row=&r->closes[r->ncloses++]; memset(row,0,sizeof(*row));
        row->owner=PP_P; row->label=PP_COMMAND_R; row->generation=1; row->fd=atoi(r->python_fdargs[2]);
        row->evidence=r->loss?PP_OWNER_DEATH:PP_UNKNOWN;
    }
    r->success=1;
}
static void pp_json_string(const char *s) {
    if(!s) { fputs("null",stdout); return; }
    putchar('"');
    for(const unsigned char *p=(const unsigned char *)s;*p;p++) {
        if(*p=='"' || *p=='\\') { putchar('\\'); putchar(*p); }
        else if(*p<32 || *p>126) printf("\\u%04x",(unsigned int)*p);
        else putchar(*p);
    }
    putchar('"');
}
static void pp_json_number(int known,int64_t n) { if(known) printf("%" PRId64,n); else fputs("null",stdout); }
static void pp_json_fact(struct pp_fact f) {
    printf("{\"attempted\":%s,\"result\":",f.attempted?"true":"false"); pp_json_number(f.attempted,f.result);
    fputs(",\"errno\":",stdout); pp_json_number(f.attempted,f.err);
    fputs(",\"at_ns\":",stdout); pp_json_number(f.at>0,f.at); putchar('}');
}
static void pp_json_product(struct pp_product p) {
    printf("[%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRId64 ",%" PRId64 "]",p.dev,p.ino,p.mode,p.size,p.mtime,p.ctime);
}
static void pp_json_identity(struct pp_identity id) {
    if(!id.known) { fputs("null",stdout); return; }
    printf("{\"pid\":%d,\"ppid\":%d,\"uid\":%" PRIu32 ",\"euid\":%" PRIu32 ",\"birth\":%" PRIu64 ",\"boot_id\":",id.pid,id.ppid,id.uid,id.euid,id.birth);
    pp_json_string(id.boot); fputs(",\"state\":",stdout); char state[2]={id.state,0}; pp_json_string(state);
    fputs(",\"product\":",stdout); pp_json_product(id.product); putchar('}');
}
static void pp_json_argv(char **argv,int count) {
    if(!argv[0]) { fputs("null",stdout); return; }
    putchar('[');
    for(int k=0;k<count;k++) { if(k) putchar(','); pp_json_string(argv[k]); }
    putchar(']');
}
static void pp_json_poll(struct pp_poll row) {
    printf("{\"fd\":%d,\"result\":%d,\"revents\":%d,\"errno\":%d,\"at_ns\":%" PRId64 ",\"purpose\":",row.fd,row.result,row.revents,row.err,row.at);
    pp_json_string(row.purpose); putchar('}');
}
static void pp_emit(struct pp_context *r) {
    fputs("{\"schema_version\":1,\"scope\":\"frontier_v8_owned_C_fixed_Python_readonly_metadata_CPU_fixture\",\"case\":",stdout); pp_json_string(r->argv[1]);
    fputs(",\"nonce\":",stdout); pp_json_string(r->nonce); fputs(",\"input_kind\":",stdout); pp_json_string(r->argv[10]);
    fputs(",\"fault\":",stdout); pp_json_string(r->argv[11]); printf(",\"native_success\":%s,\"error\":",r->success?"true":"false");
    if(!r->error.observed) fputs("null",stdout);
    else {
        fputs("{\"stage\":",stdout); pp_json_string(r->error.stage); fputs(",\"operation\":",stdout); pp_json_string(r->error.op);
        printf(",\"errno\":%d,\"result_known\":%s,\"result\":",r->error.err,r->error.known?"true":"false"); pp_json_number(r->error.known,r->error.result);
        printf(",\"at_ns\":%" PRId64 "}",r->error.at);
    }
    printf(",\"t0_ns\":%" PRId64 ",\"deadlines\":{\"work_ns\":%" PRId64 ",\"cleanup_ns\":%" PRId64 ",\"terminal_ns\":%" PRId64 ",\"total_ns\":%" PRId64 ",\"expiry_ns\":%" PRId64 "}",r->t0,r->work,r->cleanup,r->terminal,r->total,r->expiry);
    fputs(",\"runtime_argv\":",stdout); pp_json_argv(r->argv,12);
    fputs(",\"python_exec_argv\":",stdout); pp_json_argv(r->python_argv,18);
    fputs(",\"kernel_python_argv\":",stdout);
    if(!r->kernel_argv) fputs("null",stdout);
    else {
        putchar('['); size_t offset=0; int first=1;
        while(offset<r->kernel_argv_len) { if(!first) putchar(','); first=0; pp_json_string(r->kernel_argv+offset); offset+=strlen(r->kernel_argv+offset)+1; }
        putchar(']');
    }
    fputs(",\"expected_hashes\":{\"interpreter\":",stdout); pp_json_string(r->argv[6]); fputs(",\"worker\":",stdout); pp_json_string(r->argv[7]); fputs(",\"request\":",stdout); pp_json_string(r->argv[8]); putchar('}');
    fputs(",\"products\":{\"guardian\":",stdout); if(r->guardian_known) pp_json_product(r->guardian); else fputs("null",stdout);
    fputs(",\"interpreter\":",stdout); if(r->interpreter_known) pp_json_product(r->interpreter); else fputs("null",stdout); putchar('}');
    fputs(",\"identities\":{\"G\":",stdout); pp_json_identity(r->ids[0]); fputs(",\"X\":",stdout); pp_json_identity(r->ids[1]);
    fputs(",\"P_transition\":",stdout); pp_json_identity(r->ids[2]); fputs(",\"P_pre_action\":",stdout); pp_json_identity(r->ids[3]); putchar('}');
    fputs(",\"exec\":{\"attempted\":",stdout);
    if(r->exec_attempted_known) fputs(r->exec_attempted?"true":"false",stdout); else fputs("null",stdout);
    fputs(",\"returned\":",stdout);
    if(!r->exec_attempted_known || !r->exec_attempted) fputs("null",stdout); else fputs(r->exec_returned?"true":"false",stdout);
    fputs(",\"result\":",stdout); pp_json_number(r->exec_known,r->exec_result); fputs(",\"errno\":",stdout); pp_json_number(r->exec_known,r->exec_err);
    fputs(",\"enter_ns\":",stdout); pp_json_number(r->enter>0,r->enter); fputs(",\"error_eof_ns\":",stdout); pp_json_number(r->error_eof>0,r->error_eof);
    fputs(",\"error_pipe_result\":",stdout); if(r->exec_known) printf("{\"result\":%d,\"errno\":%d}",r->exec_result,r->exec_err); else fputs("null",stdout); putchar('}');
    fputs(",\"handle\":{\"fd\":",stdout); pp_json_number(r->original[PP_PIDFD]>=0,r->original[PP_PIDFD]); fputs(",\"open\":",stdout); pp_json_fact(r->open);
    fputs(",\"flags\":",stdout); pp_json_fact(r->handle_flags); fputs(",\"fdinfo_pid\":",stdout); pp_json_number(r->fdinfo_pid>0,r->fdinfo_pid);
    fputs(",\"live_poll\":",stdout); if(r->npolls) pp_json_poll(r->polls[0]); else fputs("null",stdout);
    fputs(",\"close\":",stdout); pp_json_fact(r->handle_close); fputs(",\"badfd\":",stdout); pp_json_fact(r->handle_badfd); putchar('}');
    printf(",\"signal\":{\"budget_consumed\":%s,\"attempts\":%d,\"fd\":",r->signal_consumed?"true":"false",r->signal_attempts); pp_json_number(r->signal_fd>=0,r->signal_fd);
    fputs(",\"flags\":0,\"result\":",stdout); pp_json_number(r->signal_known,r->signal_result); fputs(",\"errno\":",stdout); pp_json_number(r->signal_known,r->signal_err);
    fputs(",\"at_ns\":",stdout); pp_json_number(r->signal_at>0,r->signal_at); putchar('}');
    printf(",\"wait\":{\"attempts\":%d,\"result_pid\":",r->wait_attempts); pp_json_number(r->wait_known,r->wait_pid);
    fputs(",\"raw_status\":",stdout); pp_json_number(r->wait_known && r->wait_pid==r->child,r->wait_status); fputs(",\"errno\":",stdout); pp_json_number(r->wait_known,r->wait_err);
    fputs(",\"at_ns\":",stdout); pp_json_number(r->wait_at>0,r->wait_at); putchar('}');
    fputs(",\"polls\":[",stdout); for(int k=0;k<r->npolls;k++) { if(k) putchar(','); pp_json_poll(r->polls[k]); } putchar(']');
    fputs(",\"fd_ledger\":[",stdout);
    for(int k=0;k<r->ncloses;k++) {
        struct pp_close row=r->closes[k]; if(k) putchar(','); fputs("{\"owner\":",stdout); pp_json_string(pp_role(row.owner)); fputs(",\"label\":",stdout); pp_json_string(pp_label(row.label));
        printf(",\"generation\":%d,\"fd\":%d,\"evidence\":",row.generation,row.fd); pp_json_string(pp_evidence(row.evidence));
        fputs(",\"close\":",stdout); pp_json_fact(row.close); fputs(",\"badfd\":",stdout); pp_json_fact(row.badfd); putchar('}');
    }
    fputs("],\"fd_flags\":[",stdout);
    for(int k=0;k<r->nflags;k++) {
        struct pp_flags row=r->flags[k]; if(k) putchar(','); fputs("{\"owner\":",stdout); pp_json_string(pp_role(row.owner)); fputs(",\"label\":",stdout); pp_json_string(pp_label(row.label));
        printf(",\"generation\":%d,\"fd\":%d,\"before\":",row.generation,row.fd); pp_json_fact(row.before); fputs(",\"set\":",stdout); pp_json_fact(row.set);
        fputs(",\"after\":",stdout); pp_json_fact(row.after); fputs(",\"getfl\":",stdout); pp_json_fact(row.getfl); putchar('}');
    }
    fputs("],\"protocol\":[",stdout);
    for(int k=0;k<r->npackets;k++) {
        struct pp_packet row=r->packets[k]; if(k) putchar(','); fputs("{\"role\":",stdout); pp_json_string(pp_role(row.role)); printf(",\"direction\":\"%s\",\"seq\":%d,\"kind\":",row.outgoing?"sent":"received",row.seq); pp_json_string(row.kind);
        printf(",\"at_ns\":%" PRId64 ",\"observed_ns\":%" PRId64 ",\"length\":",row.at,row.observed); pp_json_number(row.length>=0,row.length);
        fputs(",\"sha256\":",stdout); pp_json_string(*row.sha?row.sha:NULL); fputs(",\"payload\":",stdout); pp_json_string(row.payload); putchar('}');
    }
    printf("],\"python_body\":{\"complete\":%s,\"declared_length\":",r->body_complete?"true":"false"); pp_json_number(r->body_declared>=0,r->body_declared);
    fputs(",\"declared_sha256\":",stdout); pp_json_string(*r->body_sha?r->body_sha:NULL); printf(",\"length\":%zu,\"raw_hex\":\"",r->body_len);
    for(size_t k=0;k<r->body_len;k++) printf("%02x",(unsigned int)r->body[k]);
    fputs("\"},\"times\":{",stdout);
    static const char *names[]={"pre_ready_ns","exec_go_ns","ready_ns","data_complete_ns","arm_ns","ack_ns","primary_ns","terminal_ns","reap_ns","fd_complete_ns","final_ns"};
    for(int k=0;k<11;k++) { if(k) putchar(','); pp_json_string(names[k]); putchar(':'); pp_json_number(r->times[k]>0,r->times[k]); }
    fputs("},\"native_facts\":{",stdout);
#define PP_NUMBER(name,value) printf("\"" name "\":%lld,",(long long)(value))
    PP_NUMBER("SYS_pidfd_open",SYS_pidfd_open); PP_NUMBER("SYS_pidfd_send_signal",SYS_pidfd_send_signal);
    PP_NUMBER("F_GETFD",F_GETFD); PP_NUMBER("F_SETFD",F_SETFD); PP_NUMBER("FD_CLOEXEC",FD_CLOEXEC);
    PP_NUMBER("O_CLOEXEC",O_CLOEXEC); PP_NUMBER("O_NOFOLLOW",O_NOFOLLOW); PP_NUMBER("O_NONBLOCK",O_NONBLOCK); PP_NUMBER("F_GETFL",F_GETFL);
    PP_NUMBER("EBADF",EBADF); PP_NUMBER("EAGAIN",EAGAIN); PP_NUMBER("EINTR",EINTR); PP_NUMBER("ESRCH",ESRCH);
    PP_NUMBER("SIGKILL",SIGKILL); PP_NUMBER("SIGPIPE",SIGPIPE); PP_NUMBER("POLLIN",POLLIN); PP_NUMBER("POLLNVAL",POLLNVAL); PP_NUMBER("PIPE_BUF",PIPE_BUF);
    PP_NUMBER("RLIMIT_CORE",RLIMIT_CORE); PP_NUMBER("RLIMIT_CPU",RLIMIT_CPU);
    PP_NUMBER("int_bytes",sizeof(int)); PP_NUMBER("long_bytes",sizeof(long)); PP_NUMBER("pointer_bytes",sizeof(void *)); PP_NUMBER("char_bits",CHAR_BIT); PP_NUMBER("byte_order",__BYTE_ORDER__);
    PP_NUMBER("pid_t_bytes",sizeof(pid_t)); PP_NUMBER("pid_t_signed",(pid_t)-1<0); PP_NUMBER("uid_t_bytes",sizeof(uid_t)); PP_NUMBER("uid_t_signed",(uid_t)-1<(uid_t)1);
    PP_NUMBER("dev_t_bytes",sizeof(dev_t)); PP_NUMBER("ino_t_bytes",sizeof(ino_t)); PP_NUMBER("rlim_t_bytes",sizeof(rlim_t)); PP_NUMBER("observed_pipe_buf",r->pipebuf);
#undef PP_NUMBER
    printf("\"rlimits\":{\"reported\":%s,\"core_requested\":",r->rlimits_reported?"true":"false");
    if(r->rlimits_reported) fputs("[0,0]",stdout); else fputs("null",stdout);
    fputs(",\"core_result\":",stdout); pp_json_number(r->rlimits_reported,r->core_result); fputs(",\"core_errno\":",stdout); pp_json_number(r->rlimits_reported,r->core_errno);
    fputs(",\"cpu_requested\":",stdout); if(r->rlimits_reported) fputs("[20,21]",stdout); else fputs("null",stdout);
    fputs(",\"cpu_result\":",stdout); pp_json_number(r->rlimits_reported,r->cpu_result); fputs(",\"cpu_errno\":",stdout); pp_json_number(r->rlimits_reported,r->cpu_errno);
    fputs("},\"sigpipe\":{\"set\":",stdout); pp_json_fact(r->sigpipe_set); fputs(",\"get\":",stdout); pp_json_fact(r->sigpipe_get);
    fputs(",\"ignored\":",stdout); if(r->sigpipe_get.attempted && !r->sigpipe_get.result) fputs(r->sigpipe_ignored?"true":"false",stdout); else fputs("null",stdout);
    fputs("}}}\n",stdout);
}
int main(int argc,char **argv) {
    if(argc!=12) return 64;
    struct pp_context *r=calloc(1,sizeof(*r)); if(!r) return 64;
    r->role=PP_G; r->signal_fd=-1; r->body_declared=-1;
    for(int k=0;k<PP_FDS;k++) r->fd[k]=r->original[k]=-1;
    for(int k=0;k<12;k++) {
        r->argv[k]=argv[k];
        for(const unsigned char *p=(const unsigned char *)argv[k];*p;p++) if(*p<32 || *p>126) { free(r); return 64; }
    }
    if(strcmp(argv[1],"normal") && strcmp(argv[1],"worker_loss")) { free(r); return 64; }
    r->loss=!strcmp(argv[1],"worker_loss");
    if(!pp_hash(argv[2]) || !pp_hash(argv[6]) || !pp_hash(argv[7]) || !pp_hash(argv[8])) { free(r); return 64; }
    memcpy(r->nonce,argv[2],65);
    if(strcmp(argv[10],"real_readonly_runtime") && strcmp(argv[10],"synthetic_CI_fixture")) { free(r); return 64; }
    r->fixture=!strcmp(argv[10],"synthetic_CI_fixture");
    if(!strcmp(argv[11],"none")) r->fault=0;
    else if(!strcmp(argv[11],"closed_exec")) r->fault=1;
    else if(!strcmp(argv[11],"script_hash")) r->fault=2;
    else { free(r); return 64; }
    if(r->fault && !r->fixture) { free(r); return 64; }
    unsigned int major,minor,micro; int consumed=0;
    if(sscanf(argv[9],"%u.%u.%u%n",&major,&minor,&micro,&consumed)!=3 || argv[9][consumed] || major>65535 || minor>65535 || micro>65535) { free(r); return 64; }
    char version[24]; snprintf(version,sizeof(version),"%u.%u.%u",major,minor,micro);
    if(strcmp(version,argv[9])) { free(r); return 64; }
    r->version[0]=(int)major; r->version[1]=(int)minor; r->version[2]=(int)micro;
    if(!r->fixture && (major!=3 || minor!=11)) { free(r); return 64; }
    r->t0=pp_now(r);
    if(r->t0<=0 || r->t0>INT64_MAX-35*PP_NS) { free(r); return 64; }
    r->work=r->t0+20*PP_NS; r->cleanup=r->t0+25*PP_NS; r->terminal=r->t0+28*PP_NS; r->total=r->t0+30*PP_NS; r->expiry=r->t0+35*PP_NS;
    pp_run(r);
    if(r->error.observed) {
        r->success=0; r->stage=8;
        /* Negative cleanup is close/observation only, never another signal or command. */
        if(r->fd[PP_COMMAND_W]>=0) pp_close_one(r,PP_COMMAND_W,PP_EXPLICIT);
        if(r->child>0 && r->wait_pid!=r->child && r->fd[PP_PIDFD]>=0 && pp_terminal(r,r->cleanup)) pp_reap(r,r->terminal);
    }
    for(int label=0;label<PP_FDS;label++) if(r->fd[label]>=0) pp_close_one(r,label,PP_EXPLICIT);
    r->times[9]=r->last;
    if(!pp_time(r,r->total) || r->error.observed) r->success=0;
    r->times[10]=r->last;
    pp_emit(r); int result=r->success?0:1;
    if(fflush(stdout) || ferror(stdout)) result=1;
    free(r->kernel_argv); free(r); return result;
}
