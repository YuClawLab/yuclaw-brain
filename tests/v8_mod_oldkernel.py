"""Test harness: run a Python command in a process for which the kernel's three Landlock system calls answer ENOSYS — exactly
what a kernel without Landlock (before 5.13, or built without it) answers — and with a PATH that holds no bubblewrap.

An unprivileged seccomp filter does this; it is inherited by every child, so the REAL capability probe, bootstrap and worker
of the product run unchanged and find no isolation facility. Nothing in the product is patched or mocked. This SIMULATES an
unsupported Linux kernel on this host; it is not a run on another operating system.

    python v8_mod_oldkernel.py <script.py> [args...]"""
import ctypes, errno, os, platform, struct, sys

LANDLOCK_SYSCALLS = (444, 445, 446)                                             # landlock_create_ruleset / add_rule / restrict_self: same numbers on aarch64 and x86-64
AUDIT_ARCH = {"aarch64": 0xC00000B7, "x86_64": 0xC000003E}


def deny_landlock():
    arch = platform.machine(); n = len(LANDLOCK_SYSCALLS)
    prog = [(0x20, 0, 0, 4), (0x15, 1, 0, AUDIT_ARCH[arch]), (0x06, 0, 0, 0x7FFF0000), (0x20, 0, 0, 0)]        # another ABI: leave it alone
    prog += [(0x15, n - i, 0, nr) for i, nr in enumerate(LANDLOCK_SYSCALLS)] + [(0x06, 0, 0, 0x7FFF0000), (0x06, 0, 0, 0x00050000 | errno.ENOSYS)]
    raw = b"".join(struct.pack("HBBI", *ins) for ins in prog); buf = ctypes.create_string_buffer(raw, len(raw))

    class Fprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]
    libc = ctypes.CDLL(None, use_errno=True); fp = Fprog(len(prog), ctypes.cast(buf, ctypes.c_void_p))
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(22, 2, ctypes.byref(fp), 0, 0) != 0:
        sys.exit(f"[oldkernel] the seccomp filter could not be installed (errno {ctypes.get_errno()})")
    assert libc.syscall(444, None, 0, 1) == -1 and ctypes.get_errno() == errno.ENOSYS, "Landlock still answers"


if __name__ == "__main__":
    deny_landlock(); os.environ["PATH"] = "/nonexistent-for-this-test"; os.execv(sys.executable, [sys.executable, *sys.argv[1:]])
