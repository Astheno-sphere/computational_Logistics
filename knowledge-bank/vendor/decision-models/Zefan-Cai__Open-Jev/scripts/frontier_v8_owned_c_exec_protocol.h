/* Fixed owned CPU protocol. No arbitrary command, cleanup signal or authority. */
#ifndef FRONTIER_V8_OWNED_C_EXEC_PROTOCOL_H
#define FRONTIER_V8_OWNED_C_EXEC_PROTOCOL_H
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/prctl.h>
#include <sys/wait.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#if !defined(SYS_pidfd_open) || !defined(SYS_pidfd_send_signal)
#error "Reviewed symbolic pidfd headers required"
#endif
/* Exactly one declaration per captured TU; do not reference these markers. */
const long frontier_v8_header_pidfd_open = SYS_pidfd_open;
const unsigned int frontier_v8_target_int_bytes = __SIZEOF_INT__;
const unsigned int frontier_v8_target_long_bytes = __SIZEOF_LONG__;
const unsigned int frontier_v8_target_pointer_bytes = __SIZEOF_POINTER__;
const unsigned int frontier_v8_target_char_bits = __CHAR_BIT__;
const unsigned int frontier_v8_target_byte_order = __BYTE_ORDER__;
const long frontier_v8_header_pidfd_send_signal = SYS_pidfd_send_signal;
const long frontier_v8_header_pr_set_child_subreaper = PR_SET_CHILD_SUBREAPER;
const long frontier_v8_header_pr_get_child_subreaper = PR_GET_CHILD_SUBREAPER;
const long frontier_v8_header_f_getfd = F_GETFD;
const long frontier_v8_header_f_setfd = F_SETFD;
const long frontier_v8_header_f_dupfd_cloexec = F_DUPFD_CLOEXEC;
const long frontier_v8_header_fd_cloexec = FD_CLOEXEC;
const long frontier_v8_header_o_cloexec = O_CLOEXEC;
const long frontier_v8_header_o_nofollow = O_NOFOLLOW;
const long frontier_v8_header_o_nonblock = O_NONBLOCK;
const long frontier_v8_header_f_getfl = F_GETFL;
const long frontier_v8_header_f_setfl = F_SETFL;
const long frontier_v8_header_ebadf = EBADF;
const long frontier_v8_header_sigkill = SIGKILL;
const long frontier_v8_header_sigpipe = SIGPIPE;
const long frontier_v8_header_pollin = POLLIN;
const long frontier_v8_header_pollnval = POLLNVAL;
const long frontier_v8_header_pipe_buf = PIPE_BUF;
_Static_assert(sizeof(int)==4 && INT_MAX==INT32_MAX, "signed32 int required");
_Static_assert(sizeof(pid_t)==4 && (pid_t)-1<0, "signed32 pid required");
_Static_assert(sizeof(uid_t)==4 && (uid_t)-1>0, "unsigned32 uid required");
_Static_assert(sizeof(uint64_t)==8 && sizeof(int64_t)==8 && CHAR_BIT==8,
               "Declared JSON integer representation required");
_Static_assert(sizeof(int)==__SIZEOF_INT__ && sizeof(long)==__SIZEOF_LONG__ &&
               sizeof(void *)==__SIZEOF_POINTER__, "Compiler target differs");
_Static_assert(sizeof(dev_t)<=8 && sizeof(ino_t)<=8, "stat operands too wide");

#define EX_NS INT64_C(1000000000)
#define EX_MAGIC UINT32_C(0x4a455658)
#define EX_MAX 256
enum { EX_G, EX_X, EX_E, EX_D, EX_ROLES };
enum { EX_GE, EX_GD, EX_ED, EX_HANDLES };
enum { EX_EDGE_GE, EX_EDGE_ED, EX_EDGE_ERROR, EX_EDGES };
enum { EX_NORMAL, EX_LOSS };
enum { EX_NOFAULT, EX_CLOSED_EXEC, EX_LEAK_WITNESS };
enum { EX_PREEXEC, EX_ENTRY, EX_CHILD, EX_STDIO };
enum { EX_EXPLICIT, EX_ENTRY_CLOSED, EX_REPORT_EOF, EX_OWNER_DEATH,
       EX_ABSENT, EX_UNRETURNED };
enum { EX_SELF_FD, EX_LEAF_FD, EX_WITNESS_FD, EX_COMMAND_R, EX_COMMAND_W,
       EX_REPORT_R, EX_REPORT_W, EX_ERROR_R, EX_ERROR_W, EX_GE_FD,
       EX_CHILD_COMMAND_R, EX_CHILD_COMMAND_W, EX_CHILD_REPORT_R,
       EX_CHILD_REPORT_W, EX_ED_FD, EX_GD_FD, EX_STD0, EX_STD1, EX_STD2,
       EX_FDS };
enum { EX_PRE_READY=1, EX_EXEC, EX_ENTER, EX_POST_READY, EX_CREATE,
       EX_D_CREATED, EX_D_READY, EX_HANDLE, EX_ARM, EX_ARM_ACK,
       EX_ALL_ACK, EX_FINISH, EX_D_FINISH_ACK, EX_E_FINISH_ACK,
       EX_FD_CLOSE, EX_FD_FLAGS, EX_SUB, EX_SIGPIPE, EX_STARTUP,
       EX_WAIT, EX_POLL, EX_FORWARD, EX_ERROR, EX_EXEC_ERROR, EX_PRODUCT };
enum { EX_INITIAL, EX_PRE, EX_EXEC_STAGE, EX_STARTUP_STAGE, EX_POST,
       EX_CREATED, EX_ARMED, EX_FINISH_STAGE, EX_LOSS_STAGE, EX_ADOPT,
       EX_TERMINAL, EX_NEGATIVE };
enum { EX_OP_ARGUMENT, EX_OP_CLOCK, EX_OP_DEADLINE, EX_OP_OPEN,
       EX_OP_FSTAT, EX_OP_PROC, EX_OP_PRODUCT, EX_OP_PRCTL, EX_OP_PIPE,
       EX_OP_FLAGS, EX_OP_WRITE, EX_OP_POLL, EX_OP_READ, EX_OP_FRAME,
       EX_OP_SEQUENCE, EX_OP_PIDFD_OPEN, EX_OP_FDINFO, EX_OP_PIDFD_POLL,
       EX_OP_FORK, EX_OP_EXEC, EX_OP_WAIT, EX_OP_ADOPT, EX_OP_SIGNAL,
       EX_OP_CLOSE, EX_OP_SIGPIPE, EX_OP_STATE, EX_OP_CAPACITY,
       EX_OP_STARTUP };
enum { EX_T_INITIAL, EX_T_PRE_READY, EX_T_EXEC_SENT, EX_T_EXEC_ENTER,
       EX_T_POST_READY, EX_T_POST_VALID, EX_T_CREATE, EX_T_D_READY,
       EX_T_BOUND, EX_T_ARM, EX_T_ALL_ACK, EX_T_PRIMARY, EX_T_FINISH,
       EX_T_E_SIGNAL, EX_T_E_TERM, EX_T_E_REAP, EX_T_ADOPT,
       EX_T_D_SIGNAL, EX_T_D_TERM, EX_T_D_REAP, EX_T_FD_COMPLETE,
       EX_T_RESET, EX_T_FINAL, EX_TIMES };
struct ex_fact { int attempted, result, err, value; int64_t at; };
struct ex_product { uint64_t dev, ino, size; int64_t mtime_ns, ctime_ns; };
struct ex_identity {
    int known, pid, ppid; uint32_t uid,euid; uint64_t start;
    char boot[37], state; struct ex_product product;
};
struct ex_error {
    int observed, role, stage, operation, err, result_known, result; int64_t at;
};
struct ex_poll {
    int owner,target,key,fd,stage,attempts,result,revents,err; int64_t at;
};
struct ex_wait {
    int owner,target,pid,attempts,result,status,err; int64_t at;
};
struct ex_handle {
    int known,key,fd,fdi_pid,matches,kernel;
    struct ex_fact open,flags,close,badfd;
    struct ex_identity before,after;
    struct ex_poll live;
};
struct ex_handle_wire {
    int key,fd,fdi_pid,matches;
    struct ex_fact open,flags;
    struct ex_identity before,after;
    struct ex_poll live;
};
struct ex_close {
    int owner,label,epoch,fd,evidence; struct ex_fact close,badfd;
};
struct ex_flags {
    int owner,label,epoch,fd;
    struct ex_fact before,set,after,getfl;
};
struct ex_startup { int label,fd; struct ex_fact fact; };
struct ex_small_fact { int key; struct ex_fact fact; };
struct ex_forward { int kind,original_seq; int64_t at; };
struct ex_command { struct ex_identity worker,descendant; };
struct ex_product_check { int label,fd; struct ex_product product; };
struct ex_frame {
    uint32_t magic; int schema,kind,source,case_id,fault,edge,seq,aux;
    int64_t t0,at; char nonce[65];
    union {
        struct ex_identity identity; struct ex_handle_wire handle;
        struct ex_close close; struct ex_flags flags;
        struct ex_startup startup; struct ex_small_fact fact;
        struct ex_wait wait; struct ex_poll poll; struct ex_forward forward;
        struct ex_error error; struct ex_command command;
        struct ex_product_check product;
    } body;
};
_Static_assert(sizeof(struct ex_frame)<=512 && sizeof(struct ex_frame)<=PIPE_BUF,
               "Private frame exceeds declared atomic bound");
struct ex_packet {
    int source,transport,outgoing,kind,edge,seq,aux,forwarded;
    int64_t sent,observed;
};
struct ex_signal {
    int consumed,attempts,result,err,fd; int64_t at;
    struct ex_identity before;
};
struct ex_context {
    int role,case_id,fault,stage,in,out,pipebuf,seq[EX_EDGES];
    char nonce[65];
    int incoming[EX_ROLES][EX_EDGES]; int64_t incoming_at[EX_ROLES][EX_EDGES];
    int fd[EX_FDS],acquired_fd[EX_FDS],child,created[2],bound[2],adopted[2],terminal[2],reaped[2];
    int d_authorized,success,exec_attempted,exec_returned,exec_result,exec_errno;
    int64_t exec_enter,error_eof,t0,work,cleanup,terminal_end,total,expiry,last;
    struct ex_error error;
    struct ex_product guardian_product,leaf_product;
    struct ex_identity ids[EX_ROLES],checks[7],adoption,adoption_guardian;
    int64_t adoption_at;
    struct ex_fact sub[5],child_sub[EX_ROLES],sigpipe[EX_ROLES][2];
    struct ex_startup startup[5];
    struct ex_product_check product_checks[2]; int product_checked[2];
    struct ex_handle handles[EX_HANDLES];
    struct ex_wait waits[EX_HANDLES]; struct ex_signal signals[2];
    struct ex_poll polls[EX_MAX]; int npolls;
    struct ex_close closes[EX_MAX]; int ncloses;
    struct ex_flags flags[EX_MAX]; int nflags;
    struct ex_packet packets[EX_MAX]; int npackets;
    struct ex_forward forwards[8]; int nforwards;
    int64_t times[EX_TIMES];
};
static inline const char *ex_role_name(int k) {
    static const char *v[]={"guardian","preexec_worker","worker","descendant"};
    return k>=0 && k<EX_ROLES?v[k]:"invalid";
}
static inline const char *ex_label_name(int k) {
    static const char *v[]={"guardian_product","leaf_exec","leaf_witness",
        "command_read","command_write","report_read","report_write",
        "exec_error_read","exec_error_write","G_E","child_command_read",
        "child_command_write","child_report_read","child_report_write",
        "E_D","G_D","original_stdin","original_stdout","original_stderr"};
    return k>=0 && k<EX_FDS?v[k]:"invalid";
}
static inline const char *ex_kind_name(int k) {
    static const char *v[]={"invalid","PRE_EXEC_READY","EXEC","EXEC_ENTER",
        "POST_EXEC_READY","CREATE_D","D_CREATED","D_READY","HANDLE_FACT",
        "ARM","ARM_ACK","ALL_ARM_ACK","FINISH","D_FINISH_ACK","E_FINISH_ACK",
        "FD_CLOSE_FACT","FD_FLAGS_FACT","SUBREAPER_GET","SIGPIPE_FACT",
        "STARTUP_FD_FACT","WAIT_FACT","POLL_FACT","COMMAND_FORWARDED",
        "ERROR","EXEC_ERROR","PRODUCT_CHECK"};
    return k>=0 && k<=EX_PRODUCT?v[k]:"invalid";
}
static inline const char *ex_stage_name(int k) {
    static const char *v[]={"initial","preexec","exec","startup","postexec",
        "created","armed","finish","worker_loss","adoption","terminal","negative"};
    return k>=0 && k<=EX_NEGATIVE?v[k]:"invalid";
}
static inline const char *ex_op_name(int k) {
    static const char *v[]={"argument","clock_gettime","deadline","open",
        "fstat","proc_identity","product_identity","prctl","pipe2",
        "fcntl","write","poll","read","private_frame","sequence",
        "pidfd_open","fdinfo","pidfd_poll","fork","fexecve","waitpid",
        "adoption","pidfd_send_signal","close","sigaction","state",
        "capacity","startup_fd"};
    return k>=0 && k<=EX_OP_STARTUP?v[k]:"invalid";
}
static inline void ex_init(struct ex_context *r,int role) {
    int k; memset(r,0,sizeof(*r)); r->role=role; r->in=r->out=-1;
    for(k=0;k<EX_FDS;k++) r->fd[k]=r->acquired_fd[k]=-1;
    for(k=0;k<EX_HANDLES;k++) r->handles[k].fd=-1;
    for(k=0;k<5;k++) {
        static const int labels[]={EX_LEAF_FD,EX_WITNESS_FD,EX_ERROR_W,EX_COMMAND_R,EX_REPORT_W};
        r->startup[k].fd=-1; r->startup[k].label=labels[k];
    }
    for(k=0;k<2;k++) r->signals[k].fd=-1;
}
static inline void ex_fail(struct ex_context *r,int op,int err,int known,int result) {
    if(!r->error.observed) {
        r->error.observed=1; r->error.role=r->role; r->error.stage=r->stage;
        r->error.operation=op; r->error.err=err; r->error.result_known=known;
        r->error.result=result; r->error.at=r->last;
    }
}
static inline int64_t ex_now(struct ex_context *r) {
    struct timespec t; int rc; int64_t n;
    errno=0; rc=clock_gettime(CLOCK_MONOTONIC,&t);
    if(rc || t.tv_sec<0 || t.tv_nsec<0 || t.tv_nsec>=EX_NS ||
       t.tv_sec>(INT64_MAX-t.tv_nsec)/EX_NS) {
        ex_fail(r,EX_OP_CLOCK,errno,1,rc); return -1;
    }
    n=(int64_t)t.tv_sec*EX_NS+t.tv_nsec;
    if(n<=0 || n<r->last) { ex_fail(r,EX_OP_CLOCK,0,0,0); return -1; }
    r->last=n; return n;
}
static inline int ex_gate(struct ex_context *r,int64_t end,int action) {
    int64_t n;
    if(action && r->error.observed) return 0;
    n=ex_now(r);
    if(n<0) return 0;
    if(n>=end) { ex_fail(r,EX_OP_DEADLINE,0,0,0); return 0; }
    return 1;
}
static inline int ex_deadlines(struct ex_context *r) {
    if(r->t0<=0 || r->t0>INT64_MAX-14*EX_NS) {
        ex_fail(r,EX_OP_CLOCK,0,0,0); return 0;
    }
    r->work=r->t0+5*EX_NS; r->cleanup=r->t0+8*EX_NS;
    r->terminal_end=r->t0+10*EX_NS; r->total=r->t0+12*EX_NS;
    r->expiry=r->t0+14*EX_NS; return 1;
}
static inline void ex_fact_set(struct ex_context *r,struct ex_fact *f,
                               int result,int err,int value) {
    f->attempted=1; f->result=result; f->err=err; f->value=value;
    f->at=ex_now(r); if(f->at<0) f->at=0;
}
static inline int ex_same_product(const struct ex_product *a,const struct ex_product *b) {
    return a->dev==b->dev && a->ino==b->ino && a->size==b->size &&
        a->mtime_ns==b->mtime_ns && a->ctime_ns==b->ctime_ns;
}
static inline int ex_product_fd(int fd,struct ex_product *p) {
    struct stat s;
    if(fstat(fd,&s) || !S_ISREG(s.st_mode) || s.st_size<=0 ||
       s.st_size>32*1024*1024 || (s.st_mode&(S_ISUID|S_ISGID)) ||
       s.st_mtim.tv_sec<0 || s.st_ctim.tv_sec<0 ||
       s.st_mtim.tv_nsec<0 || s.st_mtim.tv_nsec>=EX_NS ||
       s.st_ctim.tv_nsec<0 || s.st_ctim.tv_nsec>=EX_NS ||
       s.st_mtim.tv_sec>(INT64_MAX-s.st_mtim.tv_nsec)/EX_NS ||
       s.st_ctim.tv_sec>(INT64_MAX-s.st_ctim.tv_nsec)/EX_NS) return 0;
    p->dev=(uint64_t)s.st_dev; p->ino=(uint64_t)s.st_ino;
    p->size=(uint64_t)s.st_size;
    p->mtime_ns=(int64_t)s.st_mtim.tv_sec*EX_NS+s.st_mtim.tv_nsec;
    p->ctime_ns=(int64_t)s.st_ctim.tv_sec*EX_NS+s.st_ctim.tv_nsec;
    return 1;
}
static inline int ex_text(const char *path,char *body,size_t cap) {
    int fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW); size_t used=0; ssize_t n;
    if(fd<0) return 0;
    while(used<cap) {
        n=read(fd,body+used,cap-used);
        if(n<0) { int saved=errno; (void)close(fd); errno=saved; return 0; }
        if(!n) break;
        used+=(size_t)n;
    }
    if(close(fd) || used==cap || memchr(body,0,used)) return 0;
    body[used]=0; return 1;
}
static inline int ex_capture(int pid,struct ex_identity *out) {
    char path[80],body[4097],boot[80],*p,*end; long long v;
    unsigned long long u,e; int field,fd; struct ex_identity id={0};
    snprintf(path,sizeof(path),"/proc/%d/stat",pid);
    if(!ex_text(path,body,sizeof(body)-1)) return 0;
    errno=0; v=strtoll(body,&end,10);
    if(errno || v!=pid || end==body || *end!=' ' || end[1]!='(') return 0;
    p=strrchr(end,')'); if(!p || p[1]!=' ' || !p[2] || p[3]!=' ') return 0;
    id.state=p[2]; p+=4;
    for(field=4;field<=22;field++) {
        errno=0; v=strtoll(p,&end,10);
        if(errno || end==p) return 0;
        if(field==4) { if(v<=0 || v>INT32_MAX) return 0; id.ppid=(int)v; }
        if(field==22) { if(v<=0) return 0; id.start=(uint64_t)v; }
        p=end; while(*p==' ') p++;
    }
    snprintf(path,sizeof(path),"/proc/%d/status",pid);
    if(!ex_text(path,body,sizeof(body)-1) || !(p=strstr(body,"\nUid:"))) return 0;
    p+=5; errno=0; u=strtoull(p,&end,10);
    if(errno || p==end || u>UINT32_MAX) return 0;
    p=end; errno=0; e=strtoull(p,&end,10);
    if(errno || p==end || e>UINT32_MAX) return 0;
    if(!ex_text("/proc/sys/kernel/random/boot_id",boot,sizeof(boot)-1) ||
       strlen(boot)!=37 || boot[36]!='\n') return 0;
    boot[36]=0; memcpy(id.boot,boot,37);
    snprintf(path,sizeof(path),"/proc/%d/exe",pid);
    fd=open(path,O_RDONLY|O_CLOEXEC);
    if(fd<0) return 0;
    if(!ex_product_fd(fd,&id.product)) {
        int saved=errno; (void)close(fd); errno=saved; return 0;
    }
    if(close(fd)) return 0;
    id.pid=pid; id.uid=(uint32_t)u; id.euid=(uint32_t)e; id.known=1;
    *out=id; return 1;
}
static inline int ex_same_process(const struct ex_identity *a,const struct ex_identity *b,
                                  int ignore_parent) {
    return a->known && b->known && a->pid==b->pid &&
        (ignore_parent || a->ppid==b->ppid) && a->start==b->start &&
        a->uid==b->uid && a->euid==b->euid && !strcmp(a->boot,b->boot);
}
static inline int ex_same_identity(const struct ex_identity *a,const struct ex_identity *b,
                                   int ignore_parent) {
    return ex_same_process(a,b,ignore_parent) && ex_same_product(&a->product,&b->product);
}
static inline int ex_alive(const struct ex_identity *id) {
    return id->known && id->state!='Z' && id->state!='X' && id->state!='x';
}
static inline int ex_fdinfo(int fd,int *pid) {
    char path[80],body[4097],*p,*end; long v; int seen=0;
    snprintf(path,sizeof(path),"/proc/self/fdinfo/%d",fd);
    if(!ex_text(path,body,sizeof(body)-1)) return 0;
    for(p=body;*p;) {
        char *line=strchr(p,'\n'); if(!line) return 0;
        if(!strncmp(p,"Pid:",4)) {
            if(++seen!=1) return 0;
            errno=0; v=strtol(p+4,&end,10);
            if(errno || end==p+4 || v<=0 || v>INT32_MAX) return 0;
            while(end<line && (*end==' ' || *end=='\t')) end++;
            if(end!=line) return 0; *pid=(int)v;
        }
        p=line+1;
    }
    return seen==1;
}
static inline void ex_packet(struct ex_context *r,const struct ex_frame *f,
                              int transport,int outgoing,int forwarded) {
    struct ex_packet *p;
    if(r->role!=EX_G) return;
    if(r->npackets>=EX_MAX) { ex_fail(r,EX_OP_CAPACITY,0,0,0); return; }
    p=&r->packets[r->npackets++]; p->source=f->source; p->transport=transport;
    p->outgoing=outgoing; p->kind=f->kind; p->edge=f->edge; p->seq=f->seq;
    p->aux=f->aux; p->sent=f->at; p->observed=ex_now(r); p->forwarded=forwarded;
}
static inline struct ex_frame ex_frame_make(struct ex_context *r,int kind,int edge,int aux) {
    struct ex_frame f; memset(&f,0,sizeof(f)); f.magic=EX_MAGIC; f.schema=1;
    f.kind=kind; f.source=r->role; f.case_id=r->case_id; f.fault=r->fault;
    f.edge=edge; f.seq=++r->seq[edge]; f.aux=aux; f.t0=r->t0;
    memcpy(f.nonce,r->nonce,65); f.at=ex_now(r); return f;
}
static inline int ex_io_poll(struct ex_context *r,int fd,short events,int64_t end) {
    struct pollfd p={fd,events,0}; int rc; int64_t n,remaining; int timeout;
    if(!ex_gate(r,end,0)) return 0;
    n=r->last; remaining=end-n;
    timeout=(int)(remaining/INT64_C(1000000)); if(timeout<1) timeout=1;
    errno=0; rc=poll(&p,1,timeout);
    if(rc<0 || (p.revents&(POLLERR|POLLNVAL))) {
        ex_fail(r,EX_OP_POLL,errno,1,rc); return 0;
    }
    if(!ex_gate(r,end,0)) return 0;
    if(!rc) { ex_fail(r,EX_OP_DEADLINE,0,0,0); return 0; }
    return !!(p.revents&(events|POLLHUP));
}
static inline int ex_write_frame(struct ex_context *r,int fd,const struct ex_frame *f,
                                 int64_t end,int action) {
    ssize_t n;
    if(!ex_io_poll(r,fd,POLLOUT,end) || !ex_gate(r,end,action)) return 0;
    errno=0; n=write(fd,f,sizeof(*f));
    if(n!=(ssize_t)sizeof(*f)) { ex_fail(r,EX_OP_WRITE,errno,1,(int)n); return 0; }
    return ex_gate(r,end,0);
}
/* Successful partial reads accumulate; each failed syscall is permanent. */
static inline int ex_read_frame(struct ex_context *r,int fd,struct ex_frame *f,
                                int64_t end,int allow_eof) {
    size_t used=0; ssize_t n;
    while(used<sizeof(*f)) {
        if(!ex_io_poll(r,fd,POLLIN,end)) return -1;
        errno=0; n=read(fd,(char *)f+used,sizeof(*f)-used);
        if(n<0) { ex_fail(r,EX_OP_READ,errno,1,(int)n); return -1; }
        if(!n) {
            if(!used && allow_eof) return 0;
            ex_fail(r,EX_OP_READ,0,1,0); return -1;
        }
        used+=(size_t)n;
    }
    if(!ex_gate(r,end,0)) return -1;
    if(f->magic!=EX_MAGIC || f->schema!=1 || f->kind<EX_PRE_READY ||
       f->kind>EX_PRODUCT || f->source<EX_G || f->source>=EX_ROLES ||
       f->edge<0 || f->edge>=EX_EDGES || f->case_id!=r->case_id ||
       f->fault!=r->fault || f->t0!=r->t0 || memcmp(f->nonce,r->nonce,65) ||
       f->seq<=0 || f->at<r->t0 || f->at>r->last) {
        ex_fail(r,EX_OP_FRAME,0,0,0); return -1;
    }
    return 1;
}
static inline int ex_emit(struct ex_context *r,struct ex_frame *f) {
    return ex_write_frame(r,r->out,f,r->error.observed?r->expiry:r->terminal_end,0);
}
static inline void ex_store_close(struct ex_context *r,const struct ex_close *c) {
    if(r->role==EX_G) {
        if(r->ncloses>=EX_MAX) ex_fail(r,EX_OP_CAPACITY,0,0,0);
        else r->closes[r->ncloses++]=*c;
    } else {
        struct ex_frame f=ex_frame_make(r,EX_FD_CLOSE,r->role==EX_D?EX_EDGE_ED:EX_EDGE_GE,0);
        f.body.close=*c; (void)ex_emit(r,&f);
    }
}
static inline int ex_close_owned(struct ex_context *r,int label,int epoch,int report) {
    struct ex_close c; int rc,err,fd=r->fd[label]; int64_t end;
    if(fd<0) return 1;
    memset(&c,0,sizeof(c)); c.owner=r->role; c.label=label; c.epoch=epoch;
    c.fd=fd; c.evidence=EX_EXPLICIT;
    end=r->error.observed?(r->role==EX_G?r->total:r->expiry):r->terminal_end;
    if(!ex_gate(r,end,0)) return 0;
    r->fd[label]=-1; errno=0; rc=close(fd); err=errno;
    if(rc) ex_fail(r,EX_OP_CLOSE,err,1,rc);
    ex_fact_set(r,&c.close,rc,err,0);
    errno=0; rc=fcntl(fd,F_GETFD); err=errno;
    ex_fact_set(r,&c.badfd,rc,err,0);
    if(rc!=-1 || err!=EBADF) ex_fail(r,EX_OP_CLOSE,err,1,rc);
    if(report) ex_store_close(r,&c);
    return !r->error.observed;
}
static inline void ex_store_flags(struct ex_context *r,const struct ex_flags *v) {
    if(r->role==EX_G) {
        if(r->nflags>=EX_MAX) ex_fail(r,EX_OP_CAPACITY,0,0,0);
        else r->flags[r->nflags++]=*v;
    } else {
        struct ex_frame f=ex_frame_make(r,EX_FD_FLAGS,r->role==EX_D?EX_EDGE_ED:EX_EDGE_GE,0);
        f.body.flags=*v; (void)ex_emit(r,&f);
    }
}
static inline int ex_flags_check(struct ex_context *r,int label,int epoch,int retain) {
    struct ex_flags v; int fd=r->fd[label],rc,err;
    memset(&v,0,sizeof(v)); v.owner=r->role; v.label=label; v.epoch=epoch; v.fd=fd;
    errno=0; rc=fcntl(fd,F_GETFD); err=errno; ex_fact_set(r,&v.before,rc,err,0);
    if(rc<0 || (retain<0 && !(rc&FD_CLOEXEC))) ex_fail(r,EX_OP_FLAGS,err,1,rc);
    if(retain>=0 && !r->error.observed) {
        int flags=retain?rc&~FD_CLOEXEC:rc|FD_CLOEXEC;
        errno=0; rc=fcntl(fd,F_SETFD,flags); err=errno;
        ex_fact_set(r,&v.set,rc,err,flags);
        if(rc) ex_fail(r,EX_OP_FLAGS,err,1,rc);
        errno=0; rc=fcntl(fd,F_GETFD); err=errno;
        ex_fact_set(r,&v.after,rc,err,0);
        if(rc<0 || !!(rc&FD_CLOEXEC)==!!retain) ex_fail(r,EX_OP_FLAGS,err,1,rc);
    }
    errno=0; rc=fcntl(fd,F_GETFL); err=errno; ex_fact_set(r,&v.getfl,rc,err,0);
    if(rc<0 || (((label>=EX_COMMAND_R && label<=EX_ERROR_W) ||
                  (label>=EX_CHILD_COMMAND_R && label<=EX_CHILD_REPORT_W)) && !(rc&O_NONBLOCK)))
        ex_fail(r,EX_OP_FLAGS,err,1,rc);
    ex_store_flags(r,&v); return !r->error.observed;
}
static inline int ex_pipe(struct ex_context *r,int read_label,int write_label,int epoch) {
    int p[2],rc; long bound; errno=0; rc=pipe2(p,O_CLOEXEC|O_NONBLOCK);
    if(rc) { ex_fail(r,EX_OP_PIPE,errno,1,rc); return 0; }
    r->fd[read_label]=p[0]; r->fd[write_label]=p[1];
    r->acquired_fd[read_label]=p[0]; r->acquired_fd[write_label]=p[1];
    errno=0; bound=fpathconf(p[0],_PC_PIPE_BUF);
    if(bound<(long)sizeof(struct ex_frame) || bound>INT_MAX) {
        ex_fail(r,EX_OP_PIPE,errno,1,bound>INT_MAX?-1:(int)bound); return 0;
    }
    if(!r->pipebuf || bound<r->pipebuf) r->pipebuf=(int)bound;
    return ex_flags_check(r,read_label,epoch,-1) && ex_flags_check(r,write_label,epoch,-1);
}
static inline int ex_sub_get(struct ex_context *r,struct ex_fact *f,int required) {
    int value=-1,rc,err; errno=0; rc=prctl(PR_GET_CHILD_SUBREAPER,&value,0UL,0UL,0UL); err=errno;
    ex_fact_set(r,f,rc,err,value);
    if(rc || value!=required) ex_fail(r,EX_OP_PRCTL,err,1,rc);
    return !r->error.observed;
}
static inline int ex_sub_set(struct ex_context *r,struct ex_fact *f,int value) {
    int rc,err; errno=0; rc=prctl(PR_SET_CHILD_SUBREAPER,(unsigned long)value,0UL,0UL,0UL); err=errno;
    ex_fact_set(r,f,rc,err,value); if(rc) ex_fail(r,EX_OP_PRCTL,err,1,rc);
    return !r->error.observed;
}
static inline int ex_sigpipe(struct ex_context *r) {
    struct sigaction old,action; int rc,err; struct ex_frame f;
    errno=0; rc=sigaction(SIGPIPE,NULL,&old); err=errno;
    ex_fact_set(r,&r->sigpipe[r->role][0],rc,err,rc==0 && old.sa_handler==SIG_IGN);
    if(rc) ex_fail(r,EX_OP_SIGPIPE,err,1,rc);
    memset(&action,0,sizeof(action)); action.sa_handler=SIG_IGN;
    if(sigemptyset(&action.sa_mask)) { ex_fail(r,EX_OP_SIGPIPE,errno,1,-1); return 0; }
    errno=0; rc=sigaction(SIGPIPE,&action,NULL); err=errno;
    ex_fact_set(r,&r->sigpipe[r->role][1],rc,err,1);
    if(rc) ex_fail(r,EX_OP_SIGPIPE,err,1,rc);
    if(r->role!=EX_G && r->out>=0) {
        f=ex_frame_make(r,EX_SIGPIPE,r->role==EX_D?EX_EDGE_ED:EX_EDGE_GE,0);
        f.body.fact.key=0; f.body.fact.fact=r->sigpipe[r->role][0]; (void)ex_emit(r,&f);
        f=ex_frame_make(r,EX_SIGPIPE,r->role==EX_D?EX_EDGE_ED:EX_EDGE_GE,1);
        f.body.fact.key=1; f.body.fact.fact=r->sigpipe[r->role][1]; (void)ex_emit(r,&f);
    }
    return !r->error.observed;
}
static inline int ex_pidfd_poll(struct ex_context *r,int key,int stage,int64_t end,int terminal) {
    struct ex_handle *h=&r->handles[key]; struct ex_poll q;
    struct pollfd p; int rc,err,timeout; int64_t left;
    memset(&q,0,sizeof(q)); q.owner=key==EX_ED?EX_E:EX_G;
    q.target=key==EX_GE?EX_E:EX_D; q.key=key; q.fd=h->fd; q.stage=stage;
    if(!h->known || h->close.attempted) { ex_fail(r,EX_OP_STATE,0,0,0); return 0; }
    p.fd=h->fd; p.events=POLLIN;
    do {
        if(!ex_gate(r,end,0)) break;
        left=end-r->last; timeout=terminal?(int)(left/INT64_C(1000000)):0;
        if(terminal && timeout<1) timeout=1;
        p.revents=0; errno=0; rc=poll(&p,1,timeout); err=errno;
        q.attempts++; q.result=rc; q.revents=p.revents; q.err=err; q.at=ex_now(r);
        if(q.at>=end) ex_fail(r,EX_OP_DEADLINE,0,0,0);
        if(rc<0 || (p.revents&(POLLERR|POLLNVAL))) {
            ex_fail(r,EX_OP_PIDFD_POLL,err,1,rc); break;
        }
        if(!terminal) {
            if(rc || p.revents) ex_fail(r,EX_OP_PIDFD_POLL,err,1,rc);
            break;
        }
        if(rc>0 && (p.revents&POLLIN)) break;
    } while(!r->error.observed);
    if(r->role==EX_G) {
        if(r->npolls>=EX_MAX) ex_fail(r,EX_OP_CAPACITY,0,0,0);
        else r->polls[r->npolls++]=q;
    } else {
        struct ex_frame f=ex_frame_make(r,EX_POLL,EX_EDGE_GE,key);
        f.body.poll=q; (void)ex_emit(r,&f);
    }
    if(stage==EX_INITIAL) h->live=q;
    return !r->error.observed && q.attempts>0 && (terminal?(q.result>0 && (q.revents&POLLIN)):
                                                    (!q.result && !q.revents));
}
static inline int ex_handle_open(struct ex_context *r,int key,const struct ex_identity *id) {
    struct ex_handle *h=&r->handles[key]; long rc; int err;
    if(h->known || !ex_gate(r,r->work,1)) return 0;
    h->key=key; h->before=*id;
    errno=0; rc=syscall((long)SYS_pidfd_open,(long)id->pid,(unsigned long)0); err=errno;
    ex_fact_set(r,&h->open,rc>=0 && rc<=INT_MAX?(int)rc:-1,err,0);
    if(rc<0 || rc>INT_MAX) { ex_fail(r,EX_OP_PIDFD_OPEN,err,1,-1); return 0; }
    h->known=1; h->fd=(int)rc;
    r->fd[key==EX_GE?EX_GE_FD:key==EX_GD?EX_GD_FD:EX_ED_FD]=h->fd;
    r->acquired_fd[key==EX_GE?EX_GE_FD:key==EX_GD?EX_GD_FD:EX_ED_FD]=h->fd;
    if(!ex_fdinfo(h->fd,&h->fdi_pid) || h->fdi_pid!=id->pid ||
       !ex_capture(id->pid,&h->after) || !ex_same_identity(id,&h->after,0) || !ex_alive(&h->after)) {
        ex_fail(r,EX_OP_FDINFO,errno,0,0); return 0;
    }
    h->matches=1; errno=0; rc=fcntl(h->fd,F_GETFD); err=errno;
    ex_fact_set(r,&h->flags,(int)rc,err,0);
    if(rc<0 || !(rc&FD_CLOEXEC)) { ex_fail(r,EX_OP_FLAGS,err,1,(int)rc); return 0; }
    if(!ex_pidfd_poll(r,key,EX_INITIAL,r->work,0)) return 0;
    if(r->role!=EX_G) {
        struct ex_frame f=ex_frame_make(r,EX_HANDLE,EX_EDGE_GE,key);
        struct ex_handle_wire *w=&f.body.handle;
        w->key=key; w->fd=h->fd; w->fdi_pid=h->fdi_pid; w->matches=h->matches;
        w->open=h->open; w->flags=h->flags; w->before=h->before; w->after=h->after; w->live=h->live;
        (void)ex_emit(r,&f);
    }
    return !r->error.observed;
}
static inline int ex_handle_close(struct ex_context *r,int key,int report) {
    struct ex_handle *h=&r->handles[key]; int label,rc,err;
    if(!h->known || h->close.attempted) return !r->error.observed;
    label=key==EX_GE?EX_GE_FD:key==EX_GD?EX_GD_FD:EX_ED_FD;
    if(!ex_gate(r,r->error.observed?(r->role==EX_G?r->total:r->expiry):r->terminal_end,0)) return 0;
    r->fd[label]=-1; errno=0; rc=close(h->fd); err=errno;
    ex_fact_set(r,&h->close,rc,err,0); if(rc) ex_fail(r,EX_OP_CLOSE,err,1,rc);
    errno=0; rc=fcntl(h->fd,F_GETFD); err=errno;
    ex_fact_set(r,&h->badfd,rc,err,0); if(rc!=-1 || err!=EBADF) ex_fail(r,EX_OP_CLOSE,err,1,rc);
    if(report) {
        struct ex_close c; memset(&c,0,sizeof(c)); c.owner=r->role; c.label=label;
        c.epoch=key==EX_GE?EX_PREEXEC:EX_CHILD; c.fd=h->fd; c.evidence=EX_EXPLICIT;
        c.close=h->close; c.badfd=h->badfd; ex_store_close(r,&c);
    }
    return !r->error.observed;
}
static inline int ex_wait_child(struct ex_context *r,int key,int pid,int64_t end) {
    struct ex_wait *w=&r->waits[key]; struct timespec pause={0,INT64_C(1000000)};
    int status=0,rc,err;
    if(w->attempts && w->result>0) { ex_fail(r,EX_OP_WAIT,0,0,0); return 0; }
    w->owner=r->role; w->target=key==EX_GE?EX_E:EX_D; w->pid=pid;
    do {
        if(!ex_gate(r,end,0)) break;
        errno=0; rc=waitpid((pid_t)pid,&status,WNOHANG); err=errno;
        w->attempts++; w->result=rc; w->status=status; w->err=err; w->at=ex_now(r);
        if(w->at>=end) ex_fail(r,EX_OP_DEADLINE,0,0,0);
        if(rc<0) { ex_fail(r,EX_OP_WAIT,err,1,rc); break; }
        if(rc==pid) break;
        if(rc) { ex_fail(r,EX_OP_WAIT,err,1,rc); break; }
        errno=0; if(nanosleep(&pause,NULL)) { ex_fail(r,EX_OP_WAIT,errno,1,-1); break; }
    } while(1);
    if(r->role!=EX_G) {
        struct ex_frame f=ex_frame_make(r,EX_WAIT,EX_EDGE_GE,key);
        f.body.wait=*w; (void)ex_emit(r,&f);
    }
    return w->attempts>0 && w->result==pid;
}
static inline int ex_command_read(struct ex_context *r,int kind,int seq,
                                   int64_t end,struct ex_frame *f,int allow_eof) {
    int rc=ex_read_frame(r,r->in,f,end,allow_eof);
    if(rc<=0) return rc;
    if(f->source!=EX_G || f->edge!=EX_EDGE_GE || f->kind!=kind || f->seq!=seq || f->aux ||
       f->at>=r->work || !ex_same_identity(&f->body.command.worker,&r->ids[EX_E],0)) {
        ex_fail(r,EX_OP_FRAME,0,0,0); return -1;
    }
    if(r->role==EX_D && !ex_same_identity(&f->body.command.descendant,&r->ids[EX_D],0)) {
        ex_fail(r,EX_OP_FRAME,0,0,0); return -1;
    }
    return 1;
}
static inline void ex_error_up(struct ex_context *r,int exec_error) {
    struct ex_frame f; int fd=r->out;
    if(!r->error.observed) ex_fail(r,EX_OP_STATE,0,0,0);
    f=ex_frame_make(r,exec_error?EX_EXEC_ERROR:EX_ERROR,
        exec_error?EX_EDGE_ERROR:(r->role==EX_D?EX_EDGE_ED:EX_EDGE_GE),0);
    f.body.error=r->error;
    if(exec_error) fd=r->fd[EX_ERROR_W];
    if(fd>=0) (void)ex_write_frame(r,fd,&f,r->expiry,0);
}
static inline void ex_park(struct ex_context *r,int code) {
    struct timespec pause={0,INT64_C(1000000)};
    while(ex_gate(r,r->expiry,0)) {
        errno=0; if(nanosleep(&pause,NULL)) break;
    }
    _exit(code);
}
static inline int ex_u64(const char *text,uint64_t max,uint64_t *out) {
    char *end; unsigned long long v; const char *p;
    if(!text || !*text || (text[0]=='0' && text[1])) return 0;
    for(p=text;*p;p++) if(*p<'0' || *p>'9') return 0;
    errno=0; v=strtoull(text,&end,10);
    if(errno || *end || v>max) return 0; *out=(uint64_t)v; return 1;
}
static inline int ex_nonce(const char *s) {
    int k; if(strlen(s)!=64) return 0;
    for(k=0;k<64;k++) if(!((s[k]>='0' && s[k]<='9') || (s[k]>='a' && s[k]<='f'))) return 0;
    return 1;
}
static inline int ex_boot(const char *s) {
    int k; if(strlen(s)!=36) return 0;
    for(k=0;k<36;k++) {
        if(k==8 || k==13 || k==18 || k==23) { if(s[k]!='-') return 0; }
        else if(!((s[k]>='0' && s[k]<='9') || (s[k]>='a' && s[k]<='f'))) return 0;
    }
    return 1;
}
#endif
