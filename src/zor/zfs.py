import subprocess

from . import cli, utils


def zfs(*args, **kwargs) -> subprocess.CompletedProcess:
    return utils.sub_run('zfs', *args, **kwargs)


def zpool(*args, **kwargs) -> subprocess.CompletedProcess:
    return utils.sub_run('zpool', *args, **kwargs)


def datasets(config: 'cli.Config', paths: 'cli.Paths', wipe_first):
    os_ds = config.os_ds
    os_root_ds = config.os_root_ds

    if wipe_first:
        umount(paths.zroot)
        print('Destroying existing ZFS datasets')
        zfs('destroy', '-R', os_ds, returns=(0, 1))
        zfs('destroy', '-R', f'{config.pool_name}/docker', returns=(0, 1))
        zfs('destroy', '-R', f'{config.pool_name}/home', returns=(0, 1))
        zfs('destroy', '-R', f'{config.pool_name}/root', returns=(0, 1))
        zfs('destroy', '-R', f'{config.pool_name}/postgresql', returns=(0, 1))
        zfs('destroy', '-R', f'{config.pool_name}/shared', returns=(0, 1))
        if paths.zroot.exists():
            utils.rm_dir(paths.zroot)

    # --------------------
    # OS specific datasets
    # --------------------

    # Just a container that gives children mountpoints through inheritance
    zfs('create', '-o', 'canmount=off', '-o', 'mountpoint=/', os_ds)

    # The root dataset, e.g. the mount that is actually "/"
    zfs('create', '-o', 'canmount=noauto', '-o', 'mountpoint=/', os_root_ds)
    # Have mount this now, or the mounts that happen later prevent this mount from happening
    # b/c the directory is not empty
    zfs('mount', os_root_ds)

    # Another container, has to be present to create the other var datasets below, but we will never
    # mount this
    zfs('create', '-o', 'canmount=off', f'{os_ds}/var')

    # Separate dataset for logs so that if we rollback a snapshot, we don't lose logs for
    # troubleshooting.
    zfs('create', f'{os_ds}/var/log')
    zfs('create', f'{os_ds}/var/journal')

    # Datasets that should not be in a snapshot
    zfs('create', '-o', 'com.sun:auto-snapshot=false', f'{os_ds}/var/cache')
    zfs('create', '-o', 'com.sun:auto-snapshot=false', f'{os_ds}/var/tmp')

    # Custom settings for /tmp
    zfs(
        'create',
        '-o',
        'com.sun:auto-snapshot=false',
        '-o',
        'setuid=off',
        '-o',
        'devices=off',
        '-o',
        'sync=disabled',
        f'{os_ds}/tmp',
    )

    # Security for tmp directories
    utils.sub_run('chmod', '1777', f'{paths.zroot}/var/tmp')
    utils.sub_run('chmod', '1777', f'{paths.zroot}/tmp')

    # --------------------
    # Shared datasets
    # --------------------
    # these could possibly be shared across different OSs running on the same system.  Create these
    # second or they will prevent os_root_ds from mounting b/c directories will already exist.

    zfs(
        'create',
        '-o',
        'mountpoint=/home',
        '-o',
        'com.sun:auto-snapshot=true',
        f'{config.pool_name}/home',
    )
    zfs('create', '-o', 'mountpoint=/root', f'{config.pool_name}/root')
    zfs(
        'create',
        '-o',
        'com.sun:auto-snapshot=true',
        '-o',
        'mountpoint=/shared',
        f'{config.pool_name}/shared',
    )
    zfs(
        'create',
        '-o',
        'com.sun:auto-snapshot=false',
        '-o',
        'mountpoint=/var/lib/docker',
        f'{config.pool_name}/docker',
    )

    # Security for root
    utils.sub_run('chmod', '700', f'{paths.zroot}/root')

    # Special settings see Arch wiki for details: https://wiki.archlinux.org/index.php/ZFS
    zfs(
        'create',
        '-o',
        'recordsize=8K',
        '-o',
        'primarycache=metadata',
        '-o',
        'mountpoint=/var/lib/postgresql',
        '-o',
        'logbias=throughput',
        f'{config.pool_name}/postgresql',
    )


def mount(config: 'cli.Config', paths: 'cli.Path'):
    zpool('export', '-a')
    zpool('import', '-Nf', '-R', paths.zroot, config.pool_name)
    zfs('load-key', '-a')
    zfs('mount', config.os_root_ds)
    zfs('mount', '-a')


def zpool_export(pool_name: str):
    try:
        zpool('export', pool_name)
        print('Exported pool:', pool_name)
    except Exception:
        pass


def umount(zroot):
    zfs('umount', '-a')

    # zfs sometimes doesn't give up our root mount with the -a option above
    zfs_mounts = zfs('mount', capture=True)
    if str(zroot) in zfs_mounts.stdout:
        zfs('umount', zroot)
        utils.sub_run('rmdir', zroot)

    print('ZFS datasets unmounted')


def create_pool(
    mount_at,
    pool_name,
    device,
    encrypt: bool,
    **kwargs,
) -> subprocess.CompletedProcess:
    encrypt_args = (
        ('-O', 'encryption=aes-256-gcm', '-O', 'keylocation=prompt', '-O', 'keyformat=passphrase')
        if encrypt
        else ()
    )

    return zpool(
        'create',
        '-o',
        'ashift=12',
        '-o',
        'autotrim=on',
        '-O',
        'acltype=posixacl',
        '-O',
        'canmount=off',
        '-O',
        'compression=lz4',
        '-O',
        'dnodesize=auto',
        '-O',
        'normalization=formD',
        '-O',
        'relatime=on',
        '-O',
        'xattr=sa',
        *encrypt_args,
        '-O',
        'mountpoint=none',
        '-R',
        mount_at,
        '-f',
        pool_name,
        device,
        **kwargs,
    )
