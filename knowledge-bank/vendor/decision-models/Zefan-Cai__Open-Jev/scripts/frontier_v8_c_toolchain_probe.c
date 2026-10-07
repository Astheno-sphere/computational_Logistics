/* Compile-target declarations only; this translation unit is never linked or run. */
#if !defined(__linux__) || !defined(_GNU_SOURCE)
#error "Declared Linux GNU feature environment required"
#endif

#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>
#include <limits.h>

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
