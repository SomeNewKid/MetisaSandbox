/* Issue harmless syscall attempts under the container's inherited filter.
 * No filter is installed here: the helper must test Docker's actual policy.
 */
#define _GNU_SOURCE

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/ptrace.h>
#include <sys/syscall.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    long result;
    int syscall_errno;

    if (argc != 2) {
        return 2;
    }

    errno = 0;
    if (strcmp(argv[1], "ptrace") == 0) {
        /* Read from an invalid PID. Never attach to or stop another process. */
        result = syscall(SYS_ptrace, PTRACE_PEEKDATA, -1, 0, 0);
    } else if (strcmp(argv[1], "process_vm_readv") == 0) {
        /* Zero vectors targeting ourselves: no memory is read or written. */
        result = syscall(SYS_process_vm_readv, getpid(), NULL, 0UL, NULL, 0UL, 0UL);
    } else if (strcmp(argv[1], "process_vm_writev") == 0) {
        result = syscall(SYS_process_vm_writev, getpid(), NULL, 0UL, NULL, 0UL, 0UL);
    } else {
        return 2;
    }
    syscall_errno = errno;

    printf("{\"syscall\":\"%s\",\"result\":%ld,\"errno\":%d}\n",
           argv[1], result, syscall_errno);
    return 0;
}
