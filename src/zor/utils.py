from collections.abc import Iterable
from os import environ
from pathlib import Path
import subprocess


def sub_run(
    *args,
    capture=False,
    returns: None | Iterable[int] = None,
    **kwargs,
) -> subprocess.CompletedProcess:
    kwargs.setdefault('check', not bool(returns))
    capture = kwargs.setdefault('capture_output', capture)
    args = args + kwargs.pop('args', ())
    env = kwargs.pop('env', None)
    if env:
        kwargs['env'] = environ | env
    if capture:
        kwargs.setdefault('text', True)

    try:
        result = subprocess.run(args, **kwargs)
        if returns and result.returncode not in returns:
            raise subprocess.CalledProcessError(result.returncode, args[0])
        return result
    except subprocess.CalledProcessError as e:
        if capture:
            print(e.stderr)
        raise


def rm_dir(dpath):
    sub_run('rm', '-r', dpath)


def chroot(root_path: str, *args, **kwargs):
    return sub_run('chroot', root_path, *args, **kwargs)
