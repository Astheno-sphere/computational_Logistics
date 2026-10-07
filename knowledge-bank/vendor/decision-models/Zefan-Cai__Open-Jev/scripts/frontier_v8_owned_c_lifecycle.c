/* Fixed four-role owned CPU fixture. This is not a production containment guard. */
#if !defined(__linux__) || !defined(_GNU_SOURCE)
#error "Declared Linux GNU environment required"
#endif
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
_Static_assert(sizeof(int) == __SIZEOF_INT__, "int baseline differs");
_Static_assert(sizeof(long) == __SIZEOF_LONG__, "long baseline differs");
_Static_assert(sizeof(void *) == __SIZEOF_POINTER__, "pointer baseline differs");
_Static_assert(CHAR_BIT == __CHAR_BIT__, "character baseline differs");
_Static_assert(sizeof(pid_t) <= sizeof(long), "PID operand not representable");
_Static_assert(SYS_pidfd_open >= 0 && SYS_pidfd_open <= LONG_MAX, "pidfd_open number not representable");
_Static_assert(SYS_pidfd_send_signal >= 0 && SYS_pidfd_send_signal <= LONG_MAX, "send number not representable");

#define MAGIC 0x4a45564cU
#define NS 1000000000LL
#define NONE (-1)
enum { COORD, CTRL, GUARD, WORKER, ROLES };
enum { CR_R, CR_W, CC_R, CC_W, GR_R, GR_W, GC_R, GC_W, WR_R, WR_W, WC_R, WC_W, CHANNELS };
enum { H_CTRL_READY, H_GUARD_READY, H_GUARD_START, H_WORKER_READY, H_GUARD_WORKER_READY,
       H_ARM, H_ACK, H_CTRL_QUIT, H_WORKER_QUIT, H_TERMINAL, HANDSHAKES };
enum { F_COORD_CTRL, F_COORD_GUARD, F_GUARD_CTRL, F_GUARD_WORKER, HANDLES };
enum { P_ALIVE, P_CTRL_EXIT, P_GUARD_CTRL_EXIT, P_WORKER_EXIT, P_GUARD_EXIT, POLLS };
enum { T0, WORK_END, CLEAN_END, TERMINAL_END, WORKER_END, TOTAL_END, ARM_TIME, ACK_TIME,
       COMMAND_TIME, CTRL_EXIT_TIME, SIGNAL_TIME, WORKER_EXIT_TIME, WORKER_REAP_TIME,
       TERMINAL_TIME, FINAL_TIME, TIMES };
static const char *roles[] = { "coordinator", "controller", "guard", "worker" };
static const char *hs_names[] = { "controller_ready", "guard_ready", "guard_start", "worker_ready",
    "guard_worker_ready", "case_arm", "case_ack", "controller_quit", "worker_quit", "guard_terminal" };
static const char *fd_names[] = { "controller_ready_read", "controller_ready_write",
    "controller_command_read", "controller_command_write", "guard_report_read", "guard_report_write",
    "guard_command_read", "guard_command_write", "worker_ready_read", "worker_ready_write",
    "worker_command_read", "worker_command_write", "controller_pidfd", "stdin", "stdout", "stderr" };
static int channels[CHANNELS];
static int product_fd = -1, loss_case;
static char nonce[65];
static int64_t last_clock;

struct identity { int known; int64_t pid, ppid, uid, euid, start; char boot[37]; };
struct product { int known; int64_t stat[7]; };
struct fd_fact { int known, acquisition, fd, opened; int64_t open_result; int open_errno;
    int fdinfo_known; int64_t fdinfo_pid; int close_calls, close_known, close_result, close_errno,
    ebadf_known, ebadf_result, ebadf_errno; };
struct poll_fact { int known, calls, fd, observed, result, revents, events, error; };
struct wait_fact { int known, owner, calls, observed; int64_t pid, result;
    int status, error, exited, exit_code, signaled, term_signal; };
struct signal_fact { int known, attempts, fd, number, flags, observed, result, error; };
struct close_fact { int fd, kind, result, error, ebadf_result, ebadf_errno; };
struct closes { int known, count; struct close_fact row[12]; };
struct handshake { int known, bytes, kind, role; };
struct report {
    char error[64]; int error_errno;
    struct identity ids[ROLES], checks[4];
    struct product product, products[2];
    struct fd_fact fds[HANDLES]; struct poll_fact polls[POLLS]; struct wait_fact waits[3];
    struct signal_fact worker_signal, coordinator_signals[2];
    struct closes closes[3]; struct handshake hs[HANDSHAKES];
    int64_t times[TIMES]; unsigned int time_known;
    int ignore_known, ignore_result, ignore_errno;
};
struct packet { unsigned int magic; int kind, role, loss; char nonce[65]; struct report report; };
_Static_assert(sizeof(struct packet) <= PIPE_BUF, "Private bounded packet exceeds PIPE_BUF");

static void error(struct report *r, const char *stage, int saved)
{
    if (!r->error[0]) { snprintf(r->error, sizeof(r->error), "%s", stage); r->error_errno = saved; }
}
static int64_t clock_now(struct report *r)
{
    struct timespec t; int64_t value;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) { error(r, "clock", errno); return -1; }
    if (t.tv_sec < 0 || t.tv_sec > (INT64_MAX - NS) / NS || t.tv_nsec < 0 || t.tv_nsec >= NS) {
        error(r, "clock_range", 0); return -1;
    }
    value = (int64_t)t.tv_sec * NS + t.tv_nsec;
    if (value < last_clock) { error(r, "clock_reverse", 0); return -1; }
    last_clock = value; return value;
}
static int within(struct report *r, int deadline)
{
    int64_t now = clock_now(r);
    if (now < 0) return 0;
    if (now >= r->times[deadline]) { error(r, "deadline", 0); return 0; }
    return 1;
}
static int mark_time(struct report *r, int index)
{
    int64_t value = clock_now(r);
    if (value < 0) return 0;
    r->times[index] = value; r->time_known |= 1U << index; return 1;
}
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
    if (close(fd) != 0 || used == cap || memchr(body, 0, used)) return 0;
    body[used] = 0; return 1;
}
static int capture_identity(int64_t pid, struct identity *out)
{
    char path[80], body[4097], boot[80], *end, *cursor; long long value; int field;
    struct identity id = {0};
    snprintf(path, sizeof(path), "/proc/%lld/stat", (long long)pid);
    if (!read_text(path, body, sizeof(body) - 1)) return 0;
    errno = 0; value = strtoll(body, &end, 10);
    if (errno || end == body || value != pid || *end != ' ' || end[1] != '(') return 0;
    cursor = strrchr(end, ')');
    if (!cursor || cursor[1] != ' ' || !cursor[2] || cursor[3] != ' ') return 0;
    cursor += 4;
    for (field = 4; field <= 22; field++) {
        errno = 0; value = strtoll(cursor, &end, 10);
        if (errno || end == cursor) return 0;
        if (field == 4) id.ppid = value;
        if (field == 22) id.start = value;
        cursor = end;
        while (*cursor == ' ') cursor++;
    }
    snprintf(path, sizeof(path), "/proc/%lld/status", (long long)pid);
    if (!read_text(path, body, sizeof(body) - 1)) return 0;
    cursor = strstr(body, "\nUid:");
    if (!cursor) return 0;
    cursor += 5;
    errno = 0; id.uid = strtoll(cursor, &end, 10);
    if (errno || end == cursor) return 0;
    cursor = end; errno = 0; id.euid = strtoll(cursor, &end, 10);
    if (errno || end == cursor) return 0;
    if (!read_text("/proc/sys/kernel/random/boot_id", boot, sizeof(boot) - 1) ||
        strlen(boot) != 37 || boot[36] != '\n' || id.start <= 0) return 0;
    boot[36] = 0; memcpy(id.boot, boot, 37); id.pid = pid; id.known = 1; *out = id; return 1;
}
static int same_id(const struct identity *a, const struct identity *b)
{
    return a->known && b->known && a->pid == b->pid && a->ppid == b->ppid &&
        a->uid == b->uid && a->euid == b->euid && a->start == b->start && !strcmp(a->boot, b->boot);
}
static int product_stat(struct product *out)
{
    struct stat s;
    if (fstat(product_fd, &s) || !S_ISREG(s.st_mode)) return 0;
    out->stat[0] = s.st_dev; out->stat[1] = s.st_ino; out->stat[2] = s.st_mode;
    out->stat[3] = s.st_uid; out->stat[4] = s.st_size;
    out->stat[5] = (int64_t)s.st_mtim.tv_sec * NS + s.st_mtim.tv_nsec;
    out->stat[6] = (int64_t)s.st_ctim.tv_sec * NS + s.st_ctim.tv_nsec;
    out->known = 1; return 1;
}
static int same_product(const struct product *a, const struct product *b)
{ return a->known && b->known && !memcmp(a->stat, b->stat, sizeof(a->stat)); }
static void close_unrelated(struct report *r, int role, int fd, int kind)
{
    struct closes *list = &r->closes[role - 1]; struct close_fact *fact;
    if (fd < 0) return;
    list->known = 1;
    if (list->count >= 12) { error(r, "close_capacity", 0); return; }
    fact = &list->row[list->count++]; fact->fd = fd; fact->kind = kind;
    errno = 0; fact->result = close(fd); fact->error = errno;
    errno = 0; fact->ebadf_result = fcntl(fd, F_GETFD); fact->ebadf_errno = errno;
    if (fact->result || fact->ebadf_result != -1 || fact->ebadf_errno != EBADF)
        error(r, "inherited_close", fact->error);
}
static void close_channel(struct report *r, int role, int index)
{ close_unrelated(r, role, channels[index], index); channels[index] = -1; }
static void close_stdio(struct report *r, int role)
{ int n; for (n = 0; n < 3; n++) close_unrelated(r, role, n, 13 + n); }
static int make_pipe(struct report *r, int index)
{
    int pair[2];
    if (pipe2(pair, O_NONBLOCK | O_CLOEXEC)) { error(r, "pipe", errno); return 0; }
    channels[index] = pair[0]; channels[index + 1] = pair[1]; return 1;
}
static int fdinfo_pid(int fd, int64_t *out)
{
    char path[80], body[4097], *cursor, *end; int seen = 0; long long pid;
    snprintf(path, sizeof(path), "/proc/self/fdinfo/%d", fd);
    if (!read_text(path, body, sizeof(body) - 1)) return 0;
    cursor = body;
    while (*cursor) {
        char *line_end = strchr(cursor, '\n');
        if (!line_end) return 0;
        if (!strncmp(cursor, "Pid:", 4)) {
            if (++seen != 1) return 0;
            errno = 0; pid = strtoll(cursor + 4, &end, 10);
            if (errno || end == cursor + 4 || pid <= 0) return 0;
            while (end < line_end && (*end == ' ' || *end == '\t')) end++;
            if (end != line_end) return 0;
            *out = pid;
        }
        cursor = line_end + 1;
    }
    return seen == 1;
}
static int open_pidfd(struct report *r, struct fd_fact *fact, const struct identity *id)
{
    struct identity after;
    fact->known = fact->opened = 1; fact->fd = -1;
    errno = 0; fact->open_result = syscall((long)SYS_pidfd_open, (long)id->pid, (unsigned long)0);
    fact->open_errno = errno;
    if (fact->open_result < 0 || fact->open_result > INT_MAX) {
        error(r, "pidfd_open", fact->open_errno); return 0;
    }
    fact->acquisition = 1; fact->fd = (int)fact->open_result;
    if (!fdinfo_pid(fact->fd, &fact->fdinfo_pid) || fact->fdinfo_pid != id->pid ||
        !capture_identity(id->pid, &after) || !same_id(id, &after)) {
        error(r, "pidfd_identity", 0); return 0;
    }
    fact->fdinfo_known = 1; return 1;
}
static void close_pidfd(struct report *r, struct fd_fact *fact)
{
    if (!fact->known || !fact->acquisition || fact->close_calls) return;
    fact->close_calls = fact->close_known = 1;
    errno = 0; fact->close_result = close(fact->fd); fact->close_errno = errno;
    if (fact->close_result) { error(r, "pidfd_close", fact->close_errno); return; }
    fact->ebadf_known = 1; errno = 0;
    fact->ebadf_result = fcntl(fact->fd, F_GETFD); fact->ebadf_errno = errno;
    if (fact->ebadf_result != -1 || fact->ebadf_errno != EBADF) error(r, "pidfd_ebadf", 0);
}
static int poll_once(struct report *r, struct poll_fact *fact, int fd, int timeout)
{
    struct pollfd p = { fd, POLLIN, 0 };
    fact->known = fact->observed = 1; fact->fd = fd; fact->events = POLLIN; fact->calls++;
    errno = 0; fact->result = poll(&p, 1, timeout); fact->error = errno; fact->revents = p.revents;
    if (fact->result < 0 || (p.revents & POLLNVAL)) { error(r, "pidfd_poll", fact->error); return -1; }
    return fact->result;
}
static int wait_event(struct report *r, struct poll_fact *fact, int fd, int deadline)
{
    while (within(r, deadline)) {
        int n = poll_once(r, fact, fd, 10);
        if (n < 0) return 0;
        if (n == 1 && (fact->revents & POLLIN)) return 1;
    }
    return 0;
}
static int watch_live(struct report *r, int watch)
{
    struct pollfd p = { watch, POLLIN, 0 }; int n;
    if (watch < 0) return 1;
    errno = 0; n = poll(&p, 1, 0);
    if (n < 0 || p.revents) { error(r, "controller_early_exit", n < 0 ? errno : 0); return 0; }
    return 1;
}
static int transfer(struct report *r, int fd, struct packet *p, int writing, int deadline, int watch)
{
    size_t done = 0;
    while (done < sizeof(*p) && within(r, deadline) && watch_live(r, watch)) {
        ssize_t n; struct pollfd ready = { fd, writing ? POLLOUT : POLLIN, 0 };
        errno = 0;
        n = writing ? write(fd, (char *)p + done, sizeof(*p) - done) :
                      read(fd, (char *)p + done, sizeof(*p) - done);
        if (n > 0) { done += (size_t)n; continue; }
        if (!n && !writing) { error(r, "packet_eof", 0); return 0; }
        if (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK) { error(r, "packet_io", errno); return 0; }
        if (poll(&ready, 1, 10) < 0) { error(r, "packet_poll", errno); return 0; }
    }
    return done == sizeof(*p);
}
static int send_packet(struct report *r, int fd, int kind, int role, int deadline, int watch)
{
    struct packet p = {0};
    p.magic = MAGIC; p.kind = kind; p.role = role; p.loss = loss_case;
    memcpy(p.nonce, nonce, sizeof(nonce)); p.report = *r;
    if (!transfer(r, fd, &p, 1, deadline, watch)) return 0;
    r->hs[kind] = (struct handshake){1, sizeof(p), kind, role}; return 1;
}
static int recv_packet(struct report *r, int fd, struct packet *p, int kind, int role, int deadline, int watch)
{
    if (!transfer(r, fd, p, 0, deadline, watch)) return 0;
    if (p->magic != MAGIC || p->kind != kind || p->role != role || p->loss != loss_case ||
        memcmp(p->nonce, nonce, sizeof(nonce))) { error(r, "packet_binding", 0); return 0; }
    r->hs[kind] = (struct handshake){1, sizeof(*p), kind, role}; return 1;
}
static int bound_child(struct report *r, int role, int64_t fork_pid, int64_t parent,
                       const struct identity *reported, const struct product *product)
{
    struct identity fresh;
    if (!reported->known || reported->pid != fork_pid || reported->ppid != parent ||
        reported->uid != r->ids[COORD].uid || reported->euid != r->ids[COORD].euid ||
        strcmp(reported->boot, r->ids[COORD].boot) || !capture_identity(fork_pid, &fresh) ||
        !same_id(reported, &fresh) || !same_product(&r->product, product)) {
        error(r, "child_identity", 0); return 0;
    }
    r->ids[role] = *reported; return 1;
}
static int recheck_worker(struct report *r, int signaling)
{
    int base = signaling ? 2 : 0;
    if (!capture_identity(getpid(), &r->checks[base]) ||
        !capture_identity(r->ids[WORKER].pid, &r->checks[base + 1]) ||
        !same_id(&r->checks[base], &r->ids[GUARD]) ||
        !same_id(&r->checks[base + 1], &r->ids[WORKER]) ||
        !product_stat(&r->products[signaling]) || !same_product(&r->product, &r->products[signaling])) {
        error(r, "worker_identity", 0); return 0;
    }
    return 1;
}
static void signal_owned(struct report *r, struct signal_fact *fact, int fd)
{
    fact->known = 1;
    if (fact->attempts || !within(r, CLEAN_END)) return;
    fact->attempts = fact->observed = 1; fact->fd = fd; fact->number = SIGKILL; fact->flags = 0;
    errno = 0; fact->result = syscall((long)SYS_pidfd_send_signal, (long)fd,
                                      (long)SIGKILL, (void *)NULL, (unsigned long)0);
    fact->error = errno;
    if (fact->result) error(r, "pidfd_signal", fact->error);
}
static int reap(struct report *r, struct wait_fact *fact, int owner, int64_t pid, int deadline)
{
    fact->known = 1; fact->owner = owner; fact->pid = pid;
    while (within(r, deadline)) {
        struct pollfd unused = {-1, 0, 0}; int status = 0;
        fact->calls++; errno = 0;
        fact->result = waitpid((pid_t)pid, &status, WNOHANG); fact->error = errno;
        if (fact->result < 0) { fact->observed = 1; error(r, "waitpid", fact->error); return 0; }
        if (fact->result > 0) {
            fact->observed = 1; fact->status = status; fact->exited = WIFEXITED(status);
            fact->exit_code = fact->exited ? WEXITSTATUS(status) : -1;
            fact->signaled = WIFSIGNALED(status); fact->term_signal = fact->signaled ? WTERMSIG(status) : 0;
            if (fact->result != pid) { error(r, "waitpid_identity", 0); return 0; }
            return 1;
        }
        if (poll(&unused, 0, 10) < 0) { error(r, "wait_poll", errno); return 0; }
    }
    return 0;
}
static void controller(struct report r)
{
    struct packet p; int n;
    close_stdio(&r, CTRL);
    for (n = 0; n < CHANNELS; n++) if (n != CR_W && n != CC_R) close_channel(&r, CTRL, n);
    if (!capture_identity(getpid(), &r.ids[CTRL]) || !product_stat(&r.product)) _exit(31);
    if (r.error[0] || !send_packet(&r, channels[CR_W], H_CTRL_READY, CTRL, WORK_END, -1) ||
        !recv_packet(&r, channels[CC_R], &p, H_CTRL_QUIT, COORD, WORK_END, -1)) _exit(31);
    _exit(loss_case ? 23 : 0);
}
static void worker(struct report r)
{
    struct packet p; int n;
    /* Guard already closed stdio; new private pipes may now use numbers 0/1/2. */
    for (n = 0; n < CHANNELS; n++) if (n != WR_W && n != WC_R) close_channel(&r, WORKER, n);
    close_unrelated(&r, WORKER, r.fds[F_GUARD_CTRL].fd, 12);
    if (!capture_identity(getpid(), &r.ids[WORKER]) || !product_stat(&r.product)) _exit(32);
    if (r.error[0] || !send_packet(&r, channels[WR_W], H_WORKER_READY, WORKER, WORK_END, -1) ||
        !recv_packet(&r, channels[WC_R], &p, H_WORKER_QUIT, GUARD, WORKER_END, -1)) _exit(33);
    _exit(0);
}
static void merge_guard(struct report *r, const struct report *g)
{
    int n;
    if (g->error[0]) error(r, g->error, g->error_errno);
    r->ids[GUARD] = g->ids[GUARD]; r->ids[WORKER] = g->ids[WORKER];
    memcpy(r->checks, g->checks, sizeof(r->checks)); memcpy(r->products, g->products, sizeof(r->products));
    r->fds[F_GUARD_CTRL] = g->fds[F_GUARD_CTRL]; r->fds[F_GUARD_WORKER] = g->fds[F_GUARD_WORKER];
    r->polls[P_ALIVE] = g->polls[P_ALIVE]; r->polls[P_GUARD_CTRL_EXIT] = g->polls[P_GUARD_CTRL_EXIT];
    r->polls[P_WORKER_EXIT] = g->polls[P_WORKER_EXIT]; r->waits[2] = g->waits[2];
    r->worker_signal = g->worker_signal; r->closes[1] = g->closes[1]; r->closes[2] = g->closes[2];
    for (n = 0; n < HANDSHAKES; n++) if (g->hs[n].known && !r->hs[n].known) r->hs[n] = g->hs[n];
    for (n = ARM_TIME; n < TIMES; n++) if ((g->time_known & (1U << n)) && n != ACK_TIME && n != COMMAND_TIME) {
        r->times[n] = g->times[n]; r->time_known |= 1U << n;
    }
}
static void guard(struct report r)
{
    struct packet p; pid_t worker_pid = -1; int n; struct fd_fact *cf = &r.fds[F_GUARD_CTRL];
    *cf = r.fds[F_COORD_CTRL]; cf->acquisition = 2; cf->opened = 0;
    close_stdio(&r, GUARD);
    for (n = 0; n < CHANNELS; n++) if (n != GR_W && n != GC_R) close_channel(&r, GUARD, n);
    if (!capture_identity(getpid(), &r.ids[GUARD]) || !product_stat(&r.product)) error(&r, "guard_identity", errno);
    if (r.error[0] || !send_packet(&r, channels[GR_W], H_GUARD_READY, GUARD, WORK_END, cf->fd) ||
        !recv_packet(&r, channels[GC_R], &p, H_GUARD_START, COORD, WORK_END, cf->fd)) goto cleanup;
    if (!make_pipe(&r, WR_R) || !make_pipe(&r, WC_R) || !within(&r, WORK_END)) goto cleanup;
    worker_pid = fork();
    if (worker_pid == 0) worker(r);
    if (worker_pid < 0) { error(&r, "worker_fork", errno); goto cleanup; }
    close(channels[WR_W]); channels[WR_W] = -1; close(channels[WC_R]); channels[WC_R] = -1;
    if (!recv_packet(&r, channels[WR_R], &p, H_WORKER_READY, WORKER, WORK_END, cf->fd) ||
        !bound_child(&r, WORKER, worker_pid, getpid(), &p.report.ids[WORKER], &p.report.product)) goto cleanup;
    r.closes[2] = p.report.closes[2];
    if (!open_pidfd(&r, &r.fds[F_GUARD_WORKER], &r.ids[WORKER]) ||
        !send_packet(&r, channels[GR_W], H_GUARD_WORKER_READY, GUARD, WORK_END, cf->fd) ||
        !recv_packet(&r, channels[GC_R], &p, H_ARM, COORD, WORK_END, cf->fd) || !recheck_worker(&r, 0)) goto cleanup;
    n = poll_once(&r, &r.polls[P_ALIVE], cf->fd, 0);
    if (n < 0) goto cleanup;
    if (n != 0 || r.polls[P_ALIVE].revents) { error(&r, "controller_early_exit", 0); goto cleanup; }
    if (!mark_time(&r, ARM_TIME)) goto cleanup;
    if (!send_packet(&r, channels[GR_W], H_ACK, GUARD, WORK_END, cf->fd) ||
        !wait_event(&r, &r.polls[P_GUARD_CTRL_EXIT], cf->fd, CLEAN_END)) goto cleanup;
    if (!mark_time(&r, CTRL_EXIT_TIME)) goto cleanup;
    r.worker_signal.known = 1;
    if (loss_case) {
        if (!recheck_worker(&r, 1)) goto cleanup;
        if (!mark_time(&r, SIGNAL_TIME)) goto cleanup;
        signal_owned(&r, &r.worker_signal, r.fds[F_GUARD_WORKER].fd);
        if (r.error[0]) goto cleanup;
    } else if (!send_packet(&r, channels[WC_W], H_WORKER_QUIT, GUARD, CLEAN_END, -1)) goto cleanup;
    if (!wait_event(&r, &r.polls[P_WORKER_EXIT], r.fds[F_GUARD_WORKER].fd, CLEAN_END)) goto cleanup;
    if (!mark_time(&r, WORKER_EXIT_TIME)) goto cleanup;
    if (!reap(&r, &r.waits[2], GUARD, worker_pid, CLEAN_END)) goto cleanup;
    if (!mark_time(&r, WORKER_REAP_TIME)) goto cleanup;
    if ((!loss_case && (!r.waits[2].exited || r.waits[2].exit_code)) ||
        (loss_case && (!r.waits[2].signaled || r.waits[2].term_signal != SIGKILL))) error(&r, "worker_status", 0);
cleanup:
    if (r.error[0] && r.fds[F_GUARD_WORKER].acquisition && !r.waits[2].observed &&
        recheck_worker(&r, 1) && within(&r, CLEAN_END)) {
        signal_owned(&r, &r.worker_signal, r.fds[F_GUARD_WORKER].fd);
        if (wait_event(&r, &r.polls[P_WORKER_EXIT], r.fds[F_GUARD_WORKER].fd, CLEAN_END)) {
            mark_time(&r, WORKER_EXIT_TIME);
            if (reap(&r, &r.waits[2], GUARD, worker_pid, CLEAN_END)) mark_time(&r, WORKER_REAP_TIME);
        }
    }
    close_pidfd(&r, &r.fds[F_GUARD_WORKER]); close_pidfd(&r, cf);
    mark_time(&r, TERMINAL_TIME);
    if (!send_packet(&r, channels[GR_W], H_TERMINAL, GUARD, TERMINAL_END, -1)) _exit(1);
    _exit(r.error[0] ? 1 : 0);
}
static void coordinator_cleanup(struct report *r, int index, int role)
{
    struct fd_fact *fd = &r->fds[index]; struct identity fresh; struct product product; struct pollfd p;
    struct signal_fact *signal = &r->coordinator_signals[role - 1];
    signal->known = 1;
    if (!fd->acquisition || r->waits[role - 1].observed) return;
    p = (struct pollfd){fd->fd, POLLIN, 0};
    if (poll(&p, 1, 0) == 0 && capture_identity(r->ids[role].pid, &fresh) &&
        same_id(&fresh, &r->ids[role]) && product_stat(&product) &&
        same_product(&product, &r->product)) signal_owned(r, signal, fd->fd);
    reap(r, &r->waits[role - 1], COORD, r->ids[role].pid, TOTAL_END);
}
static void jnumber(int known, int64_t value)
{ if (known) printf("%lld", (long long)value); else printf("null"); }
static void jidentity(const struct identity *id)
{
    if (!id->known) { printf("null"); return; }
    printf("{\"pid\":%lld,\"ppid\":%lld,\"uid\":%lld,\"euid\":%lld,\"start_ticks\":%lld,\"boot_id\":\"%s\"}",
        (long long)id->pid, (long long)id->ppid, (long long)id->uid, (long long)id->euid,
        (long long)id->start, id->boot);
}
static void jproduct(const struct product *p)
{ int n; if (!p->known) { printf("null"); return; } printf("[");
  for (n = 0; n < 7; n++) printf("%s%lld", n ? "," : "", (long long)p->stat[n]); printf("]"); }
static void jsignal(const struct signal_fact *f)
{
    if (!f->known) { printf("null"); return; }
    printf("{\"attempts\":%d,\"fd\":", f->attempts); jnumber(f->attempts, f->fd);
    printf(",\"number\":"); jnumber(f->attempts, f->number); printf(",\"flags\":"); jnumber(f->attempts, f->flags);
    printf(",\"result\":"); jnumber(f->observed, f->result); printf(",\"errno\":"); jnumber(f->observed, f->error); printf("}");
}
static void output(const struct report *r)
{
    int n, j; static const char *handles[] = {"coordinator_controller", "coordinator_guard", "guard_controller", "guard_worker"};
    static const char *polls[] = {"controller_alive_before_arm", "controller_exit", "guard_controller_exit", "worker_exit", "guard_exit"};
    static const char *checks[] = {"guard_before_arm", "worker_before_arm", "guard_before_signal", "worker_before_signal"};
    static const char *times[] = {"t0_ns", "work_ns", "cleanup_ns", "terminal_ns", "worker_ns", "total_ns",
        "guard_arm_ns", "guard_ack_ns", "controller_command_ns", "controller_exit_ns", "worker_signal_ns",
        "worker_exit_ns", "worker_reaped_ns", "guard_terminal_ns", "coordinator_final_ns"};
    printf("{\"schema_version\":1,\"scope\":\"frontier_v8_owned_C_direct_worker_lifecycle_fixture\","
           "\"status\":\"%s\",\"case\":\"%s\",\"nonce\":\"%s\",\"error\":{\"stage\":\"%s\",\"errno\":%d},",
        r->error[0] ? "failed" : "success", loss_case ? "controller_loss" : "normal", nonce,
        r->error[0] ? r->error : "none", r->error_errno);
    printf("\"headers\":{\"pidfd_open\":%ld,\"pidfd_send_signal\":%ld,\"sigkill\":%d,\"sigpipe\":%d,"
        "\"pollin\":%d,\"pollnval\":%d,\"ebadf\":%d,\"int_bytes\":%zu,\"long_bytes\":%zu,"
        "\"pointer_bytes\":%zu,\"char_bits\":%d,\"byte_order\":%d,\"packet_magic\":%u,"
        "\"identity_packet_bytes\":%zu,\"command_packet_bytes\":%zu,\"terminal_packet_bytes\":%zu,"
        "\"controller_loss_exit_code\":23},", (long)SYS_pidfd_open, (long)SYS_pidfd_send_signal,
        SIGKILL, SIGPIPE, POLLIN, POLLNVAL, EBADF, sizeof(int), sizeof(long), sizeof(void *), CHAR_BIT,
        __BYTE_ORDER__, MAGIC, sizeof(struct packet), sizeof(struct packet), sizeof(struct packet));
    printf("\"identities\":{"); for (n = 0; n < ROLES; n++) { printf("%s\"%s\":", n ? "," : "", roles[n]); jidentity(&r->ids[n]); } printf("},");
    printf("\"identity_rechecks\":{"); for (n = 0; n < 4; n++) { printf("%s\"%s\":", n ? "," : "", checks[n]); jidentity(&r->checks[n]); } printf("},\"product_identity\":"); jproduct(&r->product);
    printf(",\"product_rechecks\":{\"before_arm\":"); jproduct(&r->products[0]); printf(",\"before_signal\":"); jproduct(&r->products[1]); printf("},");
    printf("\"handshakes\":{"); for (n = 0; n < HANDSHAKES; n++) { const struct handshake *h = &r->hs[n];
        printf("%s\"%s\":", n ? "," : "", hs_names[n]); if (!h->known) printf("null"); else
        printf("{\"bytes\":%d,\"magic\":%u,\"kind\":\"%s\",\"role\":\"%s\",\"nonce\":\"%s\",\"case\":\"%s\"}",
            h->bytes, MAGIC, hs_names[h->kind], roles[h->role], nonce, loss_case ? "controller_loss" : "normal"); } printf("},");
    printf("\"pidfds\":{"); for (n = 0; n < HANDLES; n++) { const struct fd_fact *f = &r->fds[n];
        printf("%s\"%s\":", n ? "," : "", handles[n]); if (!f->known) { printf("null"); continue; }
        printf("{\"acquisition\":\"%s\",\"fd\":", f->acquisition == 1 ? "open" : f->acquisition == 2 ? "inherited" : "none"); jnumber(f->acquisition, f->fd);
        printf(",\"open_result\":"); jnumber(f->opened, f->open_result); printf(",\"open_errno\":"); jnumber(f->opened, f->open_errno);
        printf(",\"fdinfo_pid\":"); jnumber(f->fdinfo_known, f->fdinfo_pid); printf(",\"close_calls\":%d,\"close_result\":", f->close_calls);
        jnumber(f->close_known, f->close_result); printf(",\"close_errno\":"); jnumber(f->close_known, f->close_errno);
        printf(",\"ebadf_result\":"); jnumber(f->ebadf_known, f->ebadf_result); printf(",\"ebadf_errno\":"); jnumber(f->ebadf_known, f->ebadf_errno); printf("}"); } printf("},");
    printf("\"polls\":{"); for (n = 0; n < POLLS; n++) { const struct poll_fact *p = &r->polls[n];
        printf("%s\"%s\":", n ? "," : "", polls[n]); if (!p->known) { printf("null"); continue; }
        printf("{\"calls\":%d,\"fd\":%d,\"events\":%d,\"result\":", p->calls, p->fd, p->events); jnumber(p->observed, p->result);
        printf(",\"revents\":"); jnumber(p->observed, p->revents); printf(",\"errno\":"); jnumber(p->observed, p->error); printf("}"); } printf("},");
    printf("\"waits\":{"); for (n = 0; n < 3; n++) { const struct wait_fact *w = &r->waits[n];
        printf("%s\"%s\":", n ? "," : "", roles[n + 1]); if (!w->known) { printf("null"); continue; }
        printf("{\"owner\":\"%s\",\"calls\":%d,\"pid\":%lld,\"result\":", roles[w->owner], w->calls, (long long)w->pid); jnumber(w->observed, w->result);
        printf(",\"status\":"); jnumber(w->observed && w->result > 0, w->status); printf(",\"errno\":"); jnumber(w->calls, w->error);
        printf(",\"exited\":%s,\"exit_code\":", !w->observed || w->result <= 0 ? "null" : w->exited ? "true" : "false"); jnumber(w->observed && w->result > 0 && w->exited, w->exit_code);
        printf(",\"signaled\":%s,\"term_signal\":", !w->observed || w->result <= 0 ? "null" : w->signaled ? "true" : "false"); jnumber(w->observed && w->result > 0 && w->signaled, w->term_signal); printf("}"); } printf("},\"worker_signal\":"); jsignal(&r->worker_signal);
    printf(",\"coordinator_cleanup_signals\":{\"controller\":"); jsignal(&r->coordinator_signals[0]); printf(",\"guard\":"); jsignal(&r->coordinator_signals[1]); printf("},");
    printf("\"inherited_closes\":{"); for (n = 0; n < 3; n++) { const struct closes *c = &r->closes[n]; printf("%s\"%s\":", n ? "," : "", roles[n + 1]);
        if (!c->known) { printf("null"); continue; } printf("["); for (j = 0; j < c->count; j++) { const struct close_fact *f = &c->row[j];
            printf("%s{\"fd\":%d,\"kind\":\"%s\",\"result\":%d,\"errno\":%d,\"ebadf_result\":%d,\"ebadf_errno\":%d}",
                j ? "," : "", f->fd, fd_names[f->kind], f->result, f->error, f->ebadf_result, f->ebadf_errno); } printf("]"); } printf("},");
    printf("\"deadlines\":{"); for (n = 0; n < TIMES; n++) { printf("%s\"%s\":", n ? "," : "", times[n]); jnumber(r->time_known & (1U << n), r->times[n]); } printf("},\"self_sigpipe_ignore\":");
    if (r->ignore_known) printf("{\"result\":%d,\"errno\":%d}", r->ignore_result, r->ignore_errno); else printf("null"); printf("}\n");
}
int main(int argc, char **argv)
{
    struct report r = {0}; struct packet p; int n; pid_t ctrl = -1, g = -1; int64_t t0;
    for (n = 0; n < CHANNELS; n++) channels[n] = -1;
    if (argc != 3 || (strcmp(argv[1], "normal") && strcmp(argv[1], "controller_loss")) || strlen(argv[2]) != 64) return 2;
    for (n = 0; n < 64; n++) if (!strchr("0123456789abcdef", argv[2][n])) return 2;
    loss_case = !strcmp(argv[1], "controller_loss"); memcpy(nonce, argv[2], 65);
    t0 = clock_now(&r);
    if (t0 > INT64_MAX - 14 * NS) { error(&r, "clock_range", 0); t0 = -1; }
    if (t0 >= 0) { int offsets[] = {0,5,8,10,12,14}; for (n = 0; n < 6; n++) { r.times[n] = t0 + offsets[n] * NS; r.time_known |= 1U << n; } }
    product_fd = open("/proc/self/exe", O_RDONLY | O_CLOEXEC);
    if (product_fd < 0 || !product_stat(&r.product) || !capture_identity(getpid(), &r.ids[COORD])) error(&r, "coordinator_identity", errno);
    { struct sigaction sa = {0}; sa.sa_handler = SIG_IGN; sigemptyset(&sa.sa_mask);
      r.ignore_known = 1; errno = 0; r.ignore_result = sigaction(SIGPIPE, &sa, NULL); r.ignore_errno = errno;
      if (r.ignore_result) error(&r, "sigpipe", r.ignore_errno); }
    if (r.error[0] || !make_pipe(&r, CR_R) || !make_pipe(&r, CC_R) || !make_pipe(&r, GR_R) || !make_pipe(&r, GC_R)) goto done;
    ctrl = fork();
    if (ctrl == 0) controller(r);
    if (ctrl < 0) { error(&r, "controller_fork", errno); goto done; }
    close(channels[CR_W]); channels[CR_W] = -1; close(channels[CC_R]); channels[CC_R] = -1;
    if (!recv_packet(&r, channels[CR_R], &p, H_CTRL_READY, CTRL, WORK_END, -1) ||
        !bound_child(&r, CTRL, ctrl, getpid(), &p.report.ids[CTRL], &p.report.product)) goto done;
    r.closes[0] = p.report.closes[0];
    close(channels[CR_R]); channels[CR_R] = -1;
    if (!open_pidfd(&r, &r.fds[F_COORD_CTRL], &r.ids[CTRL])) goto done;
    g = fork();
    if (g == 0) guard(r);
    if (g < 0) { error(&r, "guard_fork", errno); goto done; }
    close(channels[GR_W]); channels[GR_W] = -1; close(channels[GC_R]); channels[GC_R] = -1;
    if (!recv_packet(&r, channels[GR_R], &p, H_GUARD_READY, GUARD, WORK_END, r.fds[F_COORD_CTRL].fd) ||
        !bound_child(&r, GUARD, g, getpid(), &p.report.ids[GUARD], &p.report.product) ||
        !open_pidfd(&r, &r.fds[F_COORD_GUARD], &r.ids[GUARD]) ||
        !send_packet(&r, channels[GC_W], H_GUARD_START, COORD, WORK_END, r.fds[F_COORD_CTRL].fd) ||
        !recv_packet(&r, channels[GR_R], &p, H_GUARD_WORKER_READY, GUARD, WORK_END, r.fds[F_COORD_CTRL].fd)) goto done;
    if (!bound_child(&r, WORKER, p.report.ids[WORKER].pid, g, &p.report.ids[WORKER], &p.report.product)) goto done;
    r.closes[1] = p.report.closes[1]; r.closes[2] = p.report.closes[2];
    if (!send_packet(&r, channels[GC_W], H_ARM, COORD, WORK_END, r.fds[F_COORD_CTRL].fd) ||
        !recv_packet(&r, channels[GR_R], &p, H_ACK, GUARD, WORK_END, r.fds[F_COORD_CTRL].fd)) goto done;
    if (!mark_time(&r, ACK_TIME) || !mark_time(&r, COMMAND_TIME)) goto done;
    if (!send_packet(&r, channels[CC_W], H_CTRL_QUIT, COORD, WORK_END, -1) ||
        !wait_event(&r, &r.polls[P_CTRL_EXIT], r.fds[F_COORD_CTRL].fd, CLEAN_END) ||
        !recv_packet(&r, channels[GR_R], &p, H_TERMINAL, GUARD, TERMINAL_END, -1)) goto done;
    merge_guard(&r, &p.report);
    if (!wait_event(&r, &r.polls[P_GUARD_EXIT], r.fds[F_COORD_GUARD].fd, TOTAL_END) ||
        !reap(&r, &r.waits[0], COORD, ctrl, TOTAL_END) || !reap(&r, &r.waits[1], COORD, g, TOTAL_END)) goto done;
    if (!r.waits[0].exited || r.waits[0].exit_code != (loss_case ? 23 : 0) ||
        !r.waits[1].exited || r.waits[1].exit_code) error(&r, "coordinator_status", 0);
done:
    r.coordinator_signals[0].known = r.coordinator_signals[1].known = 1;
    if (r.error[0]) { coordinator_cleanup(&r, F_COORD_CTRL, CTRL); coordinator_cleanup(&r, F_COORD_GUARD, GUARD); }
    close_pidfd(&r, &r.fds[F_COORD_CTRL]); close_pidfd(&r, &r.fds[F_COORD_GUARD]);
    mark_time(&r, FINAL_TIME); output(&r);
    if (fflush(stdout)) return 1;
    return r.error[0] ? 1 : 0;
}
