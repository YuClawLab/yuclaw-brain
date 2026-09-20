"""Restricted-worker bootstrap. Runs as its own process BEFORE any untrusted byte is read, confines itself, then execs the worker.

    <python> -I -S -B sandbox_bootstrap.py <backend> <worker.py> <mode> <input file>

Standard library only; never imported by the server (the server starts it with a fixed argument structure and an empty
environment). Both backends apply the resource limits below; `landlock` then confines THIS process with the kernel's
Landlock LSM and a seccomp filter and execs the interpreter; `bwrap` execs bubblewrap with a fixed policy.

What the `landlock` backend denies (each item is probed by the capability check, not assumed):
  * file reads outside {interpreter runtime, system libraries, the worker file, the one staged input}; ALL file writes,
    creations, removals, renames and device ioctls (no writable path exists; results leave on stdout only);
  * every socket: socket/socketpair/connect/bind/listen/accept/send*/recv* return EPERM (seccomp), and TCP bind/connect
    is also refused by Landlock where the kernel supports it — so no TCP, UDP, raw or unix-socket traffic;
  * ptrace, process_vm_readv/writev, signals to other processes (seccomp; Landlock signal scope on ABI >= 6), io_uring,
    bpf, perf events, userfaultfd, mount/namespace/keyring/module/kexec/reboot calls;
  * new privileges (PR_SET_NO_NEW_PRIVS), core dumps, more than the fixed CPU seconds, address space, file size and
    descriptors; new processes and threads (RLIMIT_NPROC, set by the worker before it reads input).
What it does NOT provide: a separate PID, mount or user namespace; protection from a kernel vulnerability; any defence
against the same OS user acting outside this process. It is a process confinement, not a container.

The `bwrap` backend adds mount, PID, IPC, UTS, cgroup and network namespaces with a read-only runtime and only the staged
input bound in. It needs unprivileged user namespaces for bubblewrap, which some hosts deny (Ubuntu's AppArmor
restriction): the capability check then reports it unavailable and it is never used. Nothing here weakens host security."""
import ctypes
import errno
import os
import platform
import resource
import struct
import sys

LIMITS = {"cpu_seconds": 20, "address_space": 1024 * 1024 * 1024, "file_size": 0, "open_files": 64, "core": 0}

# -- Landlock (linux/landlock.h)
_SYS_CREATE, _SYS_ADD, _SYS_RESTRICT = 444, 445, 446
_FS = {"EXECUTE": 1 << 0, "WRITE_FILE": 1 << 1, "READ_FILE": 1 << 2, "READ_DIR": 1 << 3, "REMOVE_DIR": 1 << 4, "REMOVE_FILE": 1 << 5, "MAKE_CHAR": 1 << 6, "MAKE_DIR": 1 << 7,
       "MAKE_REG": 1 << 8, "MAKE_SOCK": 1 << 9, "MAKE_FIFO": 1 << 10, "MAKE_BLOCK": 1 << 11, "MAKE_SYM": 1 << 12, "REFER": 1 << 13, "TRUNCATE": 1 << 14, "IOCTL_DEV": 1 << 15}
_NET_BIND_TCP, _NET_CONNECT_TCP = 1 << 0, 1 << 1
_SCOPE_ABSTRACT_UNIX, _SCOPE_SIGNAL = 1 << 0, 1 << 1
_READ_EXEC = _FS["EXECUTE"] | _FS["READ_FILE"] | _FS["READ_DIR"]

# -- seccomp: syscalls that return EPERM (everything else is allowed; the default-deny layer for files is Landlock)
_DENY = {
    "aarch64": {"socket": 198, "socketpair": 199, "bind": 200, "listen": 201, "accept": 202, "connect": 203, "sendto": 206, "recvfrom": 207, "sendmsg": 211, "recvmsg": 212, "accept4": 242,
                "recvmmsg": 243, "sendmmsg": 269, "ptrace": 117, "process_vm_readv": 270, "process_vm_writev": 271, "kill": 129, "tkill": 130, "tgkill": 131, "rt_sigqueueinfo": 138,
                "rt_tgsigqueueinfo": 240, "pidfd_send_signal": 424, "pidfd_open": 434, "pidfd_getfd": 438, "io_uring_setup": 425, "io_uring_enter": 426, "io_uring_register": 427, "bpf": 280,
                "perf_event_open": 241, "userfaultfd": 282, "mount": 40, "umount2": 39, "pivot_root": 41, "chroot": 51, "setns": 268, "unshare": 97, "keyctl": 219, "add_key": 217,
                "request_key": 218, "kexec_load": 104, "init_module": 105, "delete_module": 106, "finit_module": 273, "reboot": 142, "swapon": 224, "swapoff": 225, "open_by_handle_at": 265,
                "name_to_handle_at": 264, "open_tree": 428, "move_mount": 429, "fsopen": 430, "fsconfig": 431, "fsmount": 432},
    "x86_64": {"socket": 41, "connect": 42, "accept": 43, "sendto": 44, "recvfrom": 45, "sendmsg": 46, "recvmsg": 47, "bind": 49, "listen": 50, "socketpair": 53, "accept4": 288,
               "recvmmsg": 299, "sendmmsg": 307, "ptrace": 101, "process_vm_readv": 310, "process_vm_writev": 311, "kill": 62, "tkill": 200, "tgkill": 234, "rt_sigqueueinfo": 129,
               "rt_tgsigqueueinfo": 297, "pidfd_send_signal": 424, "pidfd_open": 434, "pidfd_getfd": 438, "io_uring_setup": 425, "io_uring_enter": 426, "io_uring_register": 427, "bpf": 321,
               "perf_event_open": 298, "userfaultfd": 323, "mount": 165, "umount2": 166, "pivot_root": 155, "chroot": 161, "setns": 308, "unshare": 272, "keyctl": 250, "add_key": 248,
               "request_key": 249, "kexec_load": 246, "init_module": 175, "delete_module": 176, "finit_module": 313, "reboot": 169, "swapon": 167, "swapoff": 168, "open_by_handle_at": 304,
               "name_to_handle_at": 303, "open_tree": 428, "move_mount": 429, "fsopen": 430, "fsconfig": 431, "fsmount": 432},
}
_AUDIT_ARCH = {"aarch64": 0xC00000B7, "x86_64": 0xC000003E}
_RET_KILL, _RET_ALLOW, _RET_EPERM = 0x80000000, 0x7FFF0000, 0x00050000 | errno.EPERM


def _fail(msg: str, code: int = 97):
    sys.stderr.write("[sandbox-bootstrap] " + msg + "\n"); sys.stderr.flush(); os._exit(code)


def apply_limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (LIMITS["cpu_seconds"], LIMITS["cpu_seconds"]))
    resource.setrlimit(resource.RLIMIT_AS, (LIMITS["address_space"], LIMITS["address_space"]))
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMITS["file_size"], LIMITS["file_size"]))
    resource.setrlimit(resource.RLIMIT_NOFILE, (LIMITS["open_files"], LIMITS["open_files"]))


def close_inherited():
    for fd in range(3, 4096):
        try:
            os.close(fd)
        except OSError:
            pass


def runtime_roots() -> list:
    roots = {os.path.realpath(sys.base_prefix), os.path.realpath(sys.base_exec_prefix)}
    for p in ("/usr/lib", "/usr/lib64", "/lib", "/lib64", "/etc/ld.so.cache", "/etc/ld.so.conf", "/etc/ld.so.conf.d"):
        if os.path.exists(p):
            roots.add(os.path.realpath(p))
    return sorted(roots)


def landlock_abi(libc) -> int:
    v = libc.syscall(_SYS_CREATE, None, 0, 1)
    return v if v > 0 else 0


def apply_landlock(libc, read_exec_paths, read_only_files) -> dict:
    abi = landlock_abi(libc)
    if abi < 1:
        _fail("Landlock is not available in this kernel")
    handled = 0
    for name, bit in _FS.items():
        if name == "REFER" and abi < 2 or name == "TRUNCATE" and abi < 3 or name == "IOCTL_DEV" and abi < 5:
            continue
        handled |= bit
    net = (_NET_BIND_TCP | _NET_CONNECT_TCP) if abi >= 4 else 0
    scoped = (_SCOPE_ABSTRACT_UNIX | _SCOPE_SIGNAL) if abi >= 6 else 0
    attr = struct.pack("QQQ", handled, net, scoped)[: 8 if abi < 4 else 16 if abi < 6 else 24]
    fd = libc.syscall(_SYS_CREATE, ctypes.c_char_p(attr), ctypes.c_size_t(len(attr)), 0)
    if fd < 0:
        _fail(f"landlock_create_ruleset failed (errno {ctypes.get_errno()})")

    def allow(path, access):
        try:
            pfd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        except OSError as exc:
            _fail(f"cannot open allow-listed path: {exc.strerror}")
        if not os.path.isdir(path):
            access &= _FS["EXECUTE"] | _FS["READ_FILE"]
        rule = struct.pack("=Qi", access & handled, pfd)
        if libc.syscall(_SYS_ADD, fd, 1, ctypes.c_char_p(rule), 0) != 0:
            _fail(f"landlock_add_rule failed (errno {ctypes.get_errno()})")
        os.close(pfd)
    for p in read_exec_paths:
        allow(p, _READ_EXEC)
    for p in read_only_files:
        allow(p, _FS["READ_FILE"])
    if libc.prctl(38, 1, 0, 0, 0) != 0:                               # PR_SET_NO_NEW_PRIVS
        _fail("PR_SET_NO_NEW_PRIVS failed")
    if libc.syscall(_SYS_RESTRICT, fd, 0) != 0:
        _fail(f"landlock_restrict_self failed (errno {ctypes.get_errno()})")
    os.close(fd)
    return {"landlock_abi": abi, "tcp_rules": bool(net), "signal_scope": bool(scoped)}


def apply_seccomp(libc) -> int:
    arch = platform.machine()
    if arch not in _DENY:
        _fail(f"no seccomp table for architecture {arch!r}")
    deny = sorted(set(_DENY[arch].values()))
    prog = [(0x20, 0, 0, 4), (0x15, 1, 0, _AUDIT_ARCH[arch]), (0x06, 0, 0, _RET_KILL), (0x20, 0, 0, 0)]
    if arch == "x86_64":                                                # the x32 ABI shares the arch value: refuse its syscall range
        prog += [(0x35, 0, 1, 0x40000000), (0x06, 0, 0, _RET_KILL)]
    n = len(deny)
    for i, nr in enumerate(deny):
        prog.append((0x15, n - i, 0, nr))                               # match -> jump to the EPERM return
    prog += [(0x06, 0, 0, _RET_ALLOW), (0x06, 0, 0, _RET_EPERM)]
    raw = b"".join(struct.pack("HBBI", *ins) for ins in prog)
    buf = ctypes.create_string_buffer(raw, len(raw))

    class Fprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]
    fp = Fprog(len(prog), ctypes.cast(buf, ctypes.c_void_p))
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        _fail("PR_SET_NO_NEW_PRIVS failed")
    if libc.prctl(22, 2, ctypes.byref(fp), 0, 0) != 0:                   # PR_SET_SECCOMP, SECCOMP_MODE_FILTER
        _fail(f"seccomp filter refused (errno {ctypes.get_errno()})")
    return n


def bwrap_argv(python: str, worker: str, mode: str, input_path: str) -> list:
    args = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv", "--cap-drop", "ALL", "--hostname", "yuclaw-shd-worker"]
    for p in runtime_roots():
        args += ["--ro-bind", p, p]
    for link, target in (("/lib", "usr/lib"), ("/lib64", "usr/lib64"), ("/bin", "usr/bin")):
        if os.path.islink(link):
            args += ["--symlink", target, link]
    args += ["--ro-bind", worker, "/worker.py", "--ro-bind", input_path, "/input", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--chdir", "/",
             "--", python, "-I", "-S", "-B", "/worker.py", mode, "/input"]
    return args


def main(argv) -> int:
    if len(argv) != 5 or argv[1] not in ("landlock", "bwrap") or argv[3] not in ("verify", "probe", "spin", "flood"):
        _fail("usage: sandbox_bootstrap.py <landlock|bwrap> <worker.py> <verify|probe|spin|flood> <input>", 96)
    backend, worker, mode, input_path = argv[1], os.path.realpath(argv[2]), argv[3], os.path.realpath(argv[4])
    python = os.path.realpath(sys.executable)
    os.chdir("/"); os.umask(0o077)
    close_inherited(); apply_limits()
    if backend == "bwrap":
        os.execvpe("bwrap", bwrap_argv(python, worker, mode, input_path), {})
    libc = ctypes.CDLL(None, use_errno=True)
    apply_landlock(libc, runtime_roots(), [worker, input_path])
    apply_seccomp(libc)
    os.execve(python, [python, "-I", "-S", "-B", worker, mode, input_path], {})
    return 98


if __name__ == "__main__":
    sys.exit(main(sys.argv))
