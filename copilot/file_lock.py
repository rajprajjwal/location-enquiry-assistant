"""Non-blocking exclusive file locks that work on POSIX (fcntl) and Windows (msvcrt).

Both functions take an open file object or an integer file descriptor. ``try_lock`` raises ``BlockingIOError`` when another
process holds the lock, on every platform, so callers handle one exception type. The operating system releases the lock if the
process dies.
"""
import os

if os.name == "nt":
    import msvcrt

    def _fd(handle):
        return handle if isinstance(handle, int) else handle.fileno()

    def try_lock(handle):
        descriptor = _fd(handle)
        os.lseek(descriptor, 0, os.SEEK_SET)  # Windows locks a byte range from the current position
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise BlockingIOError(str(error)) from None

    def unlock(handle):
        descriptor = _fd(handle)
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def try_lock(handle):
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def unlock(handle):
        fcntl.flock(handle, fcntl.LOCK_UN)
