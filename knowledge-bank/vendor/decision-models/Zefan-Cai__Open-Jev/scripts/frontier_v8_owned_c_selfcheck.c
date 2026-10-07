/* Dedicated owned-PID runtime selfcheck; this is not a containment guard. */
#if !defined(__linux__) || !defined(_GNU_SOURCE)
#error "Declared Linux GNU feature environment required"
#endif

#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>
#include <limits.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>

#if !defined(SYS_pidfd_open) || !defined(__SIZEOF_INT__) || \
    !defined(__SIZEOF_LONG__) || !defined(__SIZEOF_POINTER__) || \
    !defined(__CHAR_BIT__) || !defined(__BYTE_ORDER__)
#error "Declared header constant and compiler target builtins required"
#endif

const long frontier_v8_header_pidfd_open = SYS_pidfd_open;
const unsigned int frontier_v8_target_int_bytes = __SIZEOF_INT__;
const unsigned int frontier_v8_target_long_bytes = __SIZEOF_LONG__;
const unsigned int frontier_v8_target_pointer_bytes = __SIZEOF_POINTER__;
const unsigned int frontier_v8_target_char_bits = __CHAR_BIT__;
const unsigned int frontier_v8_target_byte_order = __BYTE_ORDER__;

_Static_assert(sizeof(int) == __SIZEOF_INT__, "Compiler int size differs");
_Static_assert(sizeof(long) == __SIZEOF_LONG__, "Compiler long size differs");
_Static_assert(sizeof(void *) == __SIZEOF_POINTER__, "Compiler pointer size differs");
_Static_assert(CHAR_BIT == __CHAR_BIT__, "Compiler character size differs");
_Static_assert(SYS_pidfd_open >= 0, "Header constant must be nonnegative");
_Static_assert(SYS_pidfd_open <= LONG_MAX, "Header constant must fit syscall number");
_Static_assert(sizeof(pid_t) <= sizeof(long), "PID must fit declared syscall operand");

struct facts {
    const char *error_stage;
    int error_errno;
    long pid;
    long ppid;
    unsigned long uid;
    unsigned long euid;
    long proc_self_pid;
    int open_attempted;
    int pidfd_acquired;
    int pidfd;
    long fdinfo_pid;
    int fdinfo_verified;
    int poll_attempted;
    unsigned int poll_events;
    int poll_result;
    unsigned int poll_revents;
    int close_attempted;
    int close_calls;
    int close_result;
    int close_errno;
    int ebadf_check_attempted;
    int ebadf_result;
    int ebadf_errno;
    int ebadf_verified;
};

static void fail(struct facts *facts, const char *stage, int saved_errno)
{
    if (strcmp(facts->error_stage, "none") == 0) {
        facts->error_stage = stage;
        facts->error_errno = saved_errno;
    }
}

/* These stream descriptors are separate from the once-closed owned pidfd. */
static int read_proc(const char *path, char *body, size_t *size,
                     struct facts *facts, const char *open_stage,
                     const char *read_stage, const char *close_stage)
{
    FILE *stream = fopen(path, "r");
    size_t count;
    int saved_errno;
    if (stream == NULL) {
        fail(facts, open_stage, errno);
        return 0;
    }
    errno = 0;
    count = fread(body, 1, 4097, stream);
    saved_errno = errno;
    if (ferror(stream)) {
        fail(facts, read_stage, saved_errno);
    } else if (count > 4096 || memchr(body, '\0', count) != NULL) {
        fail(facts, read_stage, 0);
    }
    errno = 0;
    if (fclose(stream) != 0) {
        fail(facts, close_stage, errno);
    }
    if (strcmp(facts->error_stage, "none") != 0) {
        return 0;
    }
    body[count] = '\0';
    *size = count;
    return 1;
}

static int decimal_pid(const char *begin, const char *end, long *value)
{
    long number = 0;
    const char *cursor = begin;
    if (begin == end) {
        return 0;
    }
    while (cursor < end) {
        int digit = *cursor - '0';
        if (digit < 0 || digit > 9 || number > (LONG_MAX - digit) / 10) {
            return 0;
        }
        number = number * 10 + digit;
        cursor++;
    }
    if (number <= 0) {
        return 0;
    }
    *value = number;
    return 1;
}

static void verify_proc_pid(struct facts *facts)
{
    char body[4098];
    size_t size = 0;
    const char *space;
    if (!read_proc("/proc/self/stat", body, &size, facts,
                   "proc_stat_open", "proc_stat_read", "proc_stat_close")) {
        return;
    }
    space = memchr(body, ' ', size);
    if (space == NULL || space + 1 >= body + size || space[1] != '(' ||
        !decimal_pid(body, space, &facts->proc_self_pid) ||
        facts->proc_self_pid != facts->pid) {
        fail(facts, "proc_stat_pid", 0);
    }
}

static void verify_fdinfo(struct facts *facts)
{
    char path[64];
    char body[4098];
    size_t size = 0;
    const char *cursor;
    const char *end;
    int seen_pid = 0;
    int length = snprintf(path, sizeof(path), "/proc/self/fdinfo/%d", facts->pidfd);
    if (length <= 0 || (size_t)length >= sizeof(path)) {
        fail(facts, "fdinfo_path", 0);
        return;
    }
    if (!read_proc(path, body, &size, facts,
                   "fdinfo_open", "fdinfo_read", "fdinfo_close")) {
        return;
    }
    cursor = body;
    end = body + size;
    while (cursor < end) {
        const char *newline = memchr(cursor, '\n', (size_t)(end - cursor));
        if (newline == NULL) {
            fail(facts, "fdinfo_parse", 0);
            return;
        }
        if (newline - cursor >= 4 && memcmp(cursor, "Pid:", 4) == 0) {
            const char *begin = cursor + 4;
            const char *finish = newline;
            seen_pid++;
            while (begin < finish && (*begin == ' ' || *begin == '\t')) {
                begin++;
            }
            while (finish > begin && (finish[-1] == ' ' || finish[-1] == '\t')) {
                finish--;
            }
            if (seen_pid != 1 || !decimal_pid(begin, finish, &facts->fdinfo_pid)) {
                fail(facts, "fdinfo_parse", 0);
                return;
            }
        }
        cursor = newline + 1;
    }
    if (seen_pid != 1 || facts->fdinfo_pid != facts->pid) {
        fail(facts, "fdinfo_pid", 0);
        return;
    }
    facts->fdinfo_verified = 1;
}

int main(int argc, char **argv)
{
    struct facts facts = {0};
    long opened;
    struct pollfd poll_fd;
    int saved_errno;
    int printed;
    (void)argv;
    facts.error_stage = "none";
    facts.pid = (long)getpid();
    facts.ppid = (long)getppid();
    facts.uid = (unsigned long)getuid();
    facts.euid = (unsigned long)geteuid();
    facts.proc_self_pid = -1;
    facts.pidfd = -1;
    facts.fdinfo_pid = -1;
    facts.poll_result = -1;
    facts.close_result = -1;
    if (argc != 1) {
        fail(&facts, "arguments", 0);
    } else {
        verify_proc_pid(&facts);
    }
    if (strcmp(facts.error_stage, "none") == 0) {
        facts.open_attempted = 1;
        errno = 0;
        opened = syscall((long)SYS_pidfd_open, (long)getpid(), (unsigned long)0);
        saved_errno = errno;
        if (opened < 0) {
            fail(&facts, "pidfd_open", saved_errno);
        } else if (opened > INT_MAX) {
            fail(&facts, "pidfd_range", 0);
        } else {
            facts.pidfd_acquired = 1;
            facts.pidfd = (int)opened;
            verify_fdinfo(&facts);
            if (strcmp(facts.error_stage, "none") == 0) {
                poll_fd.fd = facts.pidfd;
                poll_fd.events = POLLIN;
                poll_fd.revents = 0;
                facts.poll_attempted = 1;
                facts.poll_events = (unsigned short)poll_fd.events;
                errno = 0;
                facts.poll_result = poll(&poll_fd, 1, 0);
                saved_errno = errno;
                facts.poll_revents = (unsigned short)poll_fd.revents;
                if (facts.poll_result < 0) {
                    fail(&facts, "poll", saved_errno);
                } else if (facts.poll_result != 0 || facts.poll_revents != 0) {
                    fail(&facts, "poll_ready", 0);
                }
            }
        }
    }
    if (facts.pidfd_acquired) {
        facts.close_attempted = 1;
        facts.close_calls = 1;
        errno = 0;
        facts.close_result = close(facts.pidfd);
        facts.close_errno = errno;
        if (facts.close_result != 0) {
            fail(&facts, "close", facts.close_errno);
        } else {
            /* No descriptor-opening operation occurs between close and fcntl. */
            facts.ebadf_check_attempted = 1;
            errno = 0;
            facts.ebadf_result = fcntl(facts.pidfd, F_GETFD);
            facts.ebadf_errno = errno;
            if (facts.ebadf_result == -1 && facts.ebadf_errno == EBADF) {
                facts.ebadf_verified = 1;
            } else {
                fail(&facts, "fcntl_ebadf", facts.ebadf_errno);
            }
        }
    }
    printed = printf("{\"schema_version\":1,\"status\":\"%s\","
        "\"error_stage\":\"%s\",\"error_errno\":%d,\"pid\":%ld,\"ppid\":%ld,"
        "\"uid\":%lu,\"euid\":%lu,\"proc_self_pid\":%ld,\"header_pidfd_open\":%ld,"
        "\"int_bytes\":%zu,\"long_bytes\":%zu,\"pointer_bytes\":%zu,"
        "\"char_bits\":%d,\"byte_order\":%d,\"header_pollin\":%d,"
        "\"header_ebadf\":%d,\"open_attempted\":%s,"
        "\"pidfd_acquired\":%s,\"pidfd\":%d,\"fdinfo_pid\":%ld,"
        "\"fdinfo_verified\":%s,\"poll_attempted\":%s,\"poll_events\":%u,"
        "\"poll_result\":%d,"
        "\"poll_revents\":%u,\"close_attempted\":%s,\"close_calls\":%d,"
        "\"close_result\":%d,\"close_errno\":%d,\"ebadf_check_attempted\":%s,"
        "\"ebadf_result\":%d,\"ebadf_errno\":%d,\"ebadf_verified\":%s}\n",
        strcmp(facts.error_stage, "none") == 0 ? "success" : "failed",
        facts.error_stage, facts.error_errno, facts.pid, facts.ppid, facts.uid,
        facts.euid, facts.proc_self_pid, (long)SYS_pidfd_open,
        sizeof(int), sizeof(long), sizeof(void *), CHAR_BIT, __BYTE_ORDER__,
        POLLIN, EBADF,
        facts.open_attempted ? "true" : "false",
        facts.pidfd_acquired ? "true" : "false", facts.pidfd, facts.fdinfo_pid,
        facts.fdinfo_verified ? "true" : "false", facts.poll_attempted ? "true" : "false",
        facts.poll_events, facts.poll_result, facts.poll_revents,
        facts.close_attempted ? "true" : "false",
        facts.close_calls, facts.close_result, facts.close_errno,
        facts.ebadf_check_attempted ? "true" : "false",
        facts.ebadf_result, facts.ebadf_errno,
        facts.ebadf_verified ? "true" : "false");
    if (printed < 0 || fflush(stdout) != 0) {
        return 1;
    }
    return strcmp(facts.error_stage, "none") == 0 ? 0 : 1;
}
