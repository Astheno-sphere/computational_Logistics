/* Fixed direct-child readonly Python CPU protocol. No model or resource authority. */
#ifndef FRONTIER_V8_OWNED_C_PYTHON_PREFLIGHT_PROTOCOL_H
#define FRONTIER_V8_OWNED_C_PYTHON_PREFLIGHT_PROTOCOL_H
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <sys/resource.h>
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
/* The existing captured CPP reader requires these exact six single markers. */
const long frontier_v8_header_pidfd_open = SYS_pidfd_open;
const unsigned int frontier_v8_target_int_bytes = __SIZEOF_INT__;
const unsigned int frontier_v8_target_long_bytes = __SIZEOF_LONG__;
const unsigned int frontier_v8_target_pointer_bytes = __SIZEOF_POINTER__;
const unsigned int frontier_v8_target_char_bits = __CHAR_BIT__;
const unsigned int frontier_v8_target_byte_order = __BYTE_ORDER__;
const long frontier_v8_header_pidfd_send_signal = SYS_pidfd_send_signal;
const long frontier_v8_header_f_getfd = F_GETFD;
const long frontier_v8_header_f_setfd = F_SETFD;
const long frontier_v8_header_fd_cloexec = FD_CLOEXEC;
const long frontier_v8_header_o_cloexec = O_CLOEXEC;
const long frontier_v8_header_o_nofollow = O_NOFOLLOW;
const long frontier_v8_header_o_nonblock = O_NONBLOCK;
const long frontier_v8_header_f_getfl = F_GETFL;
const long frontier_v8_header_ebadf = EBADF;
const long frontier_v8_header_eagain = EAGAIN;
const long frontier_v8_header_eintr = EINTR;
const long frontier_v8_header_esrch = ESRCH;
const long frontier_v8_header_sigkill = SIGKILL;
const long frontier_v8_header_sigpipe = SIGPIPE;
const long frontier_v8_header_pollin = POLLIN;
const long frontier_v8_header_pollnval = POLLNVAL;
const long frontier_v8_header_pipe_buf = PIPE_BUF;
const long frontier_v8_header_rlimit_core = RLIMIT_CORE;
const long frontier_v8_header_rlimit_cpu = RLIMIT_CPU;
_Static_assert(sizeof(int)==4 && INT_MAX==INT32_MAX, "signed32 int required");
_Static_assert(sizeof(pid_t)==4 && (pid_t)-1<0, "signed32 pid required");
_Static_assert(sizeof(uid_t)==4 && (uid_t)-1>0, "unsigned32 uid required");
_Static_assert(sizeof(uint64_t)==8 && sizeof(int64_t)==8 && CHAR_BIT==8,
               "Declared integer representations required");
_Static_assert(sizeof(int)==__SIZEOF_INT__ && sizeof(long)==__SIZEOF_LONG__ &&
               sizeof(void *)==__SIZEOF_POINTER__, "Compiler target differs");
_Static_assert(sizeof(dev_t)<=8 && sizeof(ino_t)<=8, "stat operands too wide");
#define PP_NS INT64_C(1000000000)
#define PP_BODY_MAX 262144
#define PP_CONTROL_MAX 512
#define PP_ROWS 64
#define PP_UNATTEMPTED INT32_MIN
enum { PP_G, PP_X, PP_P };
enum { PP_INTERPRETER, PP_WORKER, PP_REQUEST, PP_COMMAND_R, PP_COMMAND_W,
       PP_REPORT_R, PP_REPORT_W, PP_ERROR_R, PP_ERROR_W, PP_PIDFD,
       PP_STDIN, PP_STDOUT, PP_STDERR, PP_FDS };
enum { PP_EXPLICIT, PP_ABSENT, PP_EXEC_CLOSED, PP_PARENT_EOF,
       PP_OWNER_DEATH, PP_UNKNOWN };
struct pp_fact { int attempted,result,err; int64_t at; };
struct pp_product { uint64_t dev,ino,mode,size; int64_t mtime,ctime; };
struct pp_identity {
    int known,pid,ppid; uint32_t uid,euid; uint64_t birth;
    char boot[37],state; struct pp_product product;
};
struct pp_close {
    int owner,label,generation,fd,evidence; struct pp_fact close,badfd;
};
struct pp_flags {
    int owner,label,generation,fd; struct pp_fact before,set,after,getfl;
};
struct pp_poll { int fd,result,revents,err; int64_t at; char purpose[24]; };
struct pp_packet {
    int role,outgoing,seq; int64_t at,observed; char kind[24],payload[400];
    int length; char sha[65];
};
struct pp_error {
    int observed,err,known,result; int64_t at; char stage[24],op[48];
};
struct pp_context {
    int role,loss,fault,fixture,stage,sendseq,recvseq,pipebuf,success;
    int fd[PP_FDS],original[PP_FDS],child; char nonce[65]; int version[3];
    int64_t t0,work,cleanup,terminal,total,expiry,last;
    struct pp_error error; struct pp_identity ids[4];
    struct pp_product guardian,interpreter,worker,request;
    int guardian_known,interpreter_known;
    struct pp_fact open,handle_flags,handle_close,handle_badfd;
    int fdinfo_pid,exec_attempted,exec_attempted_known,exec_returned,exec_result,exec_err,exec_known;
    int64_t enter,error_eof;
    int signal_consumed,signal_attempts,signal_result,signal_err,signal_known;
    int64_t signal_at; int signal_fd;
    int wait_attempts,wait_pid,wait_status,wait_err,wait_known; int64_t wait_at;
    struct pp_poll polls[PP_ROWS]; int npolls;
    struct pp_close closes[PP_ROWS]; int ncloses;
    struct pp_flags flags[PP_ROWS]; int nflags;
    struct pp_packet packets[PP_ROWS]; int npackets;
    unsigned char body[PP_BODY_MAX]; size_t body_len; int body_declared,body_complete;
    char body_sha[65]; char *kernel_argv; size_t kernel_argv_len;
    int64_t times[11]; char *argv[12],*python_argv[19]; char python_fdargs[4][24],t0arg[32];
    char bootstrap_worker_hash[65];
    int core_result,core_errno,cpu_result,cpu_errno,rlimits_reported;
    struct pp_fact sigpipe_set,sigpipe_get; int sigpipe_ignored;
};
static inline const char *pp_role(int r) {
    static const char *v[]={"G","X","P"}; return r>=0 && r<3?v[r]:"invalid";
}
static inline const char *pp_label(int r) {
    static const char *v[]={"interpreter","worker_script","request","command_read",
        "command_write","report_read","report_write","exec_error_read",
        "exec_error_write","G_P","original_stdin","original_stdout","original_stderr"};
    return r>=0 && r<PP_FDS?v[r]:"invalid";
}
static inline const char *pp_evidence(int r) {
    static const char *v[]={"explicit_once_close","original_absent","exec_cloexec",
        "parent_report_eof","owner_death","unknown"};
    return r>=0 && r<6?v[r]:"unknown";
}
#endif
