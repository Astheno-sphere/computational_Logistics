/* Two fixed owned CPU adoption fixtures; G survival is assumed.
 * No exec, foreign PID, negative cleanup signal, production/model authority.
 */
#if !defined(__linux__) || !defined(_GNU_SOURCE)
#error "Declared Linux GNU environment required"
#endif
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <limits.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#if !defined(SYS_pidfd_open) || !defined(SYS_pidfd_send_signal)
#error "Declared symbolic pidfd headers required"
#endif
const long frontier_v8_header_pidfd_open = SYS_pidfd_open;
const unsigned int frontier_v8_target_int_bytes = __SIZEOF_INT__;
const unsigned int frontier_v8_target_long_bytes = __SIZEOF_LONG__;
const unsigned int frontier_v8_target_pointer_bytes = __SIZEOF_POINTER__;
const unsigned int frontier_v8_target_char_bits = __CHAR_BIT__;
const unsigned int frontier_v8_target_byte_order = __BYTE_ORDER__;
const long frontier_v8_header_pidfd_send_signal = SYS_pidfd_send_signal;
const long frontier_v8_header_pr_set_child_subreaper = PR_SET_CHILD_SUBREAPER;
const long frontier_v8_header_pr_get_child_subreaper = PR_GET_CHILD_SUBREAPER;
_Static_assert(sizeof(int) == 4 && INT_MAX == INT32_MAX, "signed32 int required");
_Static_assert(sizeof(pid_t) == 4 && (pid_t)-1 < 0, "signed32 pid required");
_Static_assert(sizeof(uid_t) == 4 && (uid_t)-1 > 0, "unsigned32 uid required");
_Static_assert(sizeof(uint64_t) == 8 && sizeof(int64_t) == 8 && CHAR_BIT == 8,
               "declared JSON integer representation required");
_Static_assert(sizeof(int) == __SIZEOF_INT__ && sizeof(long) == __SIZEOF_LONG__ &&
               sizeof(void *) == __SIZEOF_POINTER__, "compiler target differs");
_Static_assert(sizeof(dev_t) <= 8 && sizeof(ino_t) <= 8, "stat operands too wide");

#define NS INT64_C(1000000000)
#define MAGIC UINT32_C(0x4a455647)
#define MAX_ROWS 128
enum { G, C, H, W, ROLES };
enum { G_C, G_H, G_W, C_H, H_W, HANDLES };
enum { GC_R, GC_W, CR_R, CR_W, CH_R, CH_W, HR_R, HR_W, HW_R, HW_W, WR_R, WR_W, ENDS };
enum { READY, HANDLE, ARM, ACK, FD_CLOSE, EOF_FACT, ALL_ACK, EXIT23, EXIT_ACK,
       H_WAIT, FINISH, FINISH_ACK, HANDLE_CLOSE, CHILD_GET, TERMINAL_POLL, ERROR_FRAME };
enum { INITIAL, AFTER_ACK, TERMINAL };
enum { T_ID, T_READY, T_ARM, T_ALL_ACK, T_PRIMARY, T_C_EXIT, T_C_REAP, T_H_ADOPT,
       T_H_SIGNAL, T_C_H_EXIT, T_H_EXIT, T_H_REAP, T_W_ADOPT, T_W_PRE,
       T_W_SIGNAL, T_W_EXIT, T_W_REAP, T_C_FINISH, T_C_FINISH_ACK,
       T_TERMINAL, T_FINAL, TIMES };
static const char *role_names[] = { "guardian", "coordinator", "guard", "worker" };
static const char *handle_names[] = { "G_C", "G_H", "G_W", "C_H", "H_W" };
static const int handle_owners[] = { G, G, G, C, H };
static const int handle_targets[] = { C, H, W, H, W };
static const char *kind_names[] = { "ROLE_READY", "HANDLE_FACT", "ARM", "ROLE_ARM_ACK",
    "FD_CLOSE_FACT", "PIPE_EOF_FACT", "ALL_ARM_ACK", "COORDINATOR_EXIT23",
    "COORDINATOR_EXIT_ACK", "GUARD_WAIT_FACT", "COORDINATOR_FINISH",
    "COORDINATOR_FINISH_ACK", "HANDLE_CLOSE_FACT", "CHILD_SUBREAPER_GET",
    "TERMINAL_POLL_FACT", "ERROR_FACT" };
static const char *time_names[] = { "initial_identity", "all_ready", "arm_sent", "all_arm_ack",
    "primary_loss_command", "C_exit", "C_reaped", "H_adoption", "H_signal", "C_H_exit",
    "H_exit", "H_reaped", "W_adoption", "W_presignal", "W_signal", "W_exit",
    "W_reaped", "C_finish", "C_finish_ack", "terminal", "final" };
static const char *end_names[] = { "command_read", "command_write", "report_read", "report_write",
    "child_command_read", "child_command_write", "child_report_read", "child_report_write",
    "worker_command_read", "worker_command_write", "worker_report_read", "worker_report_write" };

struct fact { int attempted, result, err, has_value, value; };
struct product { uint64_t dev, ino, size; int64_t mtime_ns, ctime_ns; };
struct identity {
    int known, pid, ppid; uint32_t uid, euid; uint64_t start;
    char boot[37], state; struct product product;
};
struct poll_fact { int owner, target, fd, stage, attempts, result, revents, err; int64_t at; };
struct wait_fact { int owner, target, pid, attempted, attempts, result, status, err; int64_t at; };
struct handle_wire {
    int key, fd, fdi_pid, fdi_matches;
    struct fact open, flags; struct poll_fact live;
    struct identity before, after;
};
struct handle_fact { struct handle_wire w; int known, closed, kernel; struct fact close, badfd; };
struct close_fact { int owner, kind, fd, stage, result, err, bad_result, bad_err; };
struct close_wire { int key; struct fact close, badfd; };
struct eof_wire { struct identity id; struct poll_fact live; };
struct frame {
    uint32_t magic; int kind, role, aux, case_id, seq; int64_t t0; char nonce[65];
    union { struct identity id; struct handle_wire handle; struct close_fact close;
        struct close_wire handle_close; struct eof_wire eof; struct poll_fact poll;
        struct wait_fact wait; struct fact fact; int error; } body;
};
_Static_assert(sizeof(struct frame) <= 512 && sizeof(struct frame) <= PIPE_BUF,
               "private packet exceeds declared atomic bound");
struct packet_row { int kind, role, outgoing, aux; int64_t at; };
struct signal_fact {
    int attempts, consumed, result, err, negative_at_entry;
    int64_t at; struct identity presignal;
};
struct adoption { int known, target; struct identity id, guardian; int64_t at; };
struct report {
    int me, coord_loss, failed, error_role, error_no; const char *stage, *operation;
    int pf, pipebuf, endpoints[ENDS], original_stdio[3];
    struct stat stdio_stat[3];
    int out, in, seq, incoming_seq[ROLES];
    pid_t child; int own_handle;
    int created[ROLES], bound[ROLES], adopted[ROLES], terminal[ROLES], reaped[ROLES];
    struct product product; struct identity ids[ROLES], checks[2][ROLES];
    struct fact sub[5], child_sub[ROLES], sigpipe;
    struct handle_fact handles[HANDLES];
    struct poll_fact polls[6]; struct wait_fact waits[4];
    struct signal_fact signals[2]; struct adoption adoption[2];
    struct close_fact closes[MAX_ROWS]; int close_count;
    struct packet_row packets[MAX_ROWS]; int packet_count;
    int64_t t0, work, cleanup, terminal_end, total, expiry, last, times[TIMES], error_at;
    int reset_gate, ready_phase, initial_complete, arm_started, arm_phase;
    int terminal_command, terminal_ack_seen;
    char nonce[65];
};

static int64_t raw_now(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) || t.tv_sec < 0 ||
        t.tv_nsec < 0 || t.tv_nsec >= NS ||
        t.tv_sec > (INT64_MAX-t.tv_nsec)/NS) return -1;
    return (int64_t)t.tv_sec * NS + t.tv_nsec;
}
static void fail(struct report *r, const char *stage, const char *operation, int err)
{
    if (!r->failed) {
        r->failed = 1; r->stage = stage; r->operation = operation;
        r->error_role = r->me; r->error_no = err; r->error_at = raw_now();
    }
}
static int64_t now(struct report *r)
{
    int64_t n = raw_now();
    if (n < 0 || n < r->last) { fail(r, "clock", "clock_gettime", errno); return -1; }
    r->last = n; return n;
}
static int before(struct report *r, int64_t end)
{
    int64_t n = now(r);
    if (n < 0) return 0;
    if (n >= end) { fail(r, "deadline", "absolute_deadline", 0); return 0; }
    return 1;
}
static void mark(struct report *r, int which)
{ int64_t n = now(r); if (n >= 0) r->times[which] = n; }
static int read_text(const char *path, char *body, size_t cap)
{
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW); ssize_t n; size_t used = 0;
    if (fd < 0) return 0;
    while (used < cap) {
        n = read(fd, body + used, cap - used);
        if (n < 0) { int saved = errno; close(fd); errno = saved; return 0; }
        if (!n) break;
        used += (size_t)n;
    }
    if (close(fd) || used == cap || memchr(body, 0, used)) return 0;
    body[used] = 0; return 1;
}
static int product_fd_stat(int fd, struct product *out)
{
    struct stat s;
    if (fstat(fd, &s) || !S_ISREG(s.st_mode) || s.st_size <= 0 ||
        s.st_mtim.tv_sec < 0 || s.st_ctim.tv_sec < 0 ||
        s.st_mtim.tv_nsec < 0 || s.st_mtim.tv_nsec >= NS ||
        s.st_ctim.tv_nsec < 0 || s.st_ctim.tv_nsec >= NS ||
        s.st_mtim.tv_sec > (INT64_MAX-s.st_mtim.tv_nsec)/NS ||
        s.st_ctim.tv_sec > (INT64_MAX-s.st_ctim.tv_nsec)/NS) return 0;
    out->dev = (uint64_t)s.st_dev; out->ino = (uint64_t)s.st_ino; out->size = (uint64_t)s.st_size;
    out->mtime_ns = (int64_t)s.st_mtim.tv_sec * NS + s.st_mtim.tv_nsec;
    out->ctime_ns = (int64_t)s.st_ctim.tv_sec * NS + s.st_ctim.tv_nsec;
    return 1;
}
static int same_product(const struct product *a, const struct product *b)
{ return a->dev==b->dev && a->ino==b->ino && a->size==b->size &&
    a->mtime_ns==b->mtime_ns && a->ctime_ns==b->ctime_ns; }
static int capture(int pid, struct identity *out)
{
    char path[80], text[4097], boot[80], *end, *p; long long v; int field, fd;
    unsigned long long u, e; struct identity id = {0};
    snprintf(path, sizeof(path), "/proc/%d/stat", pid);
    if (!read_text(path, text, sizeof(text)-1)) return 0;
    errno = 0; v = strtoll(text, &end, 10);
    if (errno || v != pid || end == text || *end != ' ' || end[1] != '(') return 0;
    p = strrchr(end, ')');
    if (!p || p[1] != ' ' || !p[2] || p[3] != ' ') return 0;
    id.state = p[2]; p += 4;
    for (field=4; field<=22; field++) {
        errno=0; v=strtoll(p, &end, 10);
        if (errno || end==p) return 0;
        if (field==4) { if (v<=0 || v>INT32_MAX) return 0; id.ppid=(int)v; }
        if (field==22) { if (v<=0) return 0; id.start=(uint64_t)v; }
        p=end; while (*p==' ') p++;
    }
    snprintf(path,sizeof(path),"/proc/%d/status",pid);
    if (!read_text(path,text,sizeof(text)-1) || !(p=strstr(text,"\nUid:"))) return 0;
    p+=5; errno=0; u=strtoull(p,&end,10);
    if (errno || end==p || u>UINT32_MAX) return 0;
    p=end; errno=0; e=strtoull(p,&end,10);
    if (errno || end==p || e>UINT32_MAX) return 0;
    if (!read_text("/proc/sys/kernel/random/boot_id",boot,sizeof(boot)-1) ||
        strlen(boot)!=37 || boot[36]!='\n') return 0;
    boot[36]=0; memcpy(id.boot,boot,37);
    snprintf(path,sizeof(path),"/proc/%d/exe",pid);
    fd=open(path,O_RDONLY|O_CLOEXEC);
    if (fd<0) return 0;
    if (!product_fd_stat(fd,&id.product)) { int saved=errno; close(fd); errno=saved; return 0; }
    if (close(fd)) return 0;
    id.pid=pid; id.uid=(uint32_t)u; id.euid=(uint32_t)e; id.known=1; *out=id; return 1;
}
static int same_identity(const struct identity *a,const struct identity *b,int ignore_parent)
{
    return a->known && b->known && a->pid==b->pid && (ignore_parent || a->ppid==b->ppid) &&
        a->start==b->start && a->uid==b->uid && a->euid==b->euid &&
        !strcmp(a->boot,b->boot) && same_product(&a->product,&b->product);
}
static int alive(const struct identity *id)
{ return id->known && id->state!='Z' && id->state!='X' && id->state!='x'; }
static int fdinfo(int fd,int *pid)
{
    char path[80],text[4097],*p,*end; long v; int seen=0;
    snprintf(path,sizeof(path),"/proc/self/fdinfo/%d",fd);
    if (!read_text(path,text,sizeof(text)-1)) return 0;
    for (p=text; *p;) {
        char *line=strchr(p,'\n'); if (!line) return 0;
        if (!strncmp(p,"Pid:",4)) {
            if (++seen!=1) return 0;
            errno=0; v=strtol(p+4,&end,10);
            if (errno || end==p+4 || v<=0 || v>INT32_MAX) return 0;
            while (end<line && (*end==' ' || *end=='\t')) end++;
            if (end!=line) return 0; *pid=(int)v;
        }
        p=line+1;
    }
    return seen==1;
}
static int do_poll(struct report *r,struct poll_fact *out,int tag,int stage,int timeout)
{
    struct pollfd p; struct handle_fact *h=&r->handles[tag];
    out->owner=handle_owners[tag]; out->target=handle_targets[tag]; out->fd=h->w.fd; out->stage=stage;
    p.fd=h->w.fd; p.events=POLLIN; p.revents=0;
    out->attempts++; errno=0; out->result=poll(&p,1,timeout); out->err=errno;
    out->revents=p.revents; out->at=now(r);
    if (out->result<0 || (p.revents & (POLLERR|POLLNVAL))) {
        fail(r,"poll","poll",out->err); return 0;
    }
    return !r->failed;
}
static int open_handle(struct report *r,int tag,const struct identity *id)
{
    struct handle_fact *h=&r->handles[tag]; struct handle_wire *w=&h->w; long result;
    if (r->failed || !before(r,r->work)) return 0;
    w->key=tag; w->fd=-1; w->before=*id; w->open.attempted=1;
    errno=0; result=syscall((long)SYS_pidfd_open,(long)id->pid,(unsigned long)0);
    w->open.result=(result>=0 && result<=INT_MAX)?(int)result:-1; w->open.err=errno;
    if (result<0 || result>INT_MAX) { fail(r,"pidfd_open","syscall_pidfd_open",errno); return 0; }
    w->fd=(int)result; h->known=1;
    if (!fdinfo(w->fd,&w->fdi_pid) || w->fdi_pid!=id->pid ||
        !capture(id->pid,&w->after) || !same_identity(id,&w->after,0) || !alive(&w->after)) {
        fail(r,"pidfd_identity","fdinfo_capture",errno); return 0;
    }
    w->fdi_matches=1; w->flags.attempted=1;
    errno=0; w->flags.result=fcntl(w->fd,F_GETFD); w->flags.err=errno;
    if (w->flags.result<0 || !(w->flags.result&FD_CLOEXEC) ||
        !do_poll(r,&w->live,tag,INITIAL,0) || w->live.result || w->live.revents) {
        fail(r,"pidfd_live","fcntl_poll",errno); return 0;
    }
    return 1;
}
static int io_wait(struct report *r,int fd,short events,int64_t end)
{
    struct pollfd p={fd,events,0}; int64_t n; int ms,rc;
    if (!before(r,end)) return 0;
    n=r->last; ms=(int)((end-n+999999)/1000000); if (ms>20) ms=20;
    errno=0; rc=poll(&p,1,ms);
    if (rc<0 || (p.revents & (POLLERR|POLLNVAL))) { fail(r,"private_pipe","poll",errno); return 0; }
    return 1;
}
static struct frame frame(struct report *r,int kind,int aux)
{
    struct frame f; memset(&f,0,sizeof(f));
    f.magic=MAGIC; f.kind=kind; f.role=r->me; f.aux=aux; f.case_id=r->coord_loss;
    f.t0=r->t0; memcpy(f.nonce,r->nonce,65); f.seq=++r->seq; return f;
}
static int write_frame(struct report *r,int fd,const struct frame *f,int64_t end)
{
    ssize_t n;
    for (;;) {
        if (!before(r,end)) return 0;
        errno=0; n=write(fd,f,sizeof(*f));
        if (n==(ssize_t)sizeof(*f)) return 1;
        if (n<0 && errno==EAGAIN) { if (!io_wait(r,fd,POLLOUT,end)) return 0; continue; }
        fail(r,"private_pipe","write",errno); return 0;
    }
}
static int read_frame(struct report *r,int fd,struct frame *f,int64_t end,int allow_eof)
{
    ssize_t n;
    for (;;) {
        if (!before(r,end)) return -1;
        errno=0; n=read(fd,f,sizeof(*f));
        if (!n) { if (allow_eof) return 0; fail(r,"private_pipe","unexpected_eof",0); return -1; }
        if (n<0 && errno==EAGAIN) { if (!io_wait(r,fd,POLLIN,end)) return -1; continue; }
        if (n!=(ssize_t)sizeof(*f) || f->magic!=MAGIC || f->kind<READY || f->kind>ERROR_FRAME ||
            f->role<0 || f->role>=ROLES || f->case_id!=r->coord_loss ||
            f->t0!=r->t0 || memcmp(f->nonce,r->nonce,65)) {
            fail(r,"private_packet","frame_binding",errno); return -1;
        }
        return 1;
    }
}
static int send_up(struct report *r,struct frame *f,int64_t end)
{ return write_frame(r,r->out,f,end); }
static void packet_record(struct report *r,const struct frame *f,int outgoing)
{
    struct packet_row *p;
    if (r->packet_count>=MAX_ROWS) { fail(r,"packet_capacity","ledger",0); return; }
    p=&r->packets[r->packet_count++]; p->kind=f->kind; p->role=f->role;
    p->aux=f->aux; p->outgoing=outgoing; p->at=now(r);
}
static int close_raw(struct report *r,int fd,int kind,int stage,int report_up)
{
    struct close_fact c; struct frame f;
    if (fd<0) return 1;
    memset(&c,0,sizeof(c)); c.owner=r->me; c.kind=kind; c.fd=fd; c.stage=stage;
    errno=0; c.result=close(fd); c.err=errno;
    errno=0; c.bad_result=fcntl(fd,F_GETFD); c.bad_err=errno;
    if (r->me==G) {
        if (r->close_count<MAX_ROWS) r->closes[r->close_count++]=c;
        else fail(r,"close_capacity","ledger",0);
    } else if (report_up) { f=frame(r,FD_CLOSE,0); f.body.close=c; (void)send_up(r,&f,r->expiry); }
    if (c.result || c.bad_result!=-1 || c.bad_err!=EBADF) {
        fail(r,"close","close_f_getfd",c.err); return 0;
    }
    return 1;
}
static void close_end(struct report *r,int n,int stage,int report_up)
{
    int fd=r->endpoints[n]; r->endpoints[n]=-1;
    (void)close_raw(r,fd,n,stage,report_up);
}
static int close_handle(struct report *r,int tag,int report_up)
{
    struct handle_fact *h=&r->handles[tag]; struct frame f;
    if (!h->known || h->closed) return 1;
    h->closed=1; h->close.attempted=1; errno=0;
    h->close.result=close(h->w.fd); h->close.err=errno;
    h->badfd.attempted=1; errno=0;
    h->badfd.result=fcntl(h->w.fd,F_GETFD); h->badfd.err=errno;
    if (report_up) {
        f=frame(r,HANDLE_CLOSE,tag); f.body.handle_close.key=tag;
        f.body.handle_close.close=h->close; f.body.handle_close.badfd=h->badfd;
        (void)send_up(r,&f,r->expiry);
    }
    if (h->close.result || h->badfd.result!=-1 || h->badfd.err!=EBADF) {
        fail(r,"close","pidfd_close_f_getfd",h->close.err); return 0;
    }
    return 1;
}
static int keep_end(int role,int n)
{
    return (role==G && (n==GC_W || n==CR_R)) ||
        (role==C && (n==GC_R || n==CR_W || n==CH_W || n==HR_R)) ||
        (role==H && (n==CH_R || n==HR_W || n==HW_W || n==WR_R)) ||
        (role==W && (n==HW_R || n==WR_W));
}
static void close_inherited(struct report *r)
{
    int n;
    for (n=0;n<ENDS;n++) if (!keep_end(r->me,n)) close_end(r,n,INITIAL,r->me!=G);
    if (r->me!=G) {
        int pf=r->pf; r->pf=-1; (void)close_raw(r,pf,ENDS,INITIAL,1);
        for (n=0;n<3;n++) if (r->original_stdio[n]) {
            struct stat s; int protected=0,k;
            for (k=0;k<ENDS;k++) if (r->endpoints[k]==n) protected=1;
            if (r->own_handle>=0 && r->handles[r->own_handle].known &&
                r->handles[r->own_handle].w.fd==n) protected=1;
            if (!protected && !fstat(n,&s) && s.st_dev==r->stdio_stat[n].st_dev &&
                s.st_ino==r->stdio_stat[n].st_ino && s.st_mode==r->stdio_stat[n].st_mode)
                (void)close_raw(r,n,ENDS+1+n,INITIAL,1);
        }
    }
}
static int get_sub(struct report *r,struct fact *f,int expected)
{
    int value=-1; f->attempted=1; errno=0;
    f->result=prctl(PR_GET_CHILD_SUBREAPER,&value,0L,0L,0L); f->err=errno;
    if (!f->result) { f->has_value=1; f->value=value; }
    if (f->result || value!=expected) { fail(r,"subreaper","prctl_get",f->err); return 0; }
    return 1;
}
static int set_sub(struct report *r,struct fact *f,int value,const char *operation)
{
    f->attempted=1; errno=0; f->result=prctl(PR_SET_CHILD_SUBREAPER,(long)value,0L,0L,0L); f->err=errno;
    if (f->result) { fail(r,value?"subreaper":"terminal_reset",operation,f->err); return 0; }
    return 1;
}
static int accept_frame(struct report *r,const struct frame *f)
{
    int role=f->role;
    if (role<=r->me || f->seq<=r->incoming_seq[role]) {
        fail(r,"private_packet","origin_sequence",0); return 0;
    }
    r->incoming_seq[role]=f->seq;
    switch (f->kind) {
    case READY:
        if (r->arm_started || f->aux || role!=W-r->ready_phase ||
            r->ready_phase>=ROLES-r->me-1 || !f->body.id.known || !alive(&f->body.id) ||
            !same_product(&f->body.id.product,&r->product)) {
            fail(r,"private_packet","ready_identity",0); return 0;
        }
        if (r->ids[role].known && !same_identity(&r->ids[role],&f->body.id,0)) {
            fail(r,"private_packet","ready_identity_drift",0); return 0;
        }
        r->ids[role]=f->body.id; r->created[role]=1; r->ready_phase++; break;
    case HANDLE:
        if ((role!=C || f->aux!=C_H) && (role!=H || f->aux!=H_W)) {
            fail(r,"private_packet","handle_owner",0); return 0;
        }
        if (r->arm_started || r->handles[f->aux].known ||
            f->body.handle.key!=f->aux || f->body.handle.fd<0) {
            fail(r,"private_packet","handle_key",0); return 0;
        }
        r->handles[f->aux].w=f->body.handle; r->handles[f->aux].known=1;
        r->created[handle_targets[f->aux]]=1; break;
    case FD_CLOSE:
        if (f->body.close.owner!=role || r->close_count>=MAX_ROWS) {
            fail(r,"private_packet","close_owner_capacity",0); return 0;
        }
        r->closes[r->close_count++]=f->body.close;
        if (f->body.close.result || f->body.close.bad_result!=-1 ||
            f->body.close.bad_err!=EBADF) fail(r,"close","child_close",f->body.close.err);
        break;
    case HANDLE_CLOSE:
        if (f->aux<0 || f->aux>=HANDLES || handle_owners[f->aux]!=role ||
            !r->handles[f->aux].known || r->handles[f->aux].closed ||
            f->body.handle_close.key!=f->aux || !f->body.handle_close.close.attempted ||
            !f->body.handle_close.badfd.attempted) {
            fail(r,"private_packet","handle_close_owner",0); return 0;
        }
        r->handles[f->aux].close=f->body.handle_close.close;
        r->handles[f->aux].badfd=f->body.handle_close.badfd;
        r->handles[f->aux].closed=1;
        if (r->handles[f->aux].close.result || r->handles[f->aux].badfd.result!=-1 ||
            r->handles[f->aux].badfd.err!=EBADF)
            fail(r,"close","child_pidfd_close",r->handles[f->aux].close.err);
        break;
    case CHILD_GET:
        if (r->arm_started || f->aux || r->child_sub[role].attempted) {
            fail(r,"private_packet","child_get_phase",0); return 0;
        }
        r->child_sub[role]=f->body.fact;
        if (!f->body.fact.attempted || f->body.fact.result || f->body.fact.err ||
            !f->body.fact.has_value || f->body.fact.value!=0)
            fail(r,"subreaper","child_get",f->body.fact.err);
        break;
    case EOF_FACT:
        if ((role!=H || f->aux!=W) && (role!=C || f->aux!=H)) {
            fail(r,"private_packet","eof_owner",0); return 0;
        }
        if (!r->arm_started || r->ready_phase!=ROLES-r->me-1 ||
            r->arm_phase!=(f->aux==W?1:3) ||
            !r->handles[f->aux==W?H_W:C_H].known ||
            !f->body.eof.id.known || !alive(&f->body.eof.id) ||
            !same_identity(&r->ids[f->aux],&f->body.eof.id,0) ||
            f->body.eof.live.owner!=role || f->body.eof.live.target!=f->aux ||
            f->body.eof.live.fd!=r->handles[f->aux==W?H_W:C_H].w.fd ||
            f->body.eof.live.stage!=AFTER_ACK || f->body.eof.live.at<r->t0 ||
            f->body.eof.live.at>=r->work ||
            f->body.eof.live.result || f->body.eof.live.revents ||
            f->body.eof.live.err || !f->body.eof.live.attempts) {
            fail(r,"private_packet","eof_child_live",0); return 0;
        }
        r->polls[f->aux==W?4:5]=f->body.eof.live; r->arm_phase++; break;
    case TERMINAL_POLL:
        if (r->me!=G || r->coord_loss || r->arm_phase!=6 || role!=C || f->aux!=C_H ||
            r->polls[C_H].attempts || r->signals[0].attempts!=1 || r->signals[0].result) {
            fail(r,"private_packet","terminal_poll_owner",0); return 0;
        }
        if (f->body.poll.owner!=C || f->body.poll.target!=H ||
            f->body.poll.fd!=r->handles[C_H].w.fd || f->body.poll.stage!=TERMINAL ||
            f->body.poll.attempts<=0 || f->body.poll.result!=1 || f->body.poll.err ||
            !(f->body.poll.revents&POLLIN) || (f->body.poll.revents&(POLLERR|POLLNVAL)) ||
            f->body.poll.at<r->signals[0].at || f->body.poll.at>=r->cleanup) {
            fail(r,"private_packet","terminal_poll_fact",0); return 0;
        }
        r->polls[C_H]=f->body.poll; r->times[T_C_H_EXIT]=f->body.poll.at; break;
    case H_WAIT:
        if (r->me!=G || r->coord_loss || r->arm_phase!=6 || role!=C || f->aux ||
            !r->polls[C_H].attempts || r->waits[C_H].attempted ||
            f->body.wait.owner!=C || f->body.wait.target!=H) {
            fail(r,"private_packet","wait_owner",0); return 0;
        }
        r->waits[C_H]=f->body.wait; r->times[T_H_REAP]=f->body.wait.at;
        if (!f->body.wait.attempted || f->body.wait.attempts<=0 ||
            f->body.wait.pid!=r->ids[H].pid || f->body.wait.result!=r->ids[H].pid ||
            f->body.wait.err || f->body.wait.at<r->polls[C_H].at ||
            f->body.wait.at>=r->cleanup ||
            !WIFSIGNALED(f->body.wait.status) || WTERMSIG(f->body.wait.status)!=SIGKILL)
            fail(r,"parent_wait","guard_status",f->body.wait.err);
        else { r->terminal[H]=1; r->reaped[H]=1; r->handles[H_W].kernel=1; }
        break;
    case ERROR_FRAME: fail(r,"child_error","reported_error",f->body.error); break;
    case ACK:
        if (!r->arm_started || f->aux || r->ready_phase!=ROLES-r->me-1 ||
            r->arm_phase<0 || r->arm_phase>4 || (r->arm_phase%2) ||
            role!=W-r->arm_phase/2) {
            fail(r,"private_packet","ack_phase",0); return 0;
        }
        r->arm_phase++; break;
    case ALL_ACK:
        if (r->me!=G || role!=C || f->aux || !r->arm_started ||
            r->ready_phase!=3 || r->arm_phase!=5) {
            fail(r,"private_packet","all_ack_phase",0); return 0;
        }
        r->arm_phase=6; break;
    case EXIT_ACK: case FINISH_ACK:
        if (r->me!=G || role!=C || f->aux || r->arm_phase!=6 ||
            r->terminal_ack_seen ||
            (f->kind==EXIT_ACK && (!r->coord_loss || r->terminal_command!=EXIT23)) ||
            (f->kind==FINISH_ACK && (r->coord_loss || r->terminal_command!=FINISH))) {
            fail(r,"private_packet","terminal_ack_phase",0); return 0;
        }
        r->terminal_ack_seen=1; break;
    default: fail(r,"private_packet","unexpected_kind",0); break;
    }
    if (r->me==G && (!r->failed || f->kind==ERROR_FRAME)) packet_record(r,f,0);
    return !r->failed;
}
static int relay_until(struct report *r,int readfd,int kind,int role,int64_t end)
{
    struct frame f;
    while (!r->failed) {
        if (read_frame(r,readfd,&f,end,0)!=1 || !accept_frame(r,&f) ||
            !send_up(r,&f,end)) return 0;
        if (f.kind==kind && f.role==role) return 1;
    }
    return 0;
}
static int command_read(struct report *r,int expected,int64_t end,struct frame *out)
{
    if (r->failed || read_frame(r,r->in,out,end,0)!=1) return 0;
    if (out->kind!=expected || out->role!=G || out->seq<=r->incoming_seq[G]) {
        fail(r,"private_command","closed_command",0); return 0;
    }
    if (out->aux || (expected==ARM && (r->arm_started || r->arm_phase ||
            r->ready_phase!=ROLES-r->me-1)) ||
        (expected!=ARM && (r->me!=C || r->arm_phase!=6 || r->terminal_command ||
            (expected==EXIT23 && !r->coord_loss) || (expected==FINISH && r->coord_loss)))) {
        fail(r,"private_command","command_phase",0); return 0;
    }
    if (expected==ARM) r->arm_started=1;
    else r->terminal_command=expected;
    r->incoming_seq[G]=out->seq; return 1;
}
static int command_send(struct report *r,int kind,int64_t end)
{
    struct frame f;
    if (r->failed || !before(r,end)) return 0;
    if ((kind==ARM && (!r->initial_complete || r->ready_phase!=3 || r->arm_started || r->arm_phase)) ||
        (kind!=ARM && (!r->initial_complete || !r->arm_started || r->arm_phase!=6 ||
            r->terminal_command || (kind==EXIT23 && !r->coord_loss) ||
            (kind==FINISH && r->coord_loss)))) {
        fail(r,"private_command","send_phase",0); return 0;
    }
    f=frame(r,kind,0);
    if (!write_frame(r,r->endpoints[GC_W],&f,end)) return 0;
    if (kind==ARM) r->arm_started=1;
    else r->terminal_command=kind;
    packet_record(r,&f,1); return !r->failed;
}
static int receive_until(struct report *r,int kind,int role,int64_t end)
{
    struct frame f;
    while (!r->failed) {
        if (read_frame(r,r->endpoints[CR_R],&f,end,0)!=1 || !accept_frame(r,&f)) return 0;
        if (f.kind==kind && f.role==role) return 1;
    }
    return 0;
}
static int terminal_poll(struct report *r,int tag,int slot,int64_t end)
{
    struct poll_fact *p=&r->polls[slot];
    while (!r->failed && before(r,end)) {
        if (!do_poll(r,p,tag,TERMINAL,10)) return 0;
        if (p->result && (p->revents&POLLIN)) return 1;
    }
    return 0;
}
static int wait_role(struct report *r,int tag,int slot,int64_t end)
{
    struct wait_fact *w=&r->waits[slot]; int status; pid_t result;
    int target=handle_targets[tag];
    w->owner=r->me; w->target=target; w->pid=r->ids[target].pid;
    while (!r->failed && before(r,end)) {
        w->attempted=1; w->attempts++; errno=0; result=waitpid((pid_t)w->pid,&status,WNOHANG);
        w->result=(int)result; w->err=errno; w->at=now(r);
        if (result<0) { fail(r,"parent_wait","waitpid",w->err); return 0; }
        if (result==w->pid) {
            w->status=status; r->terminal[target]=1; r->reaped[target]=1; return 1;
        }
        if (!io_wait(r,r->handles[tag].w.fd,POLLIN,end)) return 0;
    }
    return 0;
}
static int expected_kill_wait(struct report *r,int slot)
{
    struct wait_fact *w=&r->waits[slot];
    if (!w->attempted || w->result!=w->pid || !WIFSIGNALED(w->status) ||
        WTERMSIG(w->status)!=SIGKILL) {
        fail(r,"parent_wait","signal_status",w->err); return 0;
    }
    return 1;
}
static int eof_live(struct report *r,int child_read,int tag,int slot,int target)
{
    struct frame f; struct identity id;
    if (!r->arm_started || r->ready_phase!=ROLES-r->me-1 ||
        r->arm_phase!=(target==W?1:3)) {
        fail(r,"private_pipe","local_eof_phase",0); return 0;
    }
    if (read_frame(r,child_read,&f,r->work,1)!=0) {
        fail(r,"private_pipe","missing_ack_eof",0); return 0;
    }
    if (!do_poll(r,&r->polls[slot],tag,AFTER_ACK,0) ||
        r->polls[slot].result || r->polls[slot].revents ||
        !capture(r->ids[target].pid,&id) || !alive(&id) ||
        !same_identity(&r->ids[target],&id,0)) {
        fail(r,"private_pipe","eof_child_live",0); return 0;
    }
    f=frame(r,EOF_FACT,target); f.body.eof.id=id; f.body.eof.live=r->polls[slot];
    if (!send_up(r,&f,r->work)) return 0;
    r->arm_phase++; return 1;
}
static void park(struct report *r)
{
    while (!r->failed && before(r,r->expiry)) {
        if (poll(NULL,0,10)<0) { fail(r,"expiry","poll",errno); break; }
    }
}
static void child_failure(struct report *r)
{
    int n; struct frame f=frame(r,ERROR_FRAME,0);
    f.body.error=r->error_no; (void)send_up(r,&f,r->expiry);
    if (r->own_handle>=0) (void)close_handle(r,r->own_handle,1);
    for (n=0;n<ENDS;n++) if (r->endpoints[n]>=0) close_end(r,n,TERMINAL,0);
    if (r->pf>=0) { int fd=r->pf; r->pf=-1; (void)close_raw(r,fd,ENDS,TERMINAL,0); }
    _exit(40+r->me);
}
static void child_role(struct report *r,int role)
{
    struct frame f; pid_t pid; int childrole=role+1;
    r->me=role; r->seq=0; memset(r->incoming_seq,0,sizeof(r->incoming_seq));
    r->ready_phase=0; r->initial_complete=0; r->arm_started=0; r->arm_phase=0;
    r->terminal_command=0; r->terminal_ack_seen=0;
    r->own_handle=role==C?C_H:role==H?H_W:-1;
    r->out=r->endpoints[role==C?CR_W:role==H?HR_W:WR_W];
    r->in=r->endpoints[role==C?GC_R:role==H?CH_R:HW_R];
    if (!get_sub(r,&r->child_sub[role],0) ||
        !capture((int)getpid(),&r->ids[role]) ||
        !same_product(&r->ids[role].product,&r->product) ||
        r->ids[role].uid!=r->ids[G].uid || r->ids[role].euid!=r->ids[G].euid)
        fail(r,"child_identity","initial_capture",errno);
    if (!r->failed && role!=W) {
        if (!before(r,r->work)) child_failure(r);
        errno=0; pid=fork();
        if (pid<0) fail(r,"fork","fork",errno);
        else if (!pid) child_role(r,childrole);
        else {
            r->child=pid;
            if (!capture((int)pid,&r->ids[childrole]) ||
                r->ids[childrole].ppid!=r->ids[role].pid ||
                !open_handle(r,r->own_handle,&r->ids[childrole]))
                fail(r,"child_anchor","capture_open",errno);
        }
    }
    close_inherited(r);
    if (r->failed) child_failure(r);
    f=frame(r,CHILD_GET,0); f.body.fact=r->child_sub[role];
    if (!send_up(r,&f,r->work)) child_failure(r);
    if (role!=W) {
        f=frame(r,HANDLE,r->own_handle); f.body.handle=r->handles[r->own_handle].w;
        if (!send_up(r,&f,r->work) ||
            !relay_until(r,r->endpoints[role==C?HR_R:WR_R],READY,childrole,r->work))
            child_failure(r);
    }
    f=frame(r,READY,0); f.body.id=r->ids[role];
    if (!send_up(r,&f,r->work) || !command_read(r,ARM,r->work,&f)) child_failure(r);
    if (role!=W) {
        if (!write_frame(r,r->endpoints[role==C?CH_W:HW_W],&f,r->work) ||
            !relay_until(r,r->endpoints[role==C?HR_R:WR_R],ACK,childrole,r->work) ||
            !eof_live(r,r->endpoints[role==C?HR_R:WR_R],r->own_handle,
                      role==C?5:4,childrole)) child_failure(r);
        close_end(r,role==C?CH_W:HW_W,AFTER_ACK,1);
        close_end(r,role==C?HR_R:WR_R,AFTER_ACK,1);
    }
    if (role!=C) close_end(r,role==H?CH_R:HW_R,AFTER_ACK,1);
    if (r->failed) child_failure(r);
    if (!r->arm_started || r->arm_phase!=(role==C?4:role==H?2:0)) {
        fail(r,"private_packet","local_ack_phase",0); child_failure(r);
    }
    f=frame(r,ACK,0); if (!send_up(r,&f,r->work)) child_failure(r);
    r->arm_phase++;
    if (role!=C) {
        close_end(r,role==H?HR_W:WR_W,AFTER_ACK,0);
        if (r->failed) child_failure(r);
        park(r); child_failure(r);
    }
    f=frame(r,ALL_ACK,0); if (!send_up(r,&f,r->work)) child_failure(r);
    r->arm_phase=6;
    if (r->coord_loss) {
        if (!command_read(r,EXIT23,r->work,&f) || !close_handle(r,C_H,1)) child_failure(r);
        f=frame(r,EXIT_ACK,0); if (!send_up(r,&f,r->work)) child_failure(r);
        close_end(r,GC_R,TERMINAL,0); close_end(r,CR_W,TERMINAL,0);
        _exit(r->failed?41:23);
    }
    if (!terminal_poll(r,C_H,C_H,r->cleanup) || !wait_role(r,C_H,C_H,r->cleanup) ||
        !expected_kill_wait(r,C_H)) child_failure(r);
    f=frame(r,TERMINAL_POLL,C_H); f.body.poll=r->polls[C_H];
    if (!send_up(r,&f,r->cleanup)) child_failure(r);
    f=frame(r,H_WAIT,0); f.body.wait=r->waits[C_H];
    if (!send_up(r,&f,r->cleanup) || !command_read(r,FINISH,r->terminal_end,&f) ||
        !close_handle(r,C_H,1)) child_failure(r);
    f=frame(r,FINISH_ACK,0); if (!send_up(r,&f,r->terminal_end)) child_failure(r);
    close_end(r,GC_R,TERMINAL,0); close_end(r,CR_W,TERMINAL,0);
    _exit(r->failed?41:0);
}
static int valid_initial_handle(struct report *r,int tag)
{
    struct handle_fact *h=&r->handles[tag]; struct handle_wire *w=&h->w;
    struct identity *id=&r->ids[handle_targets[tag]]; struct poll_fact *p=&w->live;
    return h->known && !h->closed && w->key==tag && w->fd>=0 &&
        w->open.attempted && w->open.result==w->fd && !w->open.err &&
        same_identity(id,&w->before,0) && same_identity(id,&w->after,0) &&
        alive(&w->before) && alive(&w->after) && w->fdi_matches && w->fdi_pid==id->pid &&
        w->flags.attempted && w->flags.result>=0 && (w->flags.result&FD_CLOEXEC) && !w->flags.err &&
        p->owner==handle_owners[tag] && p->target==handle_targets[tag] && p->fd==w->fd &&
        p->stage==INITIAL && p->attempts>0 && !p->result && !p->revents && !p->err &&
        p->at>=r->t0 && p->at<r->work;
}
static int validate_initial(struct report *r)
{
    int role,tag; struct identity fresh;
    if (r->failed || r->me!=G || r->ready_phase!=3 || r->arm_started || r->arm_phase ||
        !r->sub[0].attempted || r->sub[0].result || r->sub[0].err ||
        !r->sub[0].has_value || r->sub[0].value ||
        !r->sub[1].attempted || r->sub[1].result || r->sub[1].err ||
        !r->sub[2].attempted || r->sub[2].result || r->sub[2].err ||
        !r->sub[2].has_value || r->sub[2].value!=1) {
        fail(r,"identity","initial_gate_phase",0); return 0;
    }
    for (role=G;role<ROLES;role++) {
        if (!r->ids[role].known || !capture(r->ids[role].pid,&fresh) ||
            !same_identity(&r->ids[role],&fresh,0) || !alive(&fresh) ||
            !same_product(&fresh.product,&r->product) ||
            fresh.uid!=r->ids[G].uid || fresh.euid!=r->ids[G].euid ||
            (role>G && fresh.ppid!=r->ids[role-1].pid)) {
            fail(r,"identity","initial_chain",errno); return 0;
        }
        if (role>G) r->bound[role]=1;
    }
    for (role=C;role<ROLES;role++) if (!r->child_sub[role].attempted ||
        r->child_sub[role].result || r->child_sub[role].err ||
        !r->child_sub[role].has_value || r->child_sub[role].value) {
        fail(r,"identity","missing_initial_child_get",0); return 0;
    }
    for (role=G_H;role<=G_W;role++)
        if (!open_handle(r,role,&r->ids[handle_targets[role]])) return 0;
    for (tag=G_C;tag<HANDLES;tag++) if (!valid_initial_handle(r,tag)) {
        fail(r,"identity","missing_initial_handle",0); return 0;
    }
    r->initial_complete=1;
    return 1;
}
static int all_live(struct report *r)
{
    int role,tag; struct identity id; struct poll_fact p;
    if (r->failed || !r->initial_complete || r->ready_phase!=3 ||
        !r->arm_started || r->arm_phase!=6 || !r->polls[4].attempts || !r->polls[5].attempts) {
        fail(r,"identity","armed_chain_incomplete",0); return 0;
    }
    if (r->failed || !before(r,r->work)) return 0;
    for (role=G;role<ROLES;role++)
        if (!capture(r->ids[role].pid,&id) || !alive(&id) ||
            !same_identity(&r->ids[role],&id,0)) {
            fail(r,"identity","pre_action_chain",errno); return 0;
        }
    for (tag=G_C;tag<=G_W;tag++) {
        memset(&p,0,sizeof(p));
        if (!do_poll(r,&p,tag,INITIAL,0) || p.result || p.revents) {
            fail(r,"identity","pre_action_live",p.err); return 0;
        }
    }
    return 1;
}
static int observe_adoption(struct report *r,int target,int which,int64_t end)
{
    struct identity id,g; int64_t at;
    while (!r->failed && before(r,end)) {
        if (!capture(r->ids[G].pid,&g) || !same_identity(&r->ids[G],&g,0) ||
            !capture(r->ids[target].pid,&id) || !same_identity(&r->ids[target],&id,1) ||
            !alive(&id)) { fail(r,"adoption","same_identity",errno); return 0; }
        if (id.ppid==r->ids[G].pid) {
            at=now(r); if (at<0 || r->failed) return 0;
            if (at>=end) { fail(r,"deadline","absolute_deadline",0); return 0; }
            r->adoption[which].known=1; r->adoption[which].target=target;
            r->adoption[which].id=id; r->adoption[which].guardian=g;
            r->adoption[which].at=at; r->adopted[target]=1;
            r->times[target==H?T_H_ADOPT:T_W_ADOPT]=r->adoption[which].at;
            return !r->failed;
        }
        if (id.ppid!=r->ids[target].ppid) { fail(r,"adoption","unexpected_parent",0); return 0; }
        if (poll(NULL,0,1)<0) { fail(r,"adoption","poll",errno); return 0; }
    }
    return 0;
}
static int snapshot(struct report *r,int which)
{
    int role; struct identity id; struct poll_fact p;
    if (r->failed || !before(r,r->cleanup)) return 0;
    memset(r->checks[which],0,sizeof(r->checks[which]));
    for (role=G;role<ROLES;role++) {
        int parent;
        if ((role==C && r->coord_loss) || (role==H && which==1)) continue;
        parent=r->ids[role].ppid;
        if (role==H && r->coord_loss) parent=r->ids[G].pid;
        if (role==W && which==1) parent=r->ids[G].pid;
        if (!capture(r->ids[role].pid,&id) || !alive(&id) ||
            !same_identity(&r->ids[role],&id,1) || id.ppid!=parent) {
            fail(r,"identity","presignal_snapshot",errno); return 0;
        }
        r->checks[which][role]=id;
        if (role>G) {
            memset(&p,0,sizeof(p));
            if (!do_poll(r,&p,role==C?G_C:role==H?G_H:G_W,INITIAL,0) ||
                p.result || p.revents) { fail(r,"identity","presignal_live",p.err); return 0; }
        }
    }
    return 1;
}
static int planned_signal(struct report *r,int which)
{
    int tag=which?G_W:G_H; int64_t at,end=(!which && !r->coord_loss)?r->work:r->cleanup;
    struct signal_fact *s=&r->signals[which];
    if (r->failed || !r->initial_complete || r->ready_phase!=3 ||
        !r->arm_started || r->arm_phase!=6 || s->consumed || !before(r,end) ||
        !r->checks[which][handle_targets[tag]].known ||
        (which && !r->adopted[W]) || (!which && r->coord_loss && !r->adopted[H])) return 0;
    at=now(r); if (at<0 || r->failed) return 0;
    if (at>=end) { fail(r,"deadline","absolute_deadline",0); return 0; }
    s->negative_at_entry=0; s->consumed=1; s->attempts=1;
    s->presignal=r->checks[which][handle_targets[tag]]; s->at=at;
    errno=0; s->result=(int)syscall((long)SYS_pidfd_send_signal,(long)r->handles[tag].w.fd,
                                  (long)SIGKILL,(void *)NULL,(unsigned long)0);
    s->err=errno; r->times[which?T_W_SIGNAL:T_H_SIGNAL]=s->at;
    if (s->result) { fail(r,which?"w_signal":"h_signal","syscall_pidfd_send_signal",s->err); return 0; }
    return 1;
}
static int reset_terminal(struct report *r)
{
    int value=-1,tag,n;
    if (r->failed || !r->initial_complete || r->ready_phase!=3 ||
        !r->arm_started || r->arm_phase!=6 || !r->terminal_ack_seen ||
        r->terminal_command!=(r->coord_loss?EXIT23:FINISH) ||
        !r->reaped[C] || !r->reaped[H] || !r->reaped[W] ||
        !r->adopted[W] || (r->coord_loss && !r->adopted[H])) return 0;
    for (tag=G_C;tag<=G_W;tag++) if (!close_handle(r,tag,0)) return 0;
    if (!r->handles[C_H].closed || r->handles[C_H].close.result ||
        r->handles[C_H].badfd.result!=-1 || r->handles[C_H].badfd.err!=EBADF) {
        fail(r,"close","coordinator_handle_missing",0); return 0;
    }
    for (n=0;n<ENDS;n++) if (r->endpoints[n]>=0) {
        close_end(r,n,TERMINAL,0); if (r->failed) return 0;
    }
    if (r->pf>=0) {
        int fd=r->pf; r->pf=-1;
        if (!close_raw(r,fd,ENDS,TERMINAL,0)) return 0;
    }
    /* G retains stdout solely for final JSON. Close its captured stdin/stderr
     * only after confirming their original identities, never a reused fd. */
    for (n=0;n<3;n+=2) if (r->original_stdio[n]) {
        struct stat s;
        if (fstat(n,&s) || s.st_dev!=r->stdio_stat[n].st_dev ||
            s.st_ino!=r->stdio_stat[n].st_ino || s.st_mode!=r->stdio_stat[n].st_mode) {
            fail(r,"identity","guardian_terminal_stdio",errno); return 0;
        }
        r->original_stdio[n]=0;
        if (!close_raw(r,n,ENDS+1+n,TERMINAL,0)) return 0;
    }
    if (!before(r,r->terminal_end)) return 0;
    mark(r,T_TERMINAL);
    if (r->failed || r->times[T_TERMINAL]<=0 || r->times[T_TERMINAL]>=r->terminal_end) {
        if (!r->failed) fail(r,"deadline","absolute_deadline",0);
        return 0;
    }
    r->reset_gate=1;
    if (!set_sub(r,&r->sub[3],0,"prctl_set_disabled")) return 0;
    r->sub[4].attempted=1; errno=0;
    r->sub[4].result=prctl(PR_GET_CHILD_SUBREAPER,&value,0L,0L,0L); r->sub[4].err=errno;
    if (!r->sub[4].result) { r->sub[4].has_value=1; r->sub[4].value=value; }
    if (r->sub[4].result || value!=0) {
        fail(r,"terminal_reset","prctl_get_disabled",r->sub[4].err); return 0;
    }
    return 1;
}
static void guardian_case(struct report *r)
{
    if (!receive_until(r,READY,C,r->work) || !validate_initial(r)) return;
    mark(r,T_READY);
    mark(r,T_ARM); if (!command_send(r,ARM,r->work) ||
        !receive_until(r,ALL_ACK,C,r->work) || !all_live(r)) return;
    mark(r,T_ALL_ACK); mark(r,T_PRIMARY);
    if (r->coord_loss) {
        if (!command_send(r,EXIT23,r->work) || !receive_until(r,EXIT_ACK,C,r->work) ||
            !terminal_poll(r,G_C,G_C,r->work)) return;
        r->times[T_C_EXIT]=r->polls[G_C].at;
        if (!wait_role(r,G_C,G_C,r->work)) return;
        r->times[T_C_REAP]=r->waits[G_C].at;
        if (!WIFEXITED(r->waits[G_C].status) || WEXITSTATUS(r->waits[G_C].status)!=23) {
            fail(r,"parent_wait","coordinator_exit23",0); return;
        }
        if (!observe_adoption(r,H,0,r->cleanup) || !snapshot(r,0) || !planned_signal(r,0) ||
            !terminal_poll(r,G_H,G_H,r->cleanup)) return;
        r->times[T_H_EXIT]=r->polls[G_H].at;
        if (!wait_role(r,G_H,G_H,r->cleanup) || !expected_kill_wait(r,G_H)) return;
        r->times[T_H_REAP]=r->waits[G_H].at; r->handles[H_W].kernel=1;
    } else {
        if (!snapshot(r,0) || !planned_signal(r,0) || !receive_until(r,H_WAIT,C,r->cleanup) ||
            !terminal_poll(r,G_H,G_H,r->cleanup)) return;
        r->times[T_H_EXIT]=r->polls[G_H].at;
    }
    if (!observe_adoption(r,W,1,r->cleanup) || !snapshot(r,1)) return;
    mark(r,T_W_PRE);
    if (!planned_signal(r,1) || !terminal_poll(r,G_W,G_W,r->cleanup)) return;
    r->times[T_W_EXIT]=r->polls[G_W].at;
    if (!wait_role(r,G_W,G_W,r->cleanup) || !expected_kill_wait(r,G_W)) return;
    r->times[T_W_REAP]=r->waits[G_W].at;
    if (!r->coord_loss) {
        mark(r,T_C_FINISH);
        if (!command_send(r,FINISH,r->terminal_end) ||
            !receive_until(r,FINISH_ACK,C,r->terminal_end)) return;
        mark(r,T_C_FINISH_ACK);
        if (!terminal_poll(r,G_C,G_C,r->terminal_end)) return;
        r->times[T_C_EXIT]=r->polls[G_C].at;
        if (!wait_role(r,G_C,G_C,r->terminal_end)) return;
        r->times[T_C_REAP]=r->waits[G_C].at;
        if (!WIFEXITED(r->waits[G_C].status) || WEXITSTATUS(r->waits[G_C].status)!=0) {
            fail(r,"parent_wait","coordinator_exit0",0); return;
        }
    }
    (void)reset_terminal(r);
}
static void negative_observe(struct report *r)
{
    int tag; struct frame f;
    /* Failure is irreversible: no signal, command, new handle or reset here. */
    if (r->endpoints[CR_R]>=0) {
        ssize_t n=read(r->endpoints[CR_R],&f,sizeof(f));
        if (n==(ssize_t)sizeof(f) && f.magic==MAGIC && f.case_id==r->coord_loss &&
            f.t0==r->t0 && !memcmp(f.nonce,r->nonce,65) && f.role>=C && f.role<=W &&
            f.kind>=READY && f.kind<=ERROR_FRAME) (void)accept_frame(r,&f);
    }
    for (tag=G_C;tag<=G_W;tag++) {
        struct handle_fact *h=&r->handles[tag]; struct pollfd p; int target=handle_targets[tag],status;
        pid_t waited;
        if (!h->known || h->closed || raw_now()>=r->total) continue;
        p.fd=h->w.fd; p.events=POLLIN; p.revents=0;
        if (poll(&p,1,0)>0 && (p.revents&POLLIN)) {
            r->terminal[target]=1;
            if (!r->reaped[target] && (target==C || r->adopted[target])) {
                struct wait_fact *w=&r->waits[tag];
                w->owner=G; w->target=target; w->pid=r->ids[target].pid; w->attempted=1;
                w->attempts++; errno=0; waited=waitpid(w->pid,&status,WNOHANG);
                w->result=(int)waited; w->err=errno; w->at=raw_now();
                if (waited==w->pid) { w->status=status; r->reaped[target]=1; }
            }
        }
        (void)close_handle(r,tag,0);
    }
}
static void json_report(struct report *r);
int main(int argc,char **argv)
{
    struct report r; int n,pair[2]; pid_t pid; struct sigaction action;
    memset(&r,0,sizeof(r)); r.me=G; r.pf=-1; r.own_handle=-1; r.out=-1; r.in=-1;
    r.stage="none"; r.operation=NULL; r.error_role=-1;
    for (n=0;n<ENDS;n++) r.endpoints[n]=-1;
    if (argc!=3 || (strcmp(argv[1],"guard_loss") && strcmp(argv[1],"coordinator_loss")) ||
        strlen(argv[2])!=64) return 2;
    for (n=0;n<64;n++) if (!((argv[2][n]>='0' && argv[2][n]<='9') ||
        (argv[2][n]>='a' && argv[2][n]<='f'))) return 2;
    memcpy(r.nonce,argv[2],65); r.coord_loss=!strcmp(argv[1],"coordinator_loss");
    r.t0=raw_now(); r.last=r.t0;
    if (r.t0<0 || r.t0>INT64_MAX-14*NS) return 2;
    r.work=r.t0+5*NS; r.cleanup=r.t0+8*NS; r.terminal_end=r.t0+10*NS;
    r.total=r.t0+12*NS; r.expiry=r.t0+14*NS;
    for (n=0;n<3;n++) r.original_stdio[n]=fstat(n,&r.stdio_stat[n])==0;
    r.pf=open("/proc/self/exe",O_RDONLY|O_CLOEXEC);
    if (r.pf<0 || !product_fd_stat(r.pf,&r.product) ||
        !capture((int)getpid(),&r.ids[G])) fail(&r,"identity","guardian_product",errno);
    mark(&r,T_ID);
    memset(&action,0,sizeof(action)); action.sa_handler=SIG_IGN;
    if (sigemptyset(&action.sa_mask)) fail(&r,"signal_disposition","sigemptyset",errno);
    r.sigpipe.attempted=1; errno=0; r.sigpipe.result=sigaction(SIGPIPE,&action,NULL); r.sigpipe.err=errno;
    if (r.sigpipe.result) fail(&r,"signal_disposition","sigaction",r.sigpipe.err);
    if (!r.failed && get_sub(&r,&r.sub[0],0) &&
        set_sub(&r,&r.sub[1],1,"prctl_set_enabled") && get_sub(&r,&r.sub[2],1)) {
        for (n=0;n<ENDS && !r.failed;n+=2) {
            if (!before(&r,r.work)) break;
            if (pipe2(pair,O_NONBLOCK|O_CLOEXEC)) { fail(&r,"pipe","pipe2",errno); break; }
            r.endpoints[n]=pair[0]; r.endpoints[n+1]=pair[1];
            errno=0; { long bound=fpathconf(pair[0],_PC_PIPE_BUF);
                if (bound<(long)sizeof(struct frame) || bound>INT_MAX)
                    fail(&r,"pipe","packet_pipe_buf",errno);
                else if (!r.pipebuf || bound<r.pipebuf) r.pipebuf=(int)bound;
            }
        }
        if (!r.failed && before(&r,r.work)) {
            errno=0; pid=fork();
            if (pid<0) fail(&r,"fork","fork",errno);
            else if (!pid) child_role(&r,C);
            else {
                r.child=pid; r.created[C]=1;
                if (!capture((int)pid,&r.ids[C]) || r.ids[C].ppid!=r.ids[G].pid ||
                    !open_handle(&r,G_C,&r.ids[C])) fail(&r,"identity","coordinator_anchor",errno);
                close_inherited(&r);
                if (!r.failed) guardian_case(&r);
            }
        }
    }
    if (!r.failed && !r.reset_gate) fail(&r,"terminal","missing_complete_predicate",0);
    if (r.failed) negative_observe(&r);
    for (n=0;n<ENDS;n++) if (r.endpoints[n]>=0) close_end(&r,n,TERMINAL,0);
    if (r.pf>=0) { int fd=r.pf; r.pf=-1; (void)close_raw(&r,fd,ENDS,TERMINAL,0); }
    mark(&r,T_FINAL); json_report(&r);
    return r.failed?1:0;
}
/* Static serializer fragment authored by root; integrate into the one new TU.
 * It never converts missing observations into completed operations. */
static void json_string(const char *s)
{
    const unsigned char *p=(const unsigned char *)s;
    if (!s) { fputs("null",stdout); return; }
    putchar('"');
    for (; *p; p++) {
        if (*p=='"' || *p=='\\') { putchar('\\'); putchar(*p); }
        else if (*p<32 || *p>=127) printf("\\u%04x",(unsigned int)*p);
        else putchar(*p);
    }
    putchar('"');
}
static void json_bool(int value) { fputs(value?"true":"false",stdout); }
static void json_optional(int observed,int64_t value)
{ if (observed) printf("%" PRIi64,value); else fputs("null",stdout); }
static void json_time(int64_t value) { json_optional(value>0,value); }
static void json_fact(const struct fact *f)
{
    fputs("{\"attempted\":",stdout); json_bool(f->attempted);
    fputs(",\"result\":",stdout); json_optional(f->attempted,f->result);
    fputs(",\"errno\":",stdout); json_optional(f->attempted,f->err);
    fputs(",\"value\":",stdout); json_optional(f->attempted && f->has_value,f->value);
    putchar('}');
}
static void json_product(const struct product *p)
{
    printf("{\"dev\":%" PRIu64 ",\"ino\":%" PRIu64 ",\"size\":%" PRIu64
           ",\"mtime_ns\":%" PRIi64 ",\"ctime_ns\":%" PRIi64 "}",
           p->dev,p->ino,p->size,p->mtime_ns,p->ctime_ns);
}
static void json_identity(const struct identity *id)
{
    if (!id->known) { fputs("null",stdout); return; }
    printf("{\"pid\":%d,\"ppid\":%d,\"start_ticks\":%" PRIu64 ",\"boot_id\":",
           id->pid,id->ppid,id->start);
    json_string(id->boot);
    printf(",\"uid\":%" PRIu32 ",\"euid\":%" PRIu32 ",\"product_identity\":",id->uid,id->euid);
    json_product(&id->product); putchar('}');
}
static void json_poll(const struct poll_fact *p,int tag,int stage,int declared_fd)
{
    /* Declared routing is used only when no operation occurred. */
    int observed=p->attempts>0;
    fputs("{\"owner\":",stdout); json_string(role_names[observed?p->owner:handle_owners[tag]]);
    fputs(",\"target\":",stdout); json_string(role_names[observed?p->target:handle_targets[tag]]);
    printf(",\"fd\":%d,\"stage\":",observed?p->fd:declared_fd);
    json_string((observed?p->stage:stage)==INITIAL?"initial_live":
                (observed?p->stage:stage)==AFTER_ACK?"EOF_child_live":"terminal");
    printf(",\"attempts\":%d,\"requested_events\":%d,\"result\":",p->attempts,POLLIN);
    json_optional(observed,p->result);
    fputs(",\"revents\":",stdout); json_optional(observed,p->revents);
    fputs(",\"errno\":",stdout); json_optional(observed,p->err);
    fputs(",\"observed_at_ns\":",stdout); json_optional(observed && p->at>0,p->at); putchar('}');
}
static void json_members(const int *set,int invert)
{
    int k,comma=0; putchar('[');
    for (k=C;k<ROLES;k++) if (!!set[k]!=!!invert) {
        if (comma++) putchar(','); json_string(role_names[k]);
    }
    putchar(']');
}
static const char *json_close_kind(const struct close_fact *c)
{
    if ((c->owner==H && c->kind==CH_R) || (c->owner==W && c->kind==HW_R)) return "command_read";
    if ((c->owner==H && c->kind==HR_W) || (c->owner==W && c->kind==WR_W)) return "report_write";
    if (c->kind>=0 && c->kind<ENDS) return end_names[c->kind];
    if (c->kind==ENDS) return "product_descriptor";
    if (c->kind==ENDS+1) return "inherited_stdin";
    if (c->kind==ENDS+2) return "inherited_stdout";
    if (c->kind==ENDS+3) return "inherited_stderr";
    return "unknown_descriptor";
}
static void json_report(struct report *r)
{
    int k,j,comma=0; const char *case_name=r->coord_loss?"coordinator_loss":"guard_loss";
    const char *sub_names[]={"initial_get","set_enabled","verify_enabled_get",
                            "terminal_set_disabled","terminal_verify_disabled_get"};
    const char *control_names[]={"functional_containment_verified","containment_available",
        "execution_available","resource_authority","model_runtime_ABI_observed",
        "production_controller_guard_completed","GPU_or_foreign_restore","physical_exclusion_verified",
        "guardian_loss_recovery_verified","observer_loss_recovery_verified","host_loss_recovery_guaranteed",
        "arbitrary_descendant_or_exec_containment_verified","queue_restore_proven"};
    fputs("{\"schema_version\":1,\"scope\":\"frontier_v8_owned_C_guardian_adoption_CPU_fixture\",\"case\":",stdout);
    json_string(case_name); fputs(",\"nonce\":",stdout); json_string(r->nonce);
    fputs(",\"status\":",stdout); json_string(r->failed?"failed":"success");
    fputs(",\"error\":{\"stage\":",stdout); json_string(r->failed?r->stage:"none");
    fputs(",\"role\":",stdout); json_string(r->failed?role_names[r->error_role]:NULL);
    fputs(",\"operation\":",stdout); json_string(r->failed?r->operation:NULL);
    fputs(",\"errno\":",stdout); json_optional(r->failed,r->error_no);
    fputs(",\"bounded_detail\":null},\"headers\":{",stdout);
    printf("\"pidfd_open\":%ld,\"pidfd_send_signal\":%ld,\"pr_set_child_subreaper\":%ld,"
           "\"pr_get_child_subreaper\":%ld,\"SIGKILL\":%d,\"POLLIN\":%d,\"POLLNVAL\":%d,"
           "\"F_GETFD\":%d,\"FD_CLOEXEC\":%d,\"EBADF\":%d,\"PIPE_BUF\":%d,",
           (long)SYS_pidfd_open,(long)SYS_pidfd_send_signal,(long)PR_SET_CHILD_SUBREAPER,
           (long)PR_GET_CHILD_SUBREAPER,SIGKILL,POLLIN,POLLNVAL,F_GETFD,FD_CLOEXEC,EBADF,PIPE_BUF);
    printf("\"target_int_bytes\":%zu,\"target_long_bytes\":%zu,\"target_pointer_bytes\":%zu,"
           "\"target_char_bits\":%d,\"target_byte_order\":%d,\"pid_t_bytes\":%zu,\"uid_t_bytes\":%zu,"
           "\"pid_t_signed\":true,\"uid_t_signed\":false,\"uint64_bytes\":%zu,\"int64_bytes\":%zu,",
           sizeof(int),sizeof(long),sizeof(void *),CHAR_BIT,__BYTE_ORDER__,sizeof(pid_t),sizeof(uid_t),
           sizeof(uint64_t),sizeof(int64_t));
    printf("\"pid_representation\":\"signed32\",\"uid_representation\":\"unsigned32\","
           "\"uint64_representation\":\"unsigned64\",\"int64_representation\":\"signed64\","
           "\"pid_max\":%" PRIi32 ",\"uid_max\":%" PRIu32 ",\"uint64_max\":%" PRIu64
           ",\"int64_min\":%" PRIi64 ",\"int64_max\":%" PRIi64 "},\"subreaper\":{",
           INT32_MAX,UINT32_MAX,UINT64_MAX,INT64_MIN,INT64_MAX);
    for (k=0;k<5;k++) { if (k) putchar(','); json_string(sub_names[k]); putchar(':'); json_fact(&r->sub[k]); }
    fputs("},\"child_subreaper_get\":{",stdout);
    for (k=C;k<ROLES;k++) { if (k>C) putchar(','); json_string(role_names[k]); putchar(':'); json_fact(&r->child_sub[k]); }
    fputs("},\"identities_initial\":{",stdout);
    for (k=G;k<ROLES;k++) { if (k) putchar(','); json_string(role_names[k]); putchar(':'); json_identity(&r->ids[k]); }
    fputs("},\"identity_rechecks\":{",stdout);
    for (j=0;j<2;j++) {
        if (j) putchar(','); json_string(j?"before_W_signal":"before_H_signal"); fputs(":{",stdout);
        for (k=G;k<ROLES;k++) { if (k) putchar(','); json_string(role_names[k]); putchar(':'); json_identity(&r->checks[j][k]); }
        putchar('}');
    }
    fputs("},\"adoptions\":[",stdout);
    for (k=0;k<2;k++) if (r->adoption[k].known) {
        struct adoption *a=&r->adoption[k]; int target=a->target;
        if (comma++) putchar(','); fputs("{\"phase\":",stdout);
        json_string(target==H?"guard_adopted":"worker_adopted");
        fputs(",\"target\":",stdout); json_string(role_names[target]);
        printf(",\"expected_old_parent\":%d,\"observed_new_parent\":%d,\"observed_identity\":",
               r->ids[target].ppid,a->id.ppid);
        json_identity(&a->id); fputs(",\"initial_identity_equal_except_ppid\":",stdout);
        json_bool(same_identity(&r->ids[target],&a->id,1));
        fputs(",\"guardian_identity\":",stdout); json_identity(&a->guardian);
        fputs(",\"observed_at_ns\":",stdout); json_time(a->at);
        fputs(",\"passed\":",stdout); json_bool(same_identity(&r->ids[target],&a->id,1) &&
            a->id.ppid==a->guardian.pid && alive(&a->id) && alive(&a->guardian)); putchar('}');
    }
    fputs("],\"pidfds\":{",stdout);
    for (k=0;k<HANDLES;k++) {
        struct handle_fact *h=&r->handles[k]; struct handle_wire *w=&h->w;
        if (k) putchar(','); json_string(handle_names[k]); fputs(":{\"owner\":",stdout);
        json_string(role_names[handle_owners[k]]); fputs(",\"target\":",stdout); json_string(role_names[handle_targets[k]]);
        printf(",\"fd\":%d,\"open\":",h->known?w->fd:-1); json_fact(&w->open);
        fputs(",\"identity_before\":",stdout); json_identity(&w->before);
        fputs(",\"identity_after\":",stdout); json_identity(&w->after);
        fputs(",\"fdinfo\":{\"attempted\":",stdout); json_bool(h->known);
        fputs(",\"pid\":",stdout); json_optional(h->known,w->fdi_pid>0?w->fdi_pid:-1);
        fputs(",\"matches\":",stdout); json_bool(w->fdi_matches); fputs("},\"cloexec\":",stdout); json_fact(&w->flags);
        fputs(",\"live_poll\":",stdout); json_poll(&w->live,k,INITIAL,h->known?w->fd:-1);
        fputs(",\"close_mode\":",stdout); json_string(h->close.attempted?"explicit_close_then_immediate_EBADF":
                                                    h->kernel?"owner_SIGKILL_kernel_teardown":"unobserved");
        fputs(",\"explicit_close\":",stdout); json_fact(&h->close);
        fputs(",\"immediate_F_GETFD\":",stdout); json_fact(&h->badfd);
        fputs(",\"kernel_teardown_limit\":",stdout); json_string(h->kernel?"No explicit H_W close/EBADF observation":NULL);
        printf(",\"signal_budget\":%d}",(k==G_H || k==G_W)?1:0);
    }
    fputs("},\"polls\":{",stdout);
    for (k=0;k<6;k++) {
        int tag=k<4?k:k==4?H_W:C_H;
        if (k) putchar(','); json_string(k<4?handle_names[k]:k==4?"H_W_EOF":"C_H_EOF"); putchar(':');
        json_poll(&r->polls[k],tag,k<4?TERMINAL:AFTER_ACK,r->handles[tag].known?r->handles[tag].w.fd:-1);
    }
    fputs("},\"waits\":{",stdout);
    for (k=0;k<4;k++) {
        struct wait_fact *w=&r->waits[k]; int attempted=w->attempted;
        int completed=attempted && w->result>0 && w->result==w->pid;
        if (k) putchar(','); json_string(handle_names[k]); fputs(":{\"owner\":",stdout);
        json_string(role_names[attempted?w->owner:handle_owners[k]]);
        fputs(",\"target\":",stdout); json_string(role_names[attempted?w->target:handle_targets[k]]);
        printf(",\"pid\":%d,\"stage\":\"terminal\",\"attempted\":",
               attempted?w->pid:r->ids[handle_targets[k]].known?r->ids[handle_targets[k]].pid:-1);
        json_bool(attempted); printf(",\"attempts\":%d,\"result\":",w->attempts); json_optional(attempted,w->result);
        fputs(",\"raw_status\":",stdout); json_optional(completed,w->status);
        fputs(",\"exited\":",stdout); if (completed) json_bool(WIFEXITED(w->status)); else fputs("null",stdout);
        fputs(",\"exit_code\":",stdout); json_optional(completed && WIFEXITED(w->status),WEXITSTATUS(w->status));
        fputs(",\"signaled\":",stdout); if (completed) json_bool(WIFSIGNALED(w->status)); else fputs("null",stdout);
        fputs(",\"term_signal\":",stdout); json_optional(completed && WIFSIGNALED(w->status),WTERMSIG(w->status));
        fputs(",\"errno\":",stdout); json_optional(attempted,w->err);
        fputs(",\"observed_at_ns\":",stdout); json_optional(attempted && w->at>0,w->at); putchar('}');
    }
    fputs("},\"signals\":[",stdout);
    for (k=0;k<2;k++) {
        struct signal_fact *s=&r->signals[k]; int tag=k?G_W:G_H, target=k?W:H;
        if (k) putchar(','); fputs("{\"ledger_kind\":\"planned\",\"owner\":\"guardian\",\"target\":",stdout);
        json_string(role_names[target]); printf(",\"fd\":%d,\"original_handle_tag\":",r->handles[tag].known?r->handles[tag].w.fd:-1);
        json_string(handle_names[tag]); fputs(",\"original_identity\":",stdout); json_identity(&r->ids[target]);
        fputs(",\"presignal_identity\":",stdout); json_identity(&s->presignal);
        printf(",\"symbol\":\"SIGKILL\",\"number_from_header\":%d,\"flags\":0,\"attempts\":%d,"
               "\"attempt_budget_consumed_before_call\":",SIGKILL,s->attempts); json_bool(s->consumed);
        fputs(",\"negative_state_entered\":",stdout); json_bool(s->attempts?s->negative_at_entry:r->failed);
        fputs(",\"later_planned_actions_disabled\":",stdout); json_bool(r->failed);
        fputs(",\"result\":",stdout); json_optional(s->attempts,s->result);
        fputs(",\"errno\":",stdout); json_optional(s->attempts,s->err);
        fputs(",\"observed_at_ns\":",stdout); json_optional(s->attempts && s->at>0,s->at); putchar('}');
    }
    fputs("],\"fd_ledger\":[",stdout); comma=0;
    for (k=0;k<r->close_count;k++) {
        struct close_fact *c=&r->closes[k]; if (comma++) putchar(','); fputs("{\"owner\":",stdout);
        json_string(role_names[c->owner]); fputs(",\"kind\":",stdout); json_string(json_close_kind(c));
        printf(",\"fd\":%d,\"stage\":",c->fd); json_string(c->stage==INITIAL?"initial_inherited":c->stage==AFTER_ACK?"after_arm_ack":"terminal");
        printf(",\"attempted\":true,\"close_result\":%d,\"close_errno\":%d,\"F_GETFD_result\":%d,\"F_GETFD_errno\":%d,"
               "\"observation_mode\":\"explicit_close_then_immediate_EBADF\",\"limit\":null}",
               c->result,c->err,c->bad_result,c->bad_err);
    }
    if (r->handles[H_W].kernel) {
        if (comma++) putchar(','); printf("{\"owner\":\"guard\",\"kind\":\"pidfd\",\"fd\":%d,\"stage\":\"owner_death\","
            "\"attempted\":false,\"close_result\":null,\"close_errno\":null,\"F_GETFD_result\":null,\"F_GETFD_errno\":null,"
            "\"observation_mode\":\"owner_SIGKILL_kernel_teardown\",\"limit\":\"No explicit H_W close/EBADF observation\"}",r->handles[H_W].w.fd);
    }
    fputs("],\"packets\":[",stdout);
    for (k=0;k<r->packet_count;k++) {
        struct packet_row *p=&r->packets[k]; int display=p->kind==EOF_FACT?p->aux:p->role;
        if (k) putchar(','); fputs("{\"edge\":",stdout); json_string(p->outgoing?"C_from_G":"G_from_C");
        fputs(",\"kind\":",stdout); json_string(kind_names[p->kind]); fputs(",\"role\":",stdout); json_string(role_names[display]);
        printf(",\"stage_ordinal\":%d,\"case\":",k+1); json_string(case_name); fputs(",\"nonce\":",stdout); json_string(r->nonce);
        printf(",\"shared_t0\":%" PRIi64 ",\"bytes\":%zu,\"PIPE_BUF_bound\":%d,\"forwarded_original_frame\":",r->t0,sizeof(struct frame),r->pipebuf);
        json_bool(!p->outgoing && p->role!=C);
        fputs(",\"complete\":true,\"parent_EOF_while_child_alive\":",stdout); json_bool(p->kind==EOF_FACT); putchar('}');
    }
    fputs("],\"deadlines\":{\"t0_ns\":",stdout); json_time(r->t0);
    fputs(",\"work_ns\":",stdout); json_time(r->work); fputs(",\"cleanup_ns\":",stdout); json_time(r->cleanup);
    fputs(",\"terminal_ns\":",stdout); json_time(r->terminal_end); fputs(",\"guardian_total_ns\":",stdout); json_time(r->total);
    fputs(",\"child_self_expiry_ns\":",stdout); json_time(r->expiry); fputs("},\"times_ns\":{",stdout);
    for (k=0;k<TIMES;k++) { if (k) putchar(','); json_string(time_names[k]); putchar(':'); json_time(r->times[k]); }
    fputs("},\"controls\":{",stdout);
    for (k=0;k<13;k++) { if (k) putchar(','); json_string(control_names[k]); fputs(":false",stdout); }
    fputs("},\"negative_state\":{\"entered\":",stdout); json_bool(r->failed);
    fputs(",\"first_error_stage\":",stdout); json_string(r->failed?r->stage:NULL);
    fputs(",\"first_error_operation\":",stdout); json_string(r->failed?r->operation:NULL);
    fputs(",\"first_error_at_ns\":",stdout); json_optional(r->failed && r->error_at>0,r->error_at);
    fputs(",\"later_planned_signals_disabled\":",stdout); json_bool(r->failed);
    fputs(",\"negative_cleanup_signals\":[],\"known_created\":",stdout); json_members(r->created,0);
    fputs(",\"known_bound\":",stdout); json_members(r->bound,0);
    fputs(",\"known_adopted\":",stdout); json_members(r->adopted,0);
    fputs(",\"known_terminal\":",stdout); json_members(r->terminal,0);
    fputs(",\"known_reaped\":",stdout); json_members(r->reaped,0);
    fputs(",\"unknown_members\":",stdout); json_members(r->reaped,1);
    fputs(",\"terminal_reset_gate_complete\":",stdout); json_bool(r->reset_gate);
    fputs(",\"self_SIGPIPE_ignore\":",stdout); json_fact(&r->sigpipe); fputs("}}\n",stdout);
}
