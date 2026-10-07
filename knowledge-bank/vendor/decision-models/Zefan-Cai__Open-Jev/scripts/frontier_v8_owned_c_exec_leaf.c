#define _GNU_SOURCE
#include "frontier_v8_owned_c_exec_protocol.h"

static int leaf_arguments(struct ex_context *r,int argc,char **argv) {
    uint64_t v[23]; int k; static const int indexes[]={4,5,6,7,8,9,11,12,13,14,15,
        16,17,18,19,20,21,22,23,24,25};
    if(argc!=27 || strcmp(argv[0],"frontier-owned-leaf") || strcmp(argv[1],"--fixed-leaf") ||
       !ex_nonce(argv[3]) || !ex_boot(argv[10])) return 0;
    if(!strcmp(argv[2],"normal")) r->case_id=EX_NORMAL;
    else if(!strcmp(argv[2],"worker_loss")) r->case_id=EX_LOSS; else return 0;
    if(!strcmp(argv[26],"none")) r->fault=EX_NOFAULT;
    else if(!strcmp(argv[26],"exec_fd_closed")) r->fault=EX_CLOSED_EXEC;
    else if(!strcmp(argv[26],"witness_cloexec_cleared")) r->fault=EX_LEAK_WITNESS; else return 0;
    for(k=0;k<21;k++) if(!ex_u64(argv[indexes[k]],UINT64_MAX,&v[k])) return 0;
    if(v[0]>INT64_MAX || !v[1] || v[1]>INT32_MAX || !v[2] || v[2]>INT32_MAX ||
       !v[3] || v[4]>UINT32_MAX || v[5]>UINT32_MAX) return 0;
    for(k=6;k<=10;k++) if(v[k]<=2 || v[k]>INT_MAX) return 0;
    for(k=6;k<=10;k++) { int j; for(j=6;j<k;j++) if(v[k]==v[j]) return 0; }
    for(k=14;k<=15;k++) if(v[k]>INT64_MAX) return 0;
    for(k=19;k<=20;k++) if(v[k]>INT64_MAX) return 0;
    memcpy(r->nonce,argv[3],65); r->t0=(int64_t)v[0];
    r->ids[EX_G].known=1; r->ids[EX_G].pid=(int)v[1]; r->ids[EX_G].ppid=(int)v[2];
    r->ids[EX_G].start=v[3]; r->ids[EX_G].uid=(uint32_t)v[4]; r->ids[EX_G].euid=(uint32_t)v[5];
    memcpy(r->ids[EX_G].boot,argv[10],37);
    r->in=r->fd[EX_COMMAND_R]=(int)v[6]; r->out=r->fd[EX_REPORT_W]=(int)v[7];
    r->startup[0].label=EX_LEAF_FD; r->startup[0].fd=(int)v[8];
    r->startup[1].label=EX_WITNESS_FD; r->startup[1].fd=(int)v[9];
    r->startup[2].label=EX_ERROR_W; r->startup[2].fd=(int)v[10];
    r->startup[3].label=EX_COMMAND_R; r->startup[3].fd=(int)v[6];
    r->startup[4].label=EX_REPORT_W; r->startup[4].fd=(int)v[7];
    r->guardian_product=(struct ex_product){v[11],v[12],v[13],(int64_t)v[14],(int64_t)v[15]};
    r->leaf_product=(struct ex_product){v[16],v[17],v[18],(int64_t)v[19],(int64_t)v[20]};
    r->ids[EX_G].product=r->guardian_product;
    return r->guardian_product.size>0 && r->leaf_product.size>0 && ex_deadlines(r);
}
static void leaf_absent_stdio(struct ex_context *r) {
    int k; for(k=0;k<3;k++) {
        struct ex_close c; memset(&c,0,sizeof(c)); c.owner=r->role;
        c.label=EX_STD0+k; c.epoch=EX_STDIO; c.fd=-1; c.evidence=EX_ABSENT;
        ex_store_close(r,&c);
    }
}
/* No open/proc read occurs before all five entry F_GETFD operations. */
static int leaf_startup(struct ex_context *r) {
    int k,rc,err; struct ex_frame f; long bound;
    r->stage=EX_STARTUP_STAGE;
    for(k=0;k<5;k++) {
        errno=0; rc=fcntl(r->startup[k].fd,F_GETFD); err=errno;
        ex_fact_set(r,&r->startup[k].fact,rc,err,0);
        if(k<3 ? (rc!=-1 || err!=EBADF) : (rc<0 || (rc&FD_CLOEXEC)))
            ex_fail(r,EX_OP_STARTUP,err,1,rc);
    }
    /* Reporting is safe only through the two known retained private handles. */
    if(r->startup[3].fact.result<0 || r->startup[4].fact.result<0) return 0;
    errno=0; bound=fpathconf(r->out,_PC_PIPE_BUF);
    if(bound<(long)sizeof(struct ex_frame) || bound>INT_MAX) ex_fail(r,EX_OP_PIPE,errno,0,0);
    else r->pipebuf=(int)bound;
    (void)ex_sigpipe(r);
    for(k=0;k<5;k++) {
        f=ex_frame_make(r,EX_STARTUP,EX_EDGE_GE,k); f.body.startup=r->startup[k];
        (void)ex_emit(r,&f);
    }
    (void)ex_flags_check(r,EX_COMMAND_R,EX_PREEXEC,1);
    (void)ex_flags_check(r,EX_REPORT_W,EX_PREEXEC,1);
    leaf_absent_stdio(r);
    /* Only the controlled leaked witness is a known still-owned entry FD. */
    if(r->startup[1].fact.result>=0 && r->fault==EX_LEAK_WITNESS) {
        struct ex_product p;
        if(ex_product_fd(r->startup[1].fd,&p) && ex_same_product(&p,&r->leaf_product))
            r->fd[EX_WITNESS_FD]=r->startup[1].fd;
    }
    return !r->error.observed;
}
static void leaf_failure(struct ex_context *r,int created) {
    int k;
    ex_error_up(r,0);
    if(r->handles[EX_ED].known) (void)ex_handle_close(r,EX_ED,1);
    for(k=0;k<EX_FDS;k++) {
        if(k==EX_REPORT_W || k==EX_CHILD_REPORT_W || k>=EX_STD0) continue;
        if(r->fd[k]>=0) (void)ex_close_owned(r,k,k>=EX_CHILD_COMMAND_R && k<=EX_ED_FD?EX_CHILD:EX_PREEXEC,1);
    }
    if(r->out>=0) {
        int label=r->role==EX_D?EX_CHILD_REPORT_W:EX_REPORT_W;
        (void)ex_close_owned(r,label,r->role==EX_D?EX_CHILD:EX_PREEXEC,0); r->out=-1;
    }
    if(!created) _exit(70);
    ex_park(r,70);
}
static int leaf_relay(struct ex_context *r,int expected,int64_t end) {
    struct ex_frame f; int rc;
    while(!r->error.observed) {
        rc=ex_read_frame(r,r->fd[EX_CHILD_REPORT_R],&f,end,0);
        if(rc!=1) return 0;
        if(f.source!=EX_D || f.edge!=EX_EDGE_ED ||
           f.seq!=r->incoming[EX_D][EX_EDGE_ED]+1 || f.at<r->incoming_at[EX_D][EX_EDGE_ED]) {
            ex_fail(r,EX_OP_SEQUENCE,0,0,0); return 0;
        }
        r->incoming[EX_D][EX_EDGE_ED]=f.seq; r->incoming_at[EX_D][EX_EDGE_ED]=f.at;
        if(f.kind==EX_D_READY) {
            if(!ex_same_identity(&f.body.identity,&r->ids[EX_D],0)) {
                ex_fail(r,EX_OP_PROC,0,0,0); return 0;
            }
        } else if(f.kind==EX_ERROR) {
            if(!r->error.observed) r->error=f.body.error;
        } else if(f.kind!=EX_FD_CLOSE && f.kind!=EX_FD_FLAGS && f.kind!=EX_SUB &&
                  f.kind!=EX_SIGPIPE && f.kind!=EX_ARM_ACK && f.kind!=EX_D_FINISH_ACK) {
            ex_fail(r,EX_OP_FRAME,0,0,0); return 0;
        }
        if(!ex_write_frame(r,r->out,&f,end,0)) return 0;
        if(r->error.observed) return 0;
        if(f.kind==expected) return 1;
        if(f.kind==EX_ARM_ACK || f.kind==EX_D_FINISH_ACK || f.kind==EX_D_READY) {
            ex_fail(r,EX_OP_STATE,0,0,0); return 0;
        }
    }
    return 0;
}
static int leaf_forward(struct ex_context *r,const struct ex_frame *command) {
    struct ex_frame f; int64_t at;
    if(!ex_gate(r,r->work,1)) return 0;
    at=r->last;
    if(!ex_write_frame(r,r->fd[EX_CHILD_COMMAND_W],command,r->work,1)) return 0;
    f=ex_frame_make(r,EX_FORWARD,EX_EDGE_GE,command->kind);
    f.body.forward.kind=command->kind; f.body.forward.original_seq=command->seq;
    f.body.forward.at=at; return ex_emit(r,&f);
}
static void descendant(struct ex_context *r) {
    struct ex_frame f; int rc;
    r->role=EX_D; r->stage=EX_CREATED; memset(r->seq,0,sizeof(r->seq));
    memset(r->incoming,0,sizeof(r->incoming)); memset(r->incoming_at,0,sizeof(r->incoming_at));
    r->in=r->fd[EX_CHILD_COMMAND_R]; r->out=r->fd[EX_CHILD_REPORT_W];
    (void)ex_close_owned(r,EX_COMMAND_R,EX_PREEXEC,1);
    (void)ex_close_owned(r,EX_REPORT_W,EX_PREEXEC,1);
    (void)ex_close_owned(r,EX_CHILD_COMMAND_W,EX_CHILD,1);
    (void)ex_close_owned(r,EX_CHILD_REPORT_R,EX_CHILD,1);
    leaf_absent_stdio(r);
    if(!ex_sigpipe(r) || !ex_flags_check(r,EX_CHILD_COMMAND_R,EX_CHILD,-1) ||
       !ex_flags_check(r,EX_CHILD_REPORT_W,EX_CHILD,-1)) leaf_failure(r,1);
    if(!ex_sub_get(r,&r->child_sub[EX_D],0)) leaf_failure(r,1);
    f=ex_frame_make(r,EX_SUB,EX_EDGE_ED,EX_D); f.body.fact.key=EX_D;
    f.body.fact.fact=r->child_sub[EX_D]; if(!ex_emit(r,&f)) leaf_failure(r,1);
    if(!ex_capture((int)getpid(),&r->ids[EX_D]) ||
       r->ids[EX_D].ppid!=r->ids[EX_E].pid ||
       r->ids[EX_D].uid!=r->ids[EX_E].uid || r->ids[EX_D].euid!=r->ids[EX_E].euid ||
       strcmp(r->ids[EX_D].boot,r->ids[EX_E].boot) ||
       !ex_same_product(&r->ids[EX_D].product,&r->leaf_product)) {
        ex_fail(r,EX_OP_PROC,errno,0,0); leaf_failure(r,1);
    }
    f=ex_frame_make(r,EX_D_READY,EX_EDGE_ED,0); f.body.identity=r->ids[EX_D];
    if(!ex_emit(r,&f) || ex_command_read(r,EX_ARM,3,r->work,&f,0)!=1) leaf_failure(r,1);
    r->stage=EX_ARMED;
    f=ex_frame_make(r,EX_ARM_ACK,EX_EDGE_ED,3);
    if(!ex_emit(r,&f)) leaf_failure(r,1);
    rc=ex_command_read(r,EX_FINISH,4,r->terminal_end,&f,1);
    if(r->case_id==EX_LOSS && rc==0 && !r->error.observed) {
        /* No ERROR write to the dead owner. Closes are not returned to G. */
        (void)ex_close_owned(r,EX_CHILD_COMMAND_R,EX_CHILD,0);
        (void)ex_close_owned(r,EX_CHILD_REPORT_W,EX_CHILD,0); r->out=-1;
        ex_park(r,72);
    }
    if(r->case_id!=EX_NORMAL || rc!=1) {
        ex_fail(r,EX_OP_STATE,0,0,0); leaf_failure(r,1);
    }
    r->stage=EX_FINISH_STAGE;
    if(!ex_close_owned(r,EX_CHILD_COMMAND_R,EX_CHILD,1)) leaf_failure(r,1);
    f=ex_frame_make(r,EX_D_FINISH_ACK,EX_EDGE_ED,4);
    if(!ex_emit(r,&f)) leaf_failure(r,1);
    (void)ex_close_owned(r,EX_CHILD_REPORT_W,EX_CHILD,0); r->out=-1;
    _exit(r->error.observed?72:0);
}
int main(int argc,char **argv) {
    struct ex_context r; struct ex_frame f; struct ex_identity g;
    pid_t pid; int rc; struct ex_close eof;
    ex_init(&r,EX_E);
    if(!leaf_arguments(&r,argc,argv)) _exit(70);
    if(!leaf_startup(&r)) leaf_failure(&r,0);
    if(!ex_sub_get(&r,&r.child_sub[EX_E],0)) leaf_failure(&r,0);
    f=ex_frame_make(&r,EX_SUB,EX_EDGE_GE,EX_E); f.body.fact.key=EX_E;
    f.body.fact.fact=r.child_sub[EX_E]; if(!ex_emit(&r,&f)) leaf_failure(&r,0);
    if(!ex_capture((int)getpid(),&r.ids[EX_E]) || !ex_capture(r.ids[EX_G].pid,&g) ||
       !ex_same_identity(&g,&r.ids[EX_G],0) || !ex_alive(&g) ||
       r.ids[EX_E].ppid!=g.pid || r.ids[EX_E].uid!=g.uid || r.ids[EX_E].euid!=g.euid ||
       strcmp(r.ids[EX_E].boot,g.boot) || !ex_same_product(&r.ids[EX_E].product,&r.leaf_product)) {
        ex_fail(&r,EX_OP_PROC,errno,0,0); leaf_failure(&r,0);
    }
    r.stage=EX_POST; f=ex_frame_make(&r,EX_POST_READY,EX_EDGE_GE,0); f.body.identity=r.ids[EX_E];
    if(!ex_emit(&r,&f) || ex_command_read(&r,EX_CREATE,2,r.work,&f,0)!=1) leaf_failure(&r,0);
    r.d_authorized=1; r.stage=EX_CREATED;
    if(!ex_gate(&r,r.work,1) || !ex_pipe(&r,EX_CHILD_COMMAND_R,EX_CHILD_COMMAND_W,EX_CHILD) ||
       !ex_pipe(&r,EX_CHILD_REPORT_R,EX_CHILD_REPORT_W,EX_CHILD) || !ex_gate(&r,r.work,1)) leaf_failure(&r,0);
    errno=0; pid=fork();
    if(pid<0) { ex_fail(&r,EX_OP_FORK,errno,1,(int)pid); leaf_failure(&r,0); }
    if(!pid) descendant(&r);
    r.child=pid; r.created[1]=1;
    f=ex_frame_make(&r,EX_D_CREATED,EX_EDGE_GE,0); f.body.fact.key=EX_D;
    ex_fact_set(&r,&f.body.fact.fact,(int)pid,0,0); if(!ex_emit(&r,&f)) leaf_failure(&r,1);
    (void)ex_close_owned(&r,EX_CHILD_COMMAND_R,EX_CHILD,1);
    (void)ex_close_owned(&r,EX_CHILD_REPORT_W,EX_CHILD,1);
    if(r.error.observed || !ex_capture((int)pid,&r.ids[EX_D]) ||
       r.ids[EX_D].ppid!=r.ids[EX_E].pid ||
       !ex_same_product(&r.ids[EX_D].product,&r.leaf_product) ||
       !ex_handle_open(&r,EX_ED,&r.ids[EX_D]) || !leaf_relay(&r,EX_D_READY,r.work)) {
        ex_fail(&r,EX_OP_PROC,errno,0,0); leaf_failure(&r,1);
    }
    if(ex_command_read(&r,EX_ARM,3,r.work,&f,0)!=1 || !leaf_forward(&r,&f) ||
       !leaf_relay(&r,EX_ARM_ACK,r.work)) leaf_failure(&r,1);
    r.stage=EX_ARMED; f=ex_frame_make(&r,EX_ALL_ACK,EX_EDGE_GE,3);
    if(!ex_emit(&r,&f)) leaf_failure(&r,1);
    if(r.case_id==EX_LOSS) ex_park(&r,73);
    if(ex_command_read(&r,EX_FINISH,4,r.work,&f,0)!=1 || !leaf_forward(&r,&f) ||
       !leaf_relay(&r,EX_D_FINISH_ACK,r.terminal_end)) leaf_failure(&r,1);
    r.stage=EX_FINISH_STAGE;
    rc=ex_read_frame(&r,r.fd[EX_CHILD_REPORT_R],&f,r.terminal_end,1);
    if(rc!=0) { ex_fail(&r,EX_OP_FRAME,0,1,rc); leaf_failure(&r,1); }
    memset(&eof,0,sizeof(eof)); eof.owner=EX_D; eof.label=EX_CHILD_REPORT_W;
    eof.epoch=EX_CHILD; eof.fd=r.acquired_fd[EX_CHILD_REPORT_W];
    eof.evidence=EX_REPORT_EOF; ex_store_close(&r,&eof);
    if(!ex_pidfd_poll(&r,EX_ED,EX_TERMINAL,r.terminal_end,1) ||
       !ex_wait_child(&r,EX_ED,r.child,r.terminal_end) || r.waits[EX_ED].status!=0) {
        ex_fail(&r,EX_OP_WAIT,r.waits[EX_ED].err,1,r.waits[EX_ED].status); leaf_failure(&r,1);
    }
    if(!ex_handle_close(&r,EX_ED,1) ||
       !ex_close_owned(&r,EX_CHILD_COMMAND_W,EX_CHILD,1) ||
       !ex_close_owned(&r,EX_CHILD_REPORT_R,EX_CHILD,1) ||
       !ex_close_owned(&r,EX_COMMAND_R,EX_PREEXEC,1)) leaf_failure(&r,1);
    f=ex_frame_make(&r,EX_E_FINISH_ACK,EX_EDGE_GE,4);
    if(!ex_emit(&r,&f)) leaf_failure(&r,1);
    (void)ex_close_owned(&r,EX_REPORT_W,EX_PREEXEC,0); r.out=-1;
    _exit(r.error.observed?70:0);
}
