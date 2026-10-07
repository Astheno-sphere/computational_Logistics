#define _GNU_SOURCE
#include "frontier_v8_owned_c_exec_protocol.h"

static void json_number(int64_t n) { if(n>0) printf("%" PRIi64,n); else fputs("null",stdout); }
static void json_bool(int b) { fputs(b?"true":"false",stdout); }
static void json_string(const char *s) { /* All strings are closed names or validated hex. */
    putchar('"'); fputs(s,stdout); putchar('"');
}
static void json_fact(const struct ex_fact *f) {
    fputs("{\"attempted\":",stdout); json_bool(f->attempted);
    if(f->attempted) printf(",\"result\":%d,\"errno\":%d,\"value\":%d,\"observed_at_ns\":",f->result,f->err,f->value);
    else fputs(",\"result\":null,\"errno\":null,\"value\":null,\"observed_at_ns\":",stdout);
    json_number(f->attempted?f->at:0); putchar('}');
}
static void json_product(const struct ex_product *p) {
    printf("{\"dev\":%" PRIu64 ",\"ino\":%" PRIu64 ",\"size\":%" PRIu64
           ",\"mtime_ns\":%" PRIi64 ",\"ctime_ns\":%" PRIi64 "}",
           p->dev,p->ino,p->size,p->mtime_ns,p->ctime_ns);
}
static void json_identity(const struct ex_identity *id) {
    if(!id->known) { fputs("null",stdout); return; }
    printf("{\"pid\":%d,\"ppid\":%d,\"start_ticks\":%" PRIu64 ",\"boot_id\":",id->pid,id->ppid,id->start);
    json_string(id->boot); printf(",\"uid\":%" PRIu32 ",\"euid\":%" PRIu32 ",\"product_identity\":",id->uid,id->euid);
    json_product(&id->product); putchar('}');
}
static const char *handle_name(int key) { return key==EX_GE?"G_E":key==EX_GD?"G_D":"E_D"; }
static const char *epoch_name(int k) {
    return k==EX_PREEXEC?"preexec":k==EX_ENTRY?"exec_entry":k==EX_CHILD?"child_generation":"original_stdio";
}
static const char *poll_stage(int k) {
    return k==EX_INITIAL?"initial_live":k==EX_POST?"postexec_live":
        k==EX_ARMED?"armed_live":k==EX_TERMINAL?"terminal":"presignal_live";
}
static void json_poll(const struct ex_poll *q,int key) {
    int owner=key==EX_ED?EX_E:EX_G,target=key==EX_GE?EX_E:EX_D;
    fputs("{\"owner\":",stdout); json_string(ex_role_name(owner));
    fputs(",\"target\":",stdout); json_string(ex_role_name(target));
    fputs(",\"handle\":",stdout); json_string(handle_name(key));
    printf(",\"fd\":%d,\"stage\":",q->attempts?q->fd:-1); json_string(poll_stage(q->stage));
    printf(",\"attempts\":%d,\"requested_events\":%d",q->attempts,POLLIN);
    if(q->attempts) printf(",\"result\":%d,\"revents\":%d,\"errno\":%d,\"observed_at_ns\":",q->result,q->revents,q->err);
    else fputs(",\"result\":null,\"revents\":null,\"errno\":null,\"observed_at_ns\":",stdout);
    json_number(q->attempts?q->at:0); putchar('}');
}
static void json_wait(const struct ex_wait *w,int key) {
    fputs("{\"owner\":",stdout); json_string(ex_role_name(key==EX_ED?EX_E:EX_G));
    fputs(",\"target\":",stdout); json_string(ex_role_name(key==EX_GE?EX_E:EX_D));
    printf(",\"pid\":%d,\"attempts\":%d",w->attempts?w->pid:-1,w->attempts);
    if(w->attempts) {
        printf(",\"result\":%d,\"raw_status\":",w->result);
        if(w->result==w->pid && w->pid>0) printf("%d",w->status); else fputs("null",stdout);
        printf(",\"errno\":%d,\"observed_at_ns\":",w->err);
    } else fputs(",\"result\":null,\"raw_status\":null,\"errno\":null,\"observed_at_ns\":",stdout);
    json_number(w->attempts?w->at:0); putchar('}');
}
static void json_role_set(const int set[2]) {
    int comma=0; putchar('[');
    if(set[0]) { json_string("worker"); comma=1; }
    if(set[1]) { if(comma) putchar(','); json_string("descendant"); } putchar(']');
}
static void json_headers(void) {
    printf("{\"pidfd_open\":%ld,\"pidfd_send_signal\":%ld,\"pr_set_child_subreaper\":%ld,\"pr_get_child_subreaper\":%ld,",
        (long)SYS_pidfd_open,(long)SYS_pidfd_send_signal,(long)PR_SET_CHILD_SUBREAPER,(long)PR_GET_CHILD_SUBREAPER);
    printf("\"SIGKILL\":%d,\"SIGPIPE\":%d,\"POLLIN\":%d,\"POLLNVAL\":%d,\"F_GETFD\":%d,\"F_SETFD\":%d,\"F_DUPFD_CLOEXEC\":%d,",
        SIGKILL,SIGPIPE,POLLIN,POLLNVAL,F_GETFD,F_SETFD,F_DUPFD_CLOEXEC);
    printf("\"FD_CLOEXEC\":%d,\"O_CLOEXEC\":%d,\"O_NOFOLLOW\":%d,\"O_NONBLOCK\":%d,\"F_GETFL\":%d,\"F_SETFL\":%d,\"EBADF\":%d,\"PIPE_BUF\":%d,",
        FD_CLOEXEC,O_CLOEXEC,O_NOFOLLOW,O_NONBLOCK,F_GETFL,F_SETFL,EBADF,PIPE_BUF);
    printf("\"target_int_bytes\":%zu,\"target_long_bytes\":%zu,\"target_pointer_bytes\":%zu,\"target_char_bits\":%d,\"target_byte_order\":%d,",
        sizeof(int),sizeof(long),sizeof(void *),CHAR_BIT,__BYTE_ORDER__);
    printf("\"pid_t_bytes\":%zu,\"uid_t_bytes\":%zu,\"pid_t_signed\":true,\"uid_t_signed\":false,\"uint64_bytes\":%zu,\"int64_bytes\":%zu,",
        sizeof(pid_t),sizeof(uid_t),sizeof(uint64_t),sizeof(int64_t));
    printf("\"pid_representation\":\"signed32\",\"uid_representation\":\"unsigned32\",\"uint64_representation\":\"unsigned64\",\"int64_representation\":\"signed64\",\"pid_max\":%d,\"uid_max\":%" PRIu32 ",\"uint64_max\":%" PRIu64 ",\"int64_min\":%" PRIi64 ",\"int64_max\":%" PRIi64 "}",
        INT32_MAX,UINT32_MAX,UINT64_MAX,INT64_MIN,INT64_MAX);
}
static void json_result(const struct ex_context *r) {
    int k,j,unknown[2]; const struct ex_fact absent={0};
    static const char *sub_names[]={"initial_get","set_one","get_one","reset_zero","final_get"};
    static const char *check_names[]={"preexec","postexec","armed_worker","armed_descendant","presignal_worker","presignal_descendant","guardian_before_descendant_signal"};
    static const char *time_names[]={"initial","preexec_ready","exec_sent","exec_entered","postexec_ready","postexec_validated","create_D_sent","D_ready","all_bound","arm_sent","all_arm_ack","primary","finish_sent","E_signal","E_terminal","E_reaped","D_adopted","D_signal","D_terminal","D_reaped","FD_complete","reset","final"};
    static const char *evidence[]={"explicit_once_close","exec_entry_closed","parent_report_EOF","owner_death","original_absent","unreturned_loss_close"};
    fputs("{\"schema_version\":1,\"scope\":\"frontier_v8_owned_C_fixed_exec_descendant_CPU_fixture\",\"case\":",stdout);
    json_string(r->case_id==EX_LOSS?"worker_loss":"normal"); fputs(",\"fault\":",stdout);
    json_string(r->fault==EX_CLOSED_EXEC?"exec_fd_closed":r->fault==EX_LEAK_WITNESS?"witness_cloexec_cleared":"none");
    fputs(",\"nonce\":",stdout); json_string(r->nonce); fputs(",\"status\":",stdout);
    json_string(r->success?"success":r->error.observed?"failed":"unknown");
    fputs(",\"error\":{\"stage\":",stdout); json_string(r->error.observed?ex_stage_name(r->error.stage):"none");
    fputs(",\"role\":",stdout); if(r->error.observed) json_string(ex_role_name(r->error.role)); else fputs("null",stdout);
    fputs(",\"operation\":",stdout); if(r->error.observed) json_string(ex_op_name(r->error.operation)); else fputs("null",stdout);
    if(r->error.observed) printf(",\"errno\":%d,\"result\":",r->error.err); else fputs(",\"errno\":null,\"result\":",stdout);
    if(r->error.observed && r->error.result_known) printf("%d",r->error.result); else fputs("null",stdout);
    fputs(",\"observed_at_ns\":",stdout); json_number(r->error.observed?r->error.at:0); fputs("},\"headers\":",stdout); json_headers();
    fputs(",\"products\":{\"guardian\":",stdout); json_product(&r->guardian_product); fputs(",\"leaf\":",stdout); json_product(&r->leaf_product);
    fputs("},\"subreaper\":{",stdout);
    for(k=0;k<5;k++) { if(k) putchar(','); json_string(sub_names[k]); putchar(':'); json_fact(&r->sub[k]); }
    fputs("},\"child_subreaper_get\":{",stdout);
    for(k=EX_X;k<=EX_D;k++) { if(k>EX_X) putchar(','); json_string(ex_role_name(k)); putchar(':'); json_fact(&r->child_sub[k]); }
    fputs("},\"local_sigpipe\":{",stdout);
    for(k=EX_G;k<=EX_D;k++) {
        if(k==EX_X) continue; if(k!=EX_G) putchar(','); json_string(ex_role_name(k));
        fputs(":{\"query\":",stdout); json_fact(&r->sigpipe[k][0]); fputs(",\"set_ignore\":",stdout); json_fact(&r->sigpipe[k][1]); putchar('}');
    }
    fputs("},\"identities_initial\":{",stdout);
    for(k=0;k<EX_ROLES;k++) { if(k) putchar(','); json_string(ex_role_name(k)); putchar(':'); json_identity(&r->ids[k]); }
    fputs("},\"identity_rechecks\":{",stdout);
    for(k=0;k<7;k++) { if(k) putchar(','); json_string(check_names[k]); putchar(':'); json_identity(&r->checks[k]); }
    fputs("},\"exec_protocol\":{\"attempted\":",stdout); json_bool(r->exec_attempted);
    fputs(",\"entered_at_ns\":",stdout); json_number(r->exec_attempted?r->exec_enter:0); fputs(",\"returned\":",stdout); json_bool(r->exec_returned);
    if(r->exec_returned) printf(",\"result\":%d,\"errno\":%d",r->exec_result,r->exec_errno); else fputs(",\"result\":null,\"errno\":null",stdout);
    fputs(",\"error_pipe_eof_at_ns\":",stdout); json_number(r->error_eof);
    fputs(",\"startup_closed\":{",stdout);
    for(k=0;k<3;k++) { if(k) putchar(','); json_string(ex_label_name(r->startup[k].label)); printf(":{\"fd\":%d,\"fact\":",r->startup[k].fd); json_fact(&r->startup[k].fact); putchar('}'); }
    fputs("},\"startup_private\":{",stdout);
    for(k=3;k<5;k++) { if(k>3) putchar(','); json_string(ex_label_name(r->startup[k].label)); printf(":{\"fd\":%d,\"fact\":",r->startup[k].fd); json_fact(&r->startup[k].fact); putchar('}'); }
    fputs("},\"original_stdio\":{",stdout);
    for(k=EX_E;k<=EX_D;k++) {
        if(k>EX_E) putchar(','); json_string(ex_role_name(k)); fputs(":[",stdout);
        for(j=0;j<3;j++) { if(j) putchar(','); printf("{\"fd\":%d,\"fact\":",j); json_fact(&absent); putchar('}'); } putchar(']');
    }
    fputs("}},\"adoptions\":[",stdout);
    if(r->adoption.known) {
        printf("{\"target\":\"descendant\",\"old_parent\":%d,\"new_parent\":%d,\"identity\":",r->ids[EX_E].pid,r->ids[EX_G].pid);
        json_identity(&r->adoption); fputs(",\"guardian_identity\":",stdout); json_identity(&r->adoption_guardian);
        fputs(",\"observed_at_ns\":",stdout); json_number(r->adoption_at); putchar('}');
    }
    fputs("],\"pidfds\":{",stdout);
    for(k=0;k<EX_HANDLES;k++) {
        const struct ex_handle *h=&r->handles[k];
        if(k) putchar(','); json_string(handle_name(k)); fputs(":{\"owner\":",stdout); json_string(ex_role_name(k==EX_ED?EX_E:EX_G));
        fputs(",\"target\":",stdout); json_string(ex_role_name(k==EX_GE?EX_E:EX_D)); printf(",\"fd\":%d,\"open\":",h->known?h->fd:-1); json_fact(&h->open);
        fputs(",\"identity_before\":",stdout); json_identity(&h->before); fputs(",\"identity_after\":",stdout); json_identity(&h->after);
        fputs(",\"fdinfo_pid\":",stdout); if(h->matches) printf("%d",h->fdi_pid); else fputs("null",stdout);
        fputs(",\"fdinfo_matches\":",stdout); json_bool(h->matches); fputs(",\"cloexec\":",stdout); json_fact(&h->flags);
        fputs(",\"initial_live\":",stdout); json_poll(&h->live,k); fputs(",\"close\":",stdout); json_fact(&h->close);
        fputs(",\"F_GETFD_after_close\":",stdout); json_fact(&h->badfd); fputs(",\"owner_death_teardown\":",stdout); json_bool(h->kernel); putchar('}');
    }
    fputs("},\"polls\":[",stdout); for(k=0;k<r->npolls;k++) { if(k) putchar(','); json_poll(&r->polls[k],r->polls[k].key); }
    fputs("],\"waits\":{",stdout);
    for(k=0;k<EX_HANDLES;k++) { if(k) putchar(','); json_string(handle_name(k)); putchar(':'); json_wait(&r->waits[k],k); }
    fputs("},\"signals\":{",stdout);
    for(k=0;k<2;k++) {
        const struct ex_signal *s=&r->signals[k];
        if(k) putchar(','); json_string(handle_name(k)); fputs(":{\"owner\":\"guardian\",\"target\":",stdout); json_string(ex_role_name(k==EX_GE?EX_E:EX_D));
        printf(",\"budget\":%d,\"consumed\":",r->case_id==EX_LOSS?1:0); json_bool(s->consumed);
        printf(",\"attempts\":%d,\"fd\":%d,\"signal\":%d,\"flags\":0",s->attempts,r->handles[k].known?r->handles[k].fd:-1,SIGKILL);
        if(s->attempts) printf(",\"result\":%d,\"errno\":%d,\"observed_at_ns\":",s->result,s->err); else fputs(",\"result\":null,\"errno\":null,\"observed_at_ns\":",stdout);
        json_number(s->at); fputs(",\"presignal_identity\":",stdout); json_identity(&s->before); putchar('}');
    }
    fputs("},\"fd_ledger\":[",stdout);
    for(k=0;k<r->ncloses;k++) {
        const struct ex_close *c=&r->closes[k]; if(k) putchar(','); fputs("{\"owner\":",stdout); json_string(ex_role_name(c->owner));
        fputs(",\"label\":",stdout); json_string(ex_label_name(c->label)); fputs(",\"epoch\":",stdout); json_string(epoch_name(c->epoch));
        printf(",\"fd\":%d,\"evidence\":",c->fd); json_string(evidence[c->evidence]); fputs(",\"close\":",stdout); json_fact(&c->close);
        fputs(",\"F_GETFD_after_close\":",stdout); json_fact(&c->badfd); putchar('}');
    }
    fputs("],\"fd_flags\":[",stdout);
    for(k=0;k<r->nflags;k++) {
        const struct ex_flags *v=&r->flags[k]; if(k) putchar(','); fputs("{\"owner\":",stdout); json_string(ex_role_name(v->owner));
        fputs(",\"label\":",stdout); json_string(ex_label_name(v->label)); fputs(",\"epoch\":",stdout); json_string(epoch_name(v->epoch));
        printf(",\"fd\":%d,\"F_GETFD_before\":",v->fd); json_fact(&v->before); fputs(",\"F_SETFD\":",stdout); json_fact(&v->set);
        fputs(",\"F_GETFD_after\":",stdout); json_fact(&v->after); fputs(",\"F_GETFL\":",stdout); json_fact(&v->getfl); putchar('}');
    }
    fputs("],\"packets\":[",stdout);
    for(k=0;k<r->npackets;k++) {
        const struct ex_packet *p=&r->packets[k]; if(k) putchar(','); fputs("{\"source\":",stdout); json_string(ex_role_name(p->source));
        fputs(",\"transport\":",stdout); json_string(ex_role_name(p->transport)); fputs(",\"edge\":",stdout);
        json_string(p->edge==EX_EDGE_GE?"G_E":p->edge==EX_EDGE_ED?"E_D":"exec_error"); fputs(",\"direction\":",stdout); json_string(p->outgoing?"command":"report");
        fputs(",\"kind\":",stdout); json_string(ex_kind_name(p->kind));
        printf(",\"sequence\":%d,\"aux\":%d,\"sent_at_ns\":%" PRIi64 ",\"observed_at_ns\":%" PRIi64 ",\"shared_t0_ns\":%" PRIi64 ",\"bytes\":%zu,\"PIPE_BUF_bound\":%d,\"forwarded_original\":",
            p->seq,p->aux,p->sent,p->observed,r->t0,sizeof(struct ex_frame),r->pipebuf); json_bool(p->forwarded); putchar('}');
    }
    fputs("],\"command_forwards\":[",stdout);
    for(k=0;k<r->nforwards;k++) {
        if(k) putchar(','); fputs("{\"owner\":\"worker\",\"kind\":",stdout); json_string(ex_kind_name(r->forwards[k].kind));
        printf(",\"original_sequence\":%d,\"observed_at_ns\":%" PRIi64 "}",r->forwards[k].original_seq,r->forwards[k].at);
    }
    printf("],\"deadlines\":{\"t0_ns\":%" PRIi64 ",\"work_ns\":%" PRIi64 ",\"cleanup_ns\":%" PRIi64 ",\"terminal_ns\":%" PRIi64 ",\"Gtotal_ns\":%" PRIi64 ",\"child_expiry_ns\":%" PRIi64 "},\"times_ns\":{",
        r->t0,r->work,r->cleanup,r->terminal_end,r->total,r->expiry);
    for(k=0;k<EX_TIMES;k++) { if(k) putchar(','); json_string(time_names[k]); putchar(':'); json_number(r->times[k]); }
    fputs("},\"controls\":{\"functional_containment_verified\":false,\"containment_available\":false,\"execution_available\":false,\"resource_authority\":false,\"model_runtime_ABI_observed\":false,\"production_controller_guard_completed\":false,\"GPU_or_foreign_restore\":false,\"fixed_exec_transition_verified\":",stdout);
    json_bool(r->success); fputs(",\"normal_reap_verified\":",stdout); json_bool(r->success && r->case_id==EX_NORMAL);
    fputs(",\"worker_loss_adoption_verified\":",stdout); json_bool(r->success && r->case_id==EX_LOSS);
    fputs("},\"negative_state\":{\"created\":",stdout); json_role_set(r->created); fputs(",\"bound\":",stdout); json_role_set(r->bound);
    fputs(",\"adopted\":",stdout); json_role_set(r->adopted); fputs(",\"terminal\":",stdout); json_role_set(r->terminal);
    fputs(",\"reaped\":",stdout); json_role_set(r->reaped);
    unknown[0]=r->created[0] && !r->reaped[0]; unknown[1]=(r->created[1] || r->d_authorized) && !r->reaped[1];
    fputs(",\"unknown\":",stdout); json_role_set(unknown); fputs(",\"descendant_creation_authorized\":",stdout); json_bool(r->d_authorized);
    fputs(",\"descendant_creation_observed\":",stdout); json_bool(r->created[1]); fputs(",\"negative_cleanup_signal_attempts\":0}}\n",stdout);
}

static void guardian_error_frame(struct ex_context *r,const struct ex_frame *f) {
    if(f->kind==EX_EXEC_ERROR && (f->source!=EX_X || !f->body.error.observed ||
       f->body.error.role!=EX_X || f->body.error.stage!=EX_EXEC_STAGE ||
       f->body.error.operation!=EX_OP_EXEC || !f->body.error.result_known)) {
        ex_fail(r,EX_OP_FRAME,0,0,0); return;
    }
    if(f->body.error.observed && !r->error.observed) r->error=f->body.error;
    else if(!f->body.error.observed) ex_fail(r,EX_OP_FRAME,0,0,0);
    if(f->kind==EX_EXEC_ERROR) {
        r->exec_attempted=1; r->exec_returned=1;
        r->exec_result=f->body.error.result; r->exec_errno=f->body.error.err;
        if(r->exec_enter) r->times[EX_T_EXEC_ENTER]=r->exec_enter;
    }
}
static int guardian_accept(struct ex_context *r,const struct ex_frame *f) {
    int source=f->source,edge=f->edge;
    if(source==EX_G || (source==EX_D?edge!=EX_EDGE_ED:
        (edge!=EX_EDGE_GE && !(source==EX_X && edge==EX_EDGE_ERROR))) ||
       f->seq!=r->incoming[source][edge]+1 || f->at<r->incoming_at[source][edge]) {
        ex_fail(r,EX_OP_SEQUENCE,0,0,0); return 0;
    }
    r->incoming[source][edge]=f->seq; r->incoming_at[source][edge]=f->at;
    ex_packet(r,f,source==EX_D?EX_E:source,0,source==EX_D);
    switch(f->kind) {
    case EX_PRE_READY:
        if(source!=EX_X || r->ids[EX_X].known ||
           !ex_same_product(&f->body.identity.product,&r->guardian_product) ||
           f->body.identity.ppid!=r->ids[EX_G].pid) break;
        r->ids[EX_X]=f->body.identity; r->times[EX_T_PRE_READY]=r->last; return 1;
    case EX_ENTER:
        if(source!=EX_X || !r->times[EX_T_EXEC_SENT] || f->body.forward.kind!=EX_EXEC ||
           f->body.forward.original_seq!=1 || f->body.forward.at>=r->work) break;
        /* This marker precedes the final gate and is not proof of a call. */
        r->exec_enter=f->body.forward.at;
        if(r->exec_attempted) r->times[EX_T_EXEC_ENTER]=r->exec_enter;
        return 1;
    case EX_POST_READY:
        if(source!=EX_E || r->ids[EX_E].known || !r->error_eof ||
           !ex_same_process(&r->ids[EX_X],&f->body.identity,0) ||
           !ex_same_product(&f->body.identity.product,&r->leaf_product)) break;
        r->ids[EX_E]=f->body.identity; r->times[EX_T_POST_READY]=r->last; return 1;
    case EX_D_CREATED:
        if(source!=EX_E || !r->d_authorized || r->created[1] ||
           !f->body.fact.fact.attempted || f->body.fact.fact.result<=0 || f->body.fact.fact.err) break;
        r->created[1]=1; return 1;
    case EX_D_READY:
        if(source!=EX_D || !r->created[1] || r->ids[EX_D].known ||
           f->body.identity.ppid!=r->ids[EX_E].pid ||
           !ex_same_product(&f->body.identity.product,&r->leaf_product)) break;
        r->ids[EX_D]=f->body.identity; r->times[EX_T_D_READY]=r->last; return 1;
    case EX_HANDLE: {
        const struct ex_handle_wire *w=&f->body.handle; struct ex_handle *h=&r->handles[EX_ED];
        if(source!=EX_E || w->key!=EX_ED || h->known || !r->created[1] ||
           w->fd<0 || !w->matches || !ex_same_identity(&w->before,&w->after,0) ||
           w->before.ppid!=r->ids[EX_E].pid || !ex_same_product(&w->before.product,&r->leaf_product)) break;
        h->known=1; h->key=EX_ED; h->fd=w->fd; h->fdi_pid=w->fdi_pid; h->matches=w->matches;
        h->open=w->open; h->flags=w->flags; h->before=w->before; h->after=w->after; h->live=w->live;
        return 1;
    }
    case EX_FD_CLOSE: {
        const struct ex_close *c=&f->body.close;
        if(c->owner<EX_X || c->owner>EX_D || c->label<0 || c->label>=EX_FDS ||
           c->epoch<EX_PREEXEC || c->epoch>EX_STDIO || c->evidence<EX_EXPLICIT || c->evidence>EX_UNRETURNED ||
           (c->owner!=source && !(source==EX_E && c->owner==EX_D && c->evidence==EX_REPORT_EOF))) break;
        ex_store_close(r,c);
        if(c->owner==EX_E && c->label==EX_ED_FD && c->evidence==EX_EXPLICIT) {
            r->handles[EX_ED].close=c->close; r->handles[EX_ED].badfd=c->badfd;
        }
        return 1;
    }
    case EX_FD_FLAGS:
        if(f->body.flags.owner!=source || f->body.flags.label<0 || f->body.flags.label>=EX_FDS) break;
        ex_store_flags(r,&f->body.flags); return 1;
    case EX_SUB:
        if(f->body.fact.key!=source || source==EX_G) break;
        r->child_sub[source]=f->body.fact.fact; return 1;
    case EX_SIGPIPE:
        if((source!=EX_E && source!=EX_D) || f->body.fact.key<0 || f->body.fact.key>1) break;
        r->sigpipe[source][f->body.fact.key]=f->body.fact.fact; return 1;
    case EX_STARTUP:
        if(source!=EX_E || f->aux<0 || f->aux>=5 ||
           f->body.startup.label!=r->startup[f->aux].label ||
           f->body.startup.fd!=r->startup[f->aux].fd) break;
        r->startup[f->aux]=f->body.startup; return 1;
    case EX_POLL:
        if(source!=EX_E || f->body.poll.key!=EX_ED || f->body.poll.owner!=EX_E ||
           f->body.poll.target!=EX_D || r->npolls>=EX_MAX) break;
        r->polls[r->npolls++]=f->body.poll;
        if(f->body.poll.stage==EX_TERMINAL && f->body.poll.result>0 && (f->body.poll.revents&POLLIN)) {
            r->terminal[1]=1; r->times[EX_T_D_TERM]=f->body.poll.at;
        }
        return 1;
    case EX_WAIT:
        if(source!=EX_E || f->aux!=EX_ED || r->case_id!=EX_NORMAL ||
           f->body.wait.owner!=EX_E || f->body.wait.target!=EX_D ||
           f->body.wait.pid!=r->ids[EX_D].pid || r->waits[EX_ED].attempts) break;
        r->waits[EX_ED]=f->body.wait;
        if(f->body.wait.result==r->ids[EX_D].pid) { r->terminal[1]=1; r->reaped[1]=1; }
        r->times[EX_T_D_REAP]=f->body.wait.at; return 1;
    case EX_FORWARD:
        if(source!=EX_E || r->nforwards>=8 ||
           !((f->body.forward.kind==EX_ARM && f->body.forward.original_seq==3) ||
             (f->body.forward.kind==EX_FINISH && f->body.forward.original_seq==4)) ||
           f->body.forward.at>=r->work) break;
        r->forwards[r->nforwards++]=f->body.forward; return 1;
    case EX_ARM_ACK:
        if(source!=EX_D || !r->times[EX_T_ARM] || f->aux!=3) break;
        return 1;
    case EX_ALL_ACK:
        if(source!=EX_E || !r->times[EX_T_ARM] || f->aux!=3) break;
        r->times[EX_T_ALL_ACK]=r->last; return 1;
    case EX_D_FINISH_ACK:
        if(source!=EX_D || r->case_id!=EX_NORMAL || !r->times[EX_T_FINISH] || f->aux!=4) break;
        return 1;
    case EX_E_FINISH_ACK:
        if(source!=EX_E || r->case_id!=EX_NORMAL || !r->times[EX_T_FINISH] || f->aux!=4) break;
        return 1;
    case EX_ERROR: case EX_EXEC_ERROR:
        guardian_error_frame(r,f); return 1;
    case EX_PRODUCT: {
        int index=f->body.product.label==EX_LEAF_FD?0:f->body.product.label==EX_WITNESS_FD?1:-1;
        if(source!=EX_X || index<0 || r->product_checked[index] ||
           !ex_same_product(&f->body.product.product,&r->leaf_product)) break;
        r->product_checks[index]=f->body.product; r->product_checked[index]=1; return 1;
    }
    default: break;
    }
    ex_fail(r,EX_OP_FRAME,0,0,0); return 0;
}
static int guardian_receive(struct ex_context *r,int kind,int source,int64_t end) {
    struct ex_frame f; int rc;
    while(!r->error.observed) {
        rc=ex_read_frame(r,r->fd[EX_REPORT_R],&f,end,0);
        if(rc!=1 || !guardian_accept(r,&f) || r->error.observed) return 0;
        if(f.kind==kind && f.source==source) return 1;
        if(f.kind==EX_PRE_READY || f.kind==EX_POST_READY || f.kind==EX_D_READY ||
           f.kind==EX_ALL_ACK || f.kind==EX_E_FINISH_ACK) {
            ex_fail(r,EX_OP_STATE,0,0,0); return 0;
        }
    }
    return 0;
}
static int guardian_command(struct ex_context *r,int kind,int time_key) {
    struct ex_frame f;
    if(!ex_gate(r,r->work,1)) return 0;
    f=ex_frame_make(r,kind,EX_EDGE_GE,0);
    f.body.command.worker=kind==EX_EXEC?r->ids[EX_X]:r->ids[EX_E];
    f.body.command.descendant=r->ids[EX_D];
    if(!ex_write_frame(r,r->fd[EX_COMMAND_W],&f,r->work,1)) return 0;
    ex_packet(r,&f,EX_G,1,0); r->times[time_key]=f.at;
    return !r->error.observed;
}
static int good_get0(const struct ex_fact *f) { return f->attempted && !f->result && !f->err && f->value==0; }
static int guardian_pre_gate(struct ex_context *r) {
    struct ex_identity id;
    if(!good_get0(&r->child_sub[EX_X]) || !r->product_checked[0] || !r->product_checked[1] ||
       !ex_capture(r->child,&id) || !ex_same_identity(&id,&r->ids[EX_X],0) || !ex_alive(&id) ||
       id.uid!=r->ids[EX_G].uid || id.euid!=r->ids[EX_G].euid || strcmp(id.boot,r->ids[EX_G].boot)) {
        ex_fail(r,EX_OP_PROC,errno,0,0); return 0;
    }
    r->checks[0]=id;
    if(!ex_handle_open(r,EX_GE,&id)) return 0;
    r->bound[0]=1; return ex_gate(r,r->work,1);
}
static int guardian_post_gate(struct ex_context *r) {
    int k,pid; struct ex_identity id;
    if(!r->exec_enter || r->exec_returned || !r->error_eof || !good_get0(&r->child_sub[EX_E])) {
        ex_fail(r,EX_OP_STATE,0,0,0); return 0;
    }
    for(k=0;k<5;k++) {
        const struct ex_fact *f=&r->startup[k].fact;
        if(!f->attempted || (k<3?(f->result!=-1 || f->err!=EBADF):(f->result<0 || f->err || (f->result&FD_CLOEXEC)))) {
            ex_fail(r,EX_OP_STARTUP,f->err,1,f->result); return 0;
        }
        if(k<3) {
            struct ex_close c; memset(&c,0,sizeof(c)); c.owner=EX_E;
            c.label=r->startup[k].label; c.epoch=EX_ENTRY; c.fd=r->startup[k].fd;
            c.evidence=EX_ENTRY_CLOSED; c.badfd=*f; ex_store_close(r,&c);
        }
    }
    if(!ex_capture(r->child,&id) || !ex_same_identity(&id,&r->ids[EX_E],0) ||
       !ex_same_process(&id,&r->ids[EX_X],0) || !ex_alive(&id) ||
       !ex_fdinfo(r->handles[EX_GE].fd,&pid) || pid!=id.pid ||
       !ex_pidfd_poll(r,EX_GE,EX_POST,r->work,0)) {
        ex_fail(r,EX_OP_PROC,errno,0,0); return 0;
    }
    /* The independently observed fixed leaf transition proves execution. */
    r->exec_attempted=1; r->times[EX_T_EXEC_ENTER]=r->exec_enter;
    r->checks[1]=id; r->times[EX_T_POST_VALID]=ex_now(r);
    return ex_gate(r,r->work,1);
}
static int guardian_live(struct ex_context *r,int before_signal) {
    struct ex_identity e,d;
    if(!ex_capture(r->ids[EX_E].pid,&e) || !ex_capture(r->ids[EX_D].pid,&d) ||
       !ex_same_identity(&e,&r->ids[EX_E],0) || !ex_same_identity(&d,&r->ids[EX_D],0) ||
       !ex_alive(&e) || !ex_alive(&d) || d.ppid!=e.pid ||
       !ex_pidfd_poll(r,EX_GE,before_signal?EX_LOSS_STAGE:EX_ARMED,r->work,0) ||
       !ex_pidfd_poll(r,EX_GD,before_signal?EX_LOSS_STAGE:EX_ARMED,r->work,0)) {
        ex_fail(r,EX_OP_PROC,errno,0,0); return 0;
    }
    r->checks[before_signal?4:2]=e;
    if(!before_signal) r->checks[3]=d;
    return ex_gate(r,r->work,1);
}
static int guardian_adopt(struct ex_context *r) {
    struct ex_identity d,g; struct timespec pause={0,INT64_C(1000000)};
    r->stage=EX_ADOPT;
    while(ex_gate(r,r->cleanup,1)) {
        if(!ex_capture(r->ids[EX_G].pid,&g) || !ex_same_identity(&g,&r->ids[EX_G],0) || !ex_alive(&g) ||
           !ex_capture(r->ids[EX_D].pid,&d) || !ex_same_identity(&d,&r->ids[EX_D],1) || !ex_alive(&d)) {
            ex_fail(r,EX_OP_ADOPT,errno,0,0); return 0;
        }
        if(d.ppid==g.pid) {
            r->adoption=d; r->adoption_guardian=g; r->adoption_at=ex_now(r);
            r->adopted[1]=1; r->times[EX_T_ADOPT]=r->adoption_at;
            return ex_gate(r,r->cleanup,1);
        }
        if(d.ppid!=r->ids[EX_E].pid) { ex_fail(r,EX_OP_ADOPT,0,0,0); return 0; }
        errno=0; if(nanosleep(&pause,NULL)) { ex_fail(r,EX_OP_ADOPT,errno,1,-1); return 0; }
    }
    return 0;
}
static int guardian_signal(struct ex_context *r,int key) {
    struct ex_signal *s=&r->signals[key]; struct ex_identity d,g; int rc,err; int64_t end;
    if(r->case_id!=EX_LOSS || r->fault!=EX_NOFAULT || s->consumed || r->error.observed) {
        ex_fail(r,EX_OP_STATE,0,0,0); return 0;
    }
    end=key==EX_GE?r->work:r->cleanup;
    if(key==EX_GE) {
        if(!guardian_live(r,1)) return 0; s->before=r->checks[4];
    } else {
        if(!r->adopted[1] || !r->reaped[0] || r->waits[EX_GE].status!=9 ||
           !ex_capture(r->ids[EX_G].pid,&g) || !ex_same_identity(&g,&r->ids[EX_G],0) || !ex_alive(&g) ||
           !ex_capture(r->ids[EX_D].pid,&d) || !ex_same_identity(&d,&r->ids[EX_D],1) ||
           d.ppid!=g.pid || !ex_alive(&d) || !ex_pidfd_poll(r,EX_GD,EX_LOSS_STAGE,end,0)) {
            ex_fail(r,EX_OP_ADOPT,errno,0,0); return 0;
        }
        r->checks[5]=d; r->checks[6]=g; s->before=d;
    }
    if(!ex_gate(r,end,1)) return 0;
    s->consumed=1; s->attempts=1; s->fd=r->handles[key].fd; s->at=r->last;
    errno=0; rc=(int)syscall((long)SYS_pidfd_send_signal,(long)s->fd,(long)SIGKILL,NULL,(unsigned long)0); err=errno;
    s->result=rc; s->err=err;
    if(rc || err) ex_fail(r,EX_OP_SIGNAL,err,1,rc);
    r->times[key==EX_GE?EX_T_E_SIGNAL:EX_T_D_SIGNAL]=s->at;
    return !r->error.observed && ex_gate(r,end,0);
}
static int guardian_wait(struct ex_context *r,int key,int64_t end,int expected) {
    int slot=key==EX_GE?0:1,pid=key==EX_GE?r->child:r->ids[EX_D].pid;
    if(key==EX_GD && !r->adopted[1]) { ex_fail(r,EX_OP_WAIT,0,0,0); return 0; }
    if(!ex_pidfd_poll(r,key,EX_TERMINAL,end,1)) return 0;
    r->terminal[slot]=1;
    r->times[key==EX_GE?EX_T_E_TERM:EX_T_D_TERM]=r->polls[r->npolls-1].at;
    if(!ex_wait_child(r,key,pid,end)) return 0;
    r->reaped[slot]=1; r->times[key==EX_GE?EX_T_E_REAP:EX_T_D_REAP]=r->waits[key].at;
    if(r->waits[key].status!=expected) { ex_fail(r,EX_OP_WAIT,0,1,r->waits[key].status); return 0; }
    return !r->error.observed;
}
static void guardian_eof_ledger(struct ex_context *r,int owner,int label,int epoch,int fd,int evidence) {
    struct ex_close c; memset(&c,0,sizeof(c)); c.owner=owner; c.label=label;
    c.epoch=epoch; c.fd=fd; c.evidence=evidence; ex_store_close(r,&c);
}
static int guardian_report_eof(struct ex_context *r,int owner,int64_t end) {
    struct ex_frame f; int rc=ex_read_frame(r,r->fd[EX_REPORT_R],&f,end,1);
    if(rc!=0) { ex_fail(r,EX_OP_FRAME,0,1,rc); return 0; }
    guardian_eof_ledger(r,owner,EX_REPORT_W,EX_PREEXEC,r->acquired_fd[EX_REPORT_W],
        r->case_id==EX_LOSS && owner==EX_E?EX_OWNER_DEATH:EX_REPORT_EOF);
    return !r->error.observed;
}
static int guardian_foreign_fd(const struct ex_context *r,int owner,int label) {
    int k; for(k=r->nflags-1;k>=0;k--) if(r->flags[k].owner==owner && r->flags[k].label==label)
        return r->flags[k].fd;
    return -1;
}
static void guardian_loss_ledger(struct ex_context *r) {
    r->handles[EX_ED].kernel=1;
    guardian_eof_ledger(r,EX_E,EX_ED_FD,EX_CHILD,r->handles[EX_ED].fd,EX_OWNER_DEATH);
    guardian_eof_ledger(r,EX_E,EX_COMMAND_R,EX_PREEXEC,r->acquired_fd[EX_COMMAND_R],EX_OWNER_DEATH);
    guardian_eof_ledger(r,EX_E,EX_CHILD_COMMAND_W,EX_CHILD,guardian_foreign_fd(r,EX_E,EX_CHILD_COMMAND_W),EX_OWNER_DEATH);
    guardian_eof_ledger(r,EX_E,EX_CHILD_REPORT_R,EX_CHILD,guardian_foreign_fd(r,EX_E,EX_CHILD_REPORT_R),EX_OWNER_DEATH);
    guardian_eof_ledger(r,EX_D,EX_CHILD_COMMAND_R,EX_CHILD,guardian_foreign_fd(r,EX_D,EX_CHILD_COMMAND_R),EX_UNRETURNED);
    guardian_eof_ledger(r,EX_D,EX_CHILD_REPORT_W,EX_CHILD,guardian_foreign_fd(r,EX_D,EX_CHILD_REPORT_W),EX_UNRETURNED);
}
static int guardian_close_all(struct ex_context *r) {
    int k;
    (void)ex_handle_close(r,EX_GE,1); (void)ex_handle_close(r,EX_GD,1);
    for(k=0;k<EX_STD0;k++) if(k!=EX_GE_FD && k!=EX_GD_FD && k!=EX_ED_FD)
        (void)ex_close_owned(r,k,EX_PREEXEC,1);
    for(k=0;k<EX_STD0;k++) if(r->fd[k]>=0) return 0;
    return !r->error.observed;
}
static void guardian_negative(struct ex_context *r) {
    struct ex_frame f; int rc,owner=EX_X,k; int64_t end=r->d_authorized?r->total:r->terminal_end;
    r->stage=EX_NEGATIVE;
    if(!r->error.observed) ex_fail(r,EX_OP_STATE,0,0,0);
    if(r->fd[EX_COMMAND_W]>=0) (void)ex_close_owned(r,EX_COMMAND_W,EX_PREEXEC,1);
    if(r->fd[EX_REPORT_R]>=0) {
        while(ex_gate(r,end,0)) {
            rc=ex_read_frame(r,r->fd[EX_REPORT_R],&f,end,1);
            if(rc==0) {
                guardian_eof_ledger(r,owner,EX_REPORT_W,EX_PREEXEC,r->acquired_fd[EX_REPORT_W],EX_REPORT_EOF); break;
            }
            if(rc<0) break;
            if(f.source==EX_E || f.source==EX_D) owner=EX_E;
            if(!guardian_accept(r,&f)) break;
        }
    }
    if(r->created[0] && !r->reaped[0] && r->handles[EX_GE].known) {
        (void)ex_pidfd_poll(r,EX_GE,EX_TERMINAL,end,1);
        if(r->npolls && r->polls[r->npolls-1].key==EX_GE &&
           r->polls[r->npolls-1].result>0 && (r->polls[r->npolls-1].revents&POLLIN)) {
            r->terminal[0]=1; r->times[EX_T_E_TERM]=r->polls[r->npolls-1].at;
        }
    }
    if(r->created[0] && !r->reaped[0] && ex_wait_child(r,EX_GE,r->child,end)) {
        r->terminal[0]=r->reaped[0]=1;
        if(!r->times[EX_T_E_TERM]) r->times[EX_T_E_TERM]=r->waits[EX_GE].at;
        r->times[EX_T_E_REAP]=r->waits[EX_GE].at;
    }
    for(k=0;k<EX_STD0;k++) if(k!=EX_GE_FD && k!=EX_GD_FD && k!=EX_ED_FD)
        (void)ex_close_owned(r,k,EX_PREEXEC,1);
    (void)ex_handle_close(r,EX_GE,1); (void)ex_handle_close(r,EX_GD,1);
    r->times[EX_T_FINAL]=ex_now(r);
}
static void preexec_worker(struct ex_context *r) {
    struct ex_frame f; struct ex_product p; int k,rc,err,execfd=r->fd[EX_LEAF_FD];
    int actual_fexecve_called=0;
    char numbers[23][32]; char *argv[28]; char *const env[]={NULL}; uint64_t values[21];
    r->role=EX_X; r->stage=EX_PRE; memset(r->seq,0,sizeof(r->seq));
    memset(r->incoming,0,sizeof(r->incoming)); memset(r->incoming_at,0,sizeof(r->incoming_at));
    r->in=r->fd[EX_COMMAND_R]; r->out=r->fd[EX_REPORT_W];
    for(k=0;k<3;k++) { r->fd[EX_STD0+k]=k; (void)ex_close_owned(r,EX_STD0+k,EX_STDIO,1); }
    (void)ex_close_owned(r,EX_SELF_FD,EX_PREEXEC,1);
    (void)ex_close_owned(r,EX_COMMAND_W,EX_PREEXEC,1);
    (void)ex_close_owned(r,EX_REPORT_R,EX_PREEXEC,1);
    (void)ex_close_owned(r,EX_ERROR_R,EX_PREEXEC,1);
    if(r->error.observed || !ex_sub_get(r,&r->child_sub[EX_X],0)) goto failure;
    f=ex_frame_make(r,EX_SUB,EX_EDGE_GE,EX_X); f.body.fact.key=EX_X;
    f.body.fact.fact=r->child_sub[EX_X]; if(!ex_emit(r,&f)) goto failure;
    for(k=0;k<2;k++) {
        int label=k?EX_WITNESS_FD:EX_LEAF_FD;
        if(!ex_product_fd(r->fd[label],&p) || !ex_same_product(&p,&r->leaf_product)) {
            ex_fail(r,EX_OP_FSTAT,errno,0,0); goto failure;
        }
        f=ex_frame_make(r,EX_PRODUCT,EX_EDGE_GE,label); f.body.product.label=label;
        f.body.product.fd=r->fd[label]; f.body.product.product=p; if(!ex_emit(r,&f)) goto failure;
    }
    if(!ex_flags_check(r,EX_LEAF_FD,EX_PREEXEC,-1) || !ex_flags_check(r,EX_WITNESS_FD,EX_PREEXEC,-1) ||
       !ex_flags_check(r,EX_ERROR_W,EX_PREEXEC,-1) || !ex_flags_check(r,EX_COMMAND_R,EX_PREEXEC,1) ||
       !ex_flags_check(r,EX_REPORT_W,EX_PREEXEC,1) ||
       !ex_capture((int)getpid(),&r->ids[EX_X]) ||
       r->ids[EX_X].ppid!=r->ids[EX_G].pid || !ex_same_product(&r->ids[EX_X].product,&r->guardian_product)) {
        ex_fail(r,EX_OP_PROC,errno,0,0); goto failure;
    }
    r->ids[EX_E]=r->ids[EX_X]; f=ex_frame_make(r,EX_PRE_READY,EX_EDGE_GE,0); f.body.identity=r->ids[EX_X];
    if(!ex_emit(r,&f) || ex_command_read(r,EX_EXEC,1,r->work,&f,0)!=1) goto failure;
    r->stage=EX_EXEC_STAGE;
    if(r->fault==EX_CLOSED_EXEC && !ex_close_owned(r,EX_LEAF_FD,EX_PREEXEC,1)) goto failure;
    if(r->fault==EX_LEAK_WITNESS && !ex_flags_check(r,EX_WITNESS_FD,EX_PREEXEC,1)) goto failure;
    values[0]=(uint64_t)r->t0; values[1]=(uint64_t)r->ids[EX_G].pid;
    values[2]=(uint64_t)r->ids[EX_G].ppid; values[3]=r->ids[EX_G].start;
    values[4]=r->ids[EX_G].uid; values[5]=r->ids[EX_G].euid;
    values[6]=(uint64_t)r->in; values[7]=(uint64_t)r->out; values[8]=(uint64_t)execfd;
    values[9]=(uint64_t)r->fd[EX_WITNESS_FD]; values[10]=(uint64_t)r->fd[EX_ERROR_W];
    values[11]=r->guardian_product.dev; values[12]=r->guardian_product.ino; values[13]=r->guardian_product.size;
    values[14]=(uint64_t)r->guardian_product.mtime_ns; values[15]=(uint64_t)r->guardian_product.ctime_ns;
    values[16]=r->leaf_product.dev; values[17]=r->leaf_product.ino; values[18]=r->leaf_product.size;
    values[19]=(uint64_t)r->leaf_product.mtime_ns; values[20]=(uint64_t)r->leaf_product.ctime_ns;
    for(k=0;k<21;k++) snprintf(numbers[k],sizeof(numbers[k]),"%" PRIu64,values[k]);
    argv[0]=(char *)"frontier-owned-leaf"; argv[1]=(char *)"--fixed-leaf";
    argv[2]=(char *)(r->case_id==EX_LOSS?"worker_loss":"normal"); argv[3]=r->nonce;
    for(k=0;k<6;k++) argv[4+k]=numbers[k]; argv[10]=r->ids[EX_G].boot;
    for(k=6;k<21;k++) argv[5+k]=numbers[k];
    argv[26]=(char *)(r->fault==EX_CLOSED_EXEC?"exec_fd_closed":r->fault==EX_LEAK_WITNESS?"witness_cloexec_cleared":"none"); argv[27]=NULL;
    if(!ex_gate(r,r->work,1)) goto failure;
    f=ex_frame_make(r,EX_ENTER,EX_EDGE_GE,0); f.body.forward.kind=EX_EXEC;
    f.body.forward.original_seq=1; f.body.forward.at=r->last;
    if(!ex_emit(r,&f) || !ex_gate(r,r->work,1)) goto failure;
    actual_fexecve_called=1;
    errno=0; rc=fexecve(execfd,argv,env); err=errno;
    ex_fail(r,EX_OP_EXEC,err,1,rc);
failure:
    /* Before-call failures use the ordinary report edge without a return. */
    ex_error_up(r,actual_fexecve_called);
    for(k=0;k<EX_STD0;k++) if(k!=EX_REPORT_W && r->fd[k]>=0)
        (void)ex_close_owned(r,k,EX_PREEXEC,1);
    (void)ex_close_owned(r,EX_REPORT_W,EX_PREEXEC,0); _exit(71);
}
static int guardian_arguments(struct ex_context *r,int argc,char **argv) {
    const char *p;
    if(argc!=5 || !ex_nonce(argv[2]) || argv[3][0]!='/' || strlen(argv[3])>4096) return 0;
    if(!strcmp(argv[1],"normal")) r->case_id=EX_NORMAL;
    else if(!strcmp(argv[1],"worker_loss")) r->case_id=EX_LOSS; else return 0;
    if(!strcmp(argv[4],"none")) r->fault=EX_NOFAULT;
    else if(!strcmp(argv[4],"exec_fd_closed")) r->fault=EX_CLOSED_EXEC;
    else if(!strcmp(argv[4],"witness_cloexec_cleared")) r->fault=EX_LEAK_WITNESS; else return 0;
    for(p=argv[3];*p;p++) {
        if(!((*p>='a' && *p<='z') || (*p>='A' && *p<='Z') || (*p>='0' && *p<='9') ||
             *p=='/' || *p=='_' || *p=='-' || *p=='.' || *p=='+')) return 0;
        if(*p=='/' && (p[1]=='/' || !p[1] || (p[1]=='.' && (p[2]=='/' || !p[2] ||
            (p[2]=='.' && (p[3]=='/' || !p[3])))))) return 0;
    }
    memcpy(r->nonce,argv[2],65); return 1;
}
static int guardian_initial(struct ex_context *r,const char *path) {
    int k,rc,err; pid_t pid; unsigned char magic[4];
    r->stage=EX_INITIAL; r->t0=ex_now(r); r->times[EX_T_INITIAL]=r->t0;
    if(!ex_deadlines(r) || !ex_sigpipe(r)) return 0;
    for(k=0;k<3;k++) {
        struct ex_flags v; memset(&v,0,sizeof(v)); v.owner=EX_G; v.label=EX_STD0+k; v.epoch=EX_STDIO; v.fd=k;
        errno=0; rc=fcntl(k,F_GETFD); err=errno; ex_fact_set(r,&v.before,rc,err,0);
        ex_store_flags(r,&v); if(rc<0) { ex_fail(r,EX_OP_FLAGS,err,1,rc); return 0; }
    }
    r->fd[EX_SELF_FD]=open("/proc/self/exe",O_RDONLY|O_CLOEXEC);
    if(r->fd[EX_SELF_FD]<0 || !ex_product_fd(r->fd[EX_SELF_FD],&r->guardian_product) ||
       !ex_capture((int)getpid(),&r->ids[EX_G]) ||
       !ex_same_product(&r->ids[EX_G].product,&r->guardian_product)) {
        ex_fail(r,EX_OP_PROC,errno,0,0); return 0;
    }
    r->acquired_fd[EX_SELF_FD]=r->fd[EX_SELF_FD];
    errno=0; r->fd[EX_LEAF_FD]=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if(r->fd[EX_LEAF_FD]<0) { ex_fail(r,EX_OP_OPEN,errno,1,-1); return 0; }
    r->acquired_fd[EX_LEAF_FD]=r->fd[EX_LEAF_FD];
    if(!ex_product_fd(r->fd[EX_LEAF_FD],&r->leaf_product) ||
       pread(r->fd[EX_LEAF_FD],magic,sizeof(magic),0)!=(ssize_t)sizeof(magic) ||
       memcmp(magic,"\177ELF",4) || ex_same_product(&r->guardian_product,&r->leaf_product)) {
        ex_fail(r,EX_OP_PRODUCT,errno,0,0); return 0;
    }
    errno=0; r->fd[EX_WITNESS_FD]=fcntl(r->fd[EX_LEAF_FD],F_DUPFD_CLOEXEC,3);
    if(r->fd[EX_WITNESS_FD]<0) { ex_fail(r,EX_OP_FLAGS,errno,1,-1); return 0; }
    r->acquired_fd[EX_WITNESS_FD]=r->fd[EX_WITNESS_FD];
    if(!ex_flags_check(r,EX_SELF_FD,EX_PREEXEC,-1) || !ex_flags_check(r,EX_LEAF_FD,EX_PREEXEC,-1) ||
       !ex_flags_check(r,EX_WITNESS_FD,EX_PREEXEC,-1) ||
       !ex_pipe(r,EX_COMMAND_R,EX_COMMAND_W,EX_PREEXEC) || !ex_pipe(r,EX_REPORT_R,EX_REPORT_W,EX_PREEXEC) ||
       !ex_pipe(r,EX_ERROR_R,EX_ERROR_W,EX_PREEXEC)) return 0;
    for(k=0;k<5;k++) r->startup[k].fd=r->fd[r->startup[k].label];
    if(!ex_sub_get(r,&r->sub[0],0) || !ex_sub_set(r,&r->sub[1],1) ||
       !ex_sub_get(r,&r->sub[2],1) || !ex_gate(r,r->work,1)) return 0;
    errno=0; pid=fork();
    if(pid<0) { ex_fail(r,EX_OP_FORK,errno,1,(int)pid); return 0; }
    if(!pid) preexec_worker(r);
    r->child=pid; r->created[0]=1;
    (void)ex_close_owned(r,EX_COMMAND_R,EX_PREEXEC,1);
    (void)ex_close_owned(r,EX_REPORT_W,EX_PREEXEC,1);
    (void)ex_close_owned(r,EX_ERROR_W,EX_PREEXEC,1);
    (void)ex_close_owned(r,EX_LEAF_FD,EX_PREEXEC,1);
    (void)ex_close_owned(r,EX_WITNESS_FD,EX_PREEXEC,1);
    return !r->error.observed;
}
static int guardian_run(struct ex_context *r) {
    struct ex_frame f; struct ex_identity d; int rc;
    r->stage=EX_PRE;
    if(!guardian_receive(r,EX_PRE_READY,EX_X,r->work) || !guardian_pre_gate(r) ||
       !guardian_command(r,EX_EXEC,EX_T_EXEC_SENT)) return 0;
    r->stage=EX_EXEC_STAGE;
    rc=ex_read_frame(r,r->fd[EX_ERROR_R],&f,r->work,1);
    if(rc==1) {
        if(f.kind!=EX_EXEC_ERROR || f.source!=EX_X) ex_fail(r,EX_OP_FRAME,0,0,0);
        else (void)guardian_accept(r,&f);
        return 0;
    }
    if(rc!=0) return 0;
    r->error_eof=ex_now(r);
    if(!guardian_receive(r,EX_POST_READY,EX_E,r->work) || !guardian_post_gate(r)) return 0;
    r->stage=EX_POST;
    if(!guardian_command(r,EX_CREATE,EX_T_CREATE)) return 0;
    r->d_authorized=1;
    if(!guardian_receive(r,EX_D_READY,EX_D,r->work) || !good_get0(&r->child_sub[EX_D]) ||
       !r->handles[EX_ED].known || !ex_capture(r->ids[EX_D].pid,&d) ||
       !ex_same_identity(&d,&r->ids[EX_D],0) || !ex_alive(&d) ||
       d.ppid!=r->ids[EX_E].pid || d.uid!=r->ids[EX_G].uid || d.euid!=r->ids[EX_G].euid ||
       strcmp(d.boot,r->ids[EX_G].boot) || !ex_handle_open(r,EX_GD,&d)) {
        ex_fail(r,EX_OP_PROC,errno,0,0); return 0;
    }
    r->bound[1]=1; r->times[EX_T_BOUND]=ex_now(r);
    if(!guardian_command(r,EX_ARM,EX_T_ARM) || !guardian_receive(r,EX_ALL_ACK,EX_E,r->work) ||
       !guardian_live(r,0)) return 0;
    r->stage=EX_ARMED; r->times[EX_T_PRIMARY]=ex_now(r);
    if(r->case_id==EX_NORMAL) {
        if(!guardian_command(r,EX_FINISH,EX_T_FINISH) ||
           !guardian_receive(r,EX_E_FINISH_ACK,EX_E,r->terminal_end) ||
           !guardian_report_eof(r,EX_E,r->terminal_end) ||
           !r->reaped[1] || r->waits[EX_ED].status!=0 ||
           !r->handles[EX_ED].close.attempted || r->handles[EX_ED].close.result ||
           !guardian_wait(r,EX_GE,r->terminal_end,0) ||
           !ex_pidfd_poll(r,EX_GD,EX_TERMINAL,r->terminal_end,1)) return 0;
    } else {
        r->stage=EX_LOSS_STAGE;
        if(!guardian_signal(r,EX_GE) || !guardian_wait(r,EX_GE,r->cleanup,9) ||
           !guardian_report_eof(r,EX_E,r->cleanup) || !guardian_adopt(r) ||
           !guardian_signal(r,EX_GD) || !guardian_wait(r,EX_GD,r->terminal_end,9)) return 0;
        guardian_loss_ledger(r);
    }
    r->stage=EX_TERMINAL;
    if(!r->reaped[0] || !r->reaped[1] || !guardian_close_all(r) || !ex_gate(r,r->terminal_end,1)) return 0;
    r->times[EX_T_FD_COMPLETE]=r->last;
    if(!ex_sub_set(r,&r->sub[3],0) || !ex_sub_get(r,&r->sub[4],0) || !ex_gate(r,r->terminal_end,1)) return 0;
    r->times[EX_T_RESET]=r->last; r->times[EX_T_FINAL]=ex_now(r);
    if(!ex_gate(r,r->terminal_end,1)) return 0;
    r->success=1; return 1;
}
int main(int argc,char **argv) {
    struct ex_context r; ex_init(&r,EX_G);
    if(!guardian_arguments(&r,argc,argv)) return 2;
    if(!guardian_initial(&r,argv[3]) || !guardian_run(&r)) guardian_negative(&r);
    json_result(&r); return r.success && !ferror(stdout)?0:1;
}
