from __future__ import print_function, division, absolute_import

import errno
import fcntl
import os
import threading
import weakref
from contextlib import contextmanager
from datetime import datetime, timedelta

from .compatibility import unicode, UTC


_paths_lock = threading.Lock()
_paths_to_locks = weakref.WeakValueDictionary()


def lock_file(path):
    """File based lock on ``path``.

    Creates a file based lock. When acquired, other processes or threads are
    prevented from acquiring the same lock until it is released.
    """
    with _paths_lock:
        lock = _paths_to_locks.get(path)
        if lock is None:
            _paths_to_locks[path] = lock = _FileLock(path)
    return lock


class _FileLock(object):
    """Internal file based lock object"""
    def __init__(self, path):
        self._path = path
        self._file = None
        self._threadlock = threading.Lock()

    def _acquire_file(self):
        if self._file is None:
            self._file = open(self._path, "wb")
        fcntl.flock(self._file, fcntl.LOCK_EX)

    def _release_file(self):
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()
        self._file = None

    def acquire(self):
        self._threadlock.acquire()
        try:
            self._acquire_file()
        except Exception:  # pragma: no cover
            self._threadlock.release()
            raise

    def release(self):
        self._release_file()
        self._threadlock.release()

    def __enter__(self):
        self.acquire()

    def __exit__(self, *args):
        self.release()


def pid_exists(pid):
    try:
        os.kill(pid, 0)
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
    return True


@contextmanager
def grpc_fork_support_disabled():
    """Temporarily disable fork support in gRPC.

    Fork + exec has always been supported, but the recent fork handling code in
    gRPC (>= 1.15) results in extraneous error logs currently. For now we
    explicitly disable fork support for gRPC clients we create.
    """
    key = 'GRPC_ENABLE_FORK_SUPPORT'
    try:
        os.environ[key] = '0'
        yield
    finally:
        del os.environ[key]


def xor(a, b):
    return bool(a) != bool(b)


def ensure_unicode(x):
    if type(x) is not unicode:
        x = x.decode('utf-8')
    return x


def format_list(x):
    return "\n".join("- %s" % s for s in sorted(x))


def format_comma_separated_list(x, conjunction='or'):
    n = len(x)
    if n == 0:
        return ''
    if n == 1:
        return str(x[0])
    if n == 2:
        left, right = x
        return '%s %s %s' % (left, conjunction, right)
    left, right = ', '.join(map(str, x[:-1])), x[-1]
    return '%s, %s %s' % (left, conjunction, right)


def humanize_timedelta(td):
    """Pretty-print a timedelta in a human readable format."""
    secs = int(td.total_seconds())
    hours, secs = divmod(secs, 60 * 60)
    mins, secs = divmod(secs, 60)
    if hours:
        return '%dh %dm' % (hours, mins)
    if mins:
        return '%dm' % mins
    return '%ds' % secs


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def datetime_from_millis(x):
    if x is None or x == 0:
        return None
    return _EPOCH + timedelta(milliseconds=x)


def datetime_to_millis(x):
    return int((x - _EPOCH).total_seconds() * 1000)


def runtime(start_time, finish_time):
    if start_time is None:
        return timedelta(0)
    if finish_time is None:
        return datetime.now(UTC) - start_time
    return finish_time - start_time


def format_table(columns, rows):
    """Formats an ascii table for given columns and rows.

    Parameters
    ----------
    columns : list
        The column names
    rows : list of tuples
        The rows in the table. Each tuple must be the same length as
        ``columns``.
    """
    rows = [tuple(str(i) for i in r) for r in rows]
    columns = tuple(str(i).upper() for i in columns)
    if rows:
        widths = tuple(max(max(map(len, x)), len(c))
                       for x, c in zip(zip(*rows), columns))
    else:
        widths = tuple(map(len, columns))
    row_template = ('    '.join('%%-%ds' for _ in columns)) % widths
    header = (row_template % tuple(columns)).strip()
    if rows:
        data = '\n'.join((row_template % r).strip() for r in rows)
        return '\n'.join([header, data])
    else:
        return header


class cached_property(object):

    def __init__(self, func):
        self.__doc__ = getattr(func, "__doc__")
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self

        res = obj.__dict__[self.func.__name__] = self.func(obj)
        return res


def implements(f):
    def decorator(g):
        g.__doc__ = f.__doc__
        return g
    return decorator
