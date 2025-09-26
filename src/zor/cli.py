import configparser
from dataclasses import dataclass
import os
from pathlib import Path
import time

import click
import sh

from . import disks, op_sys, utils, zfs


PKG_DPATH = Path(__file__).parent.parent.parent.resolve()

# ------------------
# Configuration
# ------------------

config = None
config_tpl = """
[zor]
# Device path to the disk that will be used for the EFI, boot, and ZFS partitions
# Assume ALL DATA WILL BE DESTROYED on this device, even though that may not always be true
# Example: /dev/disk/by-id/nvme-Samsung_SSD_960_PRO_1TB_...
DISK_DEV =

# Short name for DISK_DEV above.  This will be used for partition name prefixes
# as well as the root ZFS pool name
# Example: "sampro" for a samsung pro drive
DISK_LABEL =

# The name of the dataset that will be the root for this OS installation.  Often
# named after the OS version being installed
# Examples: "bionic" or "eoan"
OS_DATASET =

# The release codename of the OS to be installed, used by debootstrap.  debootstrap manpage
# refers to this as the "SUITE".
# Examples: "bionic" or "eoan"
RELEASE_CODENAME =

# The hostname of this installation
# Example: some-host-name
HOSTNAME =

# Filesystem path to directory where cache files can be kept.  To speed up this script
# across reboots of the live environment, make this a path to parmanent storage (e.g. mounted
# USB drive)
# Examples "/tmp" or "/mnt/usb/zor-cache"
CACHE_DPATH = /mnt/usb-data/zor-cache

# Installed system user credentials
ADMIN_USERNAME =
# openssl passwd -1 'put password here'
ADMIN_PASSHASH =
"""


@dataclass
class Config:
    disk_dev: str
    disk_label: str
    os_dataset: str
    release_codename: str
    hostname: str
    cache_dpath: Path | None = None
    admin_username: str = ''
    admin_passhash: str = ''
    pool_name: str = ''
    efi_partname: str = ''
    efi_dev: str = ''
    boot_partname: str = ''
    boot_dev: str = ''
    swap_partname: str = ''
    swap_dev: str = ''
    zfs_partname: str = ''
    zfs_dev: str = ''

    def __post_init__(self):
        self.cache_dpath = Path(self.cache_dpath)

        self.efi_partname = f'{self.disk_label}-efi'
        self.efi_dev = f'/dev/disk/by-partlabel/{self.efi_partname}'

        self.boot_partname = f'{self.disk_label}-boot'
        self.boot_dev = f'/dev/disk/by-partlabel/{self.boot_partname}'

        self.zfs_partname = f'{self.disk_label}-zfs'
        self.zfs_dev = f'/dev/disk/by-partlabel/{self.zfs_partname}'

        self.pool_name = self.disk_label
        self.os_ds = f'{self.pool_name}/{self.os_dataset}'
        self.os_root_ds = f'{self.os_ds}/root'


def config_prep(click_ctx: click.Context):
    config_fpath = PKG_DPATH / 'zor-config.ini'
    config = configparser.ConfigParser()
    if not config_fpath.exists():
        config_fpath.write_text(config_tpl)
        click_ctx.fail(f"Config file didn't exist, created template at: {config_fpath}")
    else:
        print('Config file:', config_fpath)

    config.read(config_fpath)
    if not config['zor']['DISK_DEV']:
        click_ctx.fail('Config disk is blank')

    return Config(
        disk_dev=config['zor']['DISK_DEV'],
        disk_label=config['zor']['DISK_LABEL'],
        os_dataset=config['zor']['OS_DATASET'],
        release_codename=config['zor']['RELEASE_CODENAME'],
        hostname=config['zor']['HOSTNAME'],
        cache_dpath=config['zor']['CACHE_DPATH'],
        admin_username=config['zor']['ADMIN_USERNAME'],
        admin_passhash=config['zor']['ADMIN_PASSHASH'],
    )


# ------------------
# Filesystem Paths
# ------------------
@dataclass
class Paths:
    mnt: Path = Path('/mnt')

    efi_mnt: Path = mnt / 'efi'

    zroot: Path = mnt / 'zroot'
    boot: Path = zroot / 'boot'
    dev: Path = zroot / 'dev'
    proc: Path = zroot / 'proc'
    sys: Path = zroot / 'sys'

    apt_cache_host: Path = Path('/var/cache/apt/archives')
    apt_cache: Path = zroot / 'var/cache/apt/archives'


paths = Paths()

# ------------------
# CLI Commands Below
# ------------------


@click.group()
@click.pass_context
def main(ctx):
    global config
    config = config_prep(ctx)

    if os.getuid() != 0:
        ctx.fail('You must be root')


@main.command('config')
def _config():
    print(config)


@main.command()
def kernel_versions():
    print(utils.kernels_in_boot(Path(f'{paths.zroot}/boot')))


@main.command()
def status():
    print('Config values --------------------\n')
    for k, v in config.__dict__.items():
        print(k, v)

    print('Paths-- --------------------------\n')
    for k, v in paths.__dict__.items():
        print(k, v)

    print(f'\n$ sgdisk --print {config.disk_dev} --------------------\n')
    disks.sgdisk_print(config.disk_dev)

    print('\n$ blkid --------------------------\n')
    utils.sub_run('blkid')

    print('\n$ zpool list ---------------------------\n')
    zfs.zpool('list')

    print('\n$ zfs list ---------------------------\n')
    zfs.zfs('list')

    print('\n$ zfs mount ---------------------------\n')
    zfs.zfs('mount')


@main.command()
@click.option('--chroot', is_flag=True, default=False)
@click.pass_context
def recover(ctx: click.Context, chroot: bool):
    """Import pool and mount filesystem in prep for recovery efforts"""
    zfs.mount()
    disks.efi_mount(paths.efi_mnt, config.efi_dev)
    disks.mounts()

    if chroot:
        ctx.forward(chroot_cmd)


@main.command()
def chroot_cmd():
    """Import pool and mount filesystem in prep for recovery efforts"""
    utils.chroot(paths.zroot, '/bin/bash', '--login')


@main.command()
def unmount():
    """Cleanup all the mounts we created"""
    disks.unmounts(paths)
    zfs.umount(paths.zroot)
    zfs.zpool_export(config.pool_name)


@main.command('disk-partition')
def disk_partition():
    """Partition a presumably blank disk"""
    disks.disk_partition(
        config.disk_dev,
        efi_label=config.efi_partname,
        boot_label=config.boot_partname,
        zfs_label=config.zfs_partname,
    )


@main.command('disk-format')
def disk_format():
    # format EFI
    disks.efi_format(config.efi_partname)

    # format boot
    mkfsext4 = sh.Command('mkfs.ext4')
    mkfsext4('-qF', '-L', config.boot_partname, config.boot_dev)


@main.command('disk-wipe')
def disk_wipe():
    """Wipe all filesystem and parition data from the disk."""
    disks.disk_wipe(config.disk_dev)


@main.command()
@click.option('--mount-only', is_flag=True, default=False)
def efi(mount_only: bool):
    """Write programs to EFI partition"""

    if mount_only:
        disks.efi_mount(config.efi_partname, paths.efi_mnt)
        return

    disks.efi_refind(config.efi_partname, paths.efi_mnt)


@main.command()
@click.option('--wipe-first', is_flag=True, default=False)
def zpool(wipe_first):
    """Create ZFS pool and datasets"""
    if wipe_first:
        zfs.umount(paths.zroot)
        zfs.zpool('destroy', config.pool_name, returns=(0, 1))

    print('Creating zpool:', config.pool_name)

    # Use for instead of `while True` because we don't test the kind of error zpool is throwing.
    # If it's a problem with the parameters passed in, then it will loop forever.
    # TODO: could make it time based...if the create command fails in < 1s, then it's not a user
    # entered issue.
    for _ in range(10):
        result = zfs.create_pool(paths.zroot, config.pool_name, config.zfs_dev, check=False)
        if result.returncode == 0:
            print('ZFS pool created:', config.pool_name)
            return


@main.command('zfs')
@click.option('--wipe-first', is_flag=True, default=False)
def zfs_cmd(wipe_first):
    """Create ZFS pool and dataset"""
    zfs.datasets(config, paths, wipe_first)
    print('ZFS datasets created')


@main.command('install-os')
@click.option('--wipe-first', is_flag=True, default=False)
def install_os(wipe_first):
    """Install the OS into the presumably mounted datasets"""
    if wipe_first:
        zfs.datasets(config, paths, wipe_first)
        print('Sleeping 5 seconds to give zfs datasets time to mount...')
        time.sleep(5)

    config.cache_dpath.mkdir(exist_ok=True)
    db_tarball_fpath = config.cache_dpath / 'debootstrap.tar'
    # It would be ideal to just use these files but not sure if that's possible and the .tar
    # method is working.
    db_staging_fpath = config.cache_dpath / 'debootstrap-staging'

    if not db_tarball_fpath.exists():
        sh.debootstrap(
            '--make-tarball',
            db_tarball_fpath,
            config.release_codename,
            db_staging_fpath,
            _fg=True,
        )

    if not paths.zroot.joinpath('bin').exists():
        zfs.zfs('set', 'devices=on', config.os_root_ds)
        sh.debootstrap(
            '--unpack-tarball',
            db_tarball_fpath,
            config.release_codename,
            paths.zroot,
            _fg=True,
        )
        zfs.zfs('set', 'devices=off', config.os_root_ds)

    disks.unmounts(paths)
    disks.mounts(config, paths)

    boot_dpath = paths.zroot / 'boot'
    # refind_linux.conf provides kernel boot options.  Don't confuse it with refind.conf.
    refind_conf_content = op_sys.boot_refind_conf_tpl.format(zfs_os_root_ds=config.os_root_ds)
    boot_dpath.joinpath('refind_linux.conf').write_text(refind_conf_content)

    etc_fpath = paths.zroot / 'etc'

    sources_list_content = op_sys.apt_sources_list.format(codename=config.release_codename)
    etc_fpath.joinpath('apt', 'sources.list').write_text(sources_list_content)

    fstab_content = op_sys.etc_fstab_tpl.format(config=config)
    etc_fpath.joinpath('fstab').write_text(fstab_content)

    etc_fpath.joinpath('hostname').write_text(config.hostname)

    etc_hosts_content = op_sys.etc_hosts_tpl.format(hostname=config.hostname)
    etc_fpath.joinpath('hosts').write_text(etc_hosts_content)

    # Customize OS in chroot
    # ----------------------
    utils.chroot(paths.zroot, 'apt', 'update')

    utils.chroot(paths.zroot, 'locale-gen', '--purge', 'en_US.UTF-8')
    utils.chroot(paths.zroot, 'update-locale', "LANG='en_US.UTF-8'", "LANGUAGE='en_US:en'")

    utils.chroot(paths.zroot, 'ln', '-fs', '/usr/share/zoneinfo/US/Eastern', '/etc/localtime')
    utils.chroot(paths.zroot, 'dpkg-reconfigure', '-f', 'noninteractive', 'tzdata')

    # Have to install the kernel and zfs-initramfs so that ZFS is installed and creating the user's
    # dataset below works.
    utils.chroot(
        paths.zroot,
        'apt',
        'install',
        '--yes',
        '--no-install-recommends',
        'linux-image-generic',
    )
    utils.chroot(paths.zroot, 'apt', 'install', '--yes', 'zfs-initramfs')

    # `update-initramfs -uk all` doesn't work, see:
    # https://bugs.launchpad.net/ubuntu/+source/initramfs-tools/+bug/1829805
    for kernel_version in op_sys.kernels_in_boot(paths.boot):
        utils.chroot(paths.zroot, 'update-initramfs', '-uk', kernel_version)


@main.command('install-user')
@click.option('--wipe-first', is_flag=True, default=False)
def install_user(wipe_first):
    username = config.admin_username
    passhash = config.admin_passhash

    # Don't use a ZFS dataset for now.  The home directory won't be created as expected and
    # /home is already a dedicated dataset.
    # user_dataset = f'{config.pool_name}/home/{username}'

    if wipe_first:
        utils.chroot(paths.zroot, 'userdel', username, '--remove', returns=(0, 6))

    utils.chroot(
        paths.zroot,
        'useradd',
        '--create-home',
        '--shell',
        '/bin/bash',
        '-p',
        passhash,
        username,
    )

    utils.chroot(paths.zroot, 'addgroup', '--system', 'docker')
    utils.chroot(paths.zroot, 'addgroup', '--system', 'lpadmin')
    utils.chroot(paths.zroot, 'addgroup', '--system', 'netdev')
    utils.chroot(paths.zroot, 'addgroup', '--system', 'sambashare')
    utils.chroot(
        paths.zroot,
        'usermod',
        '-a',
        '-G',
        'adm,cdrom,dip,docker,lpadmin,netdev,plugdev,sambashare,sudo',
        username,
    )


@main.command('install-desktop')
@click.argument('desktop', type=click.Choice(['cinnamon', 'xubuntu']))
def install_desktop(desktop):
    desk_env = 'cinnamon-desktop-environment' if desktop == 'cinnamon' else 'xubuntu-desktop'

    # Full OS & desktop install
    utils.chroot(paths.zroot, 'apt', 'dist-upgrade', '--yes')

    # Ideally 'cinnamon-core' would work, but alas, didn't.
    utils.chroot(paths.zroot, 'apt', 'install', '--yes', desk_env)


@main.command()
@click.argument('desktop', type=click.Choice(['cinnamon', 'xubuntu']))
@click.option('--inspect', is_flag=True)
@click.pass_context
def install(ctx: click.Context, desktop: str, inspect: bool):
    ctx.invoke(unmount)

    if not disks.disk_wipe(config.disk_dev):
        print('exiting')
        return

    ctx.invoke(disk_partition)
    ctx.invoke(disk_format)
    ctx.invoke(efi)
    # TODO: zpool command will fail if password is mistyped.  Should use a loop here to catch
    # that exception and try again.  More user friendly.
    ctx.invoke(zpool)
    ctx.invoke(zfs_cmd)
    ctx.invoke(install_os)
    ctx.invoke(install_user)
    ctx.invoke(install_desktop, desktop=desktop)
    ctx.invoke(status)
    print('System install complete')
    if not inspect:
        ctx.invoke(unmount)
    else:
        print('Inspection requested.  Run `zor unmount` before rebooting.')


@main.command()
@click.argument('img_src')
@click.argument('dest_dev')
@click.option('--part-prefix', default='resc')
@click.option('--zeros/--no-zeros', default=True)
def create_rescue(img_src: str, dest_dev: str, part_prefix: str, zeros: bool):
    src_part = disks.Partition.from_path(img_src)
    efi_part_label = f'{part_prefix}-efi'
    efi_mnt_dir = Path('/mnt/rescue-efi')
    dest_part_label = f'{part_prefix}-{src_part.label}'

    disks.Mounts().unmount(efi_mnt_dir)

    # User info & confirmation
    print('\nRescue image source partition:', src_part.path, '\nFrom device:\n')
    src_part.lsblk_parent()
    if not disks.disk_wipe(dest_dev, write_zeros=zeros):
        print('exiting')
        return

    # GPT format and EFI partition
    disks.disk_partition(dest_dev, efi_label=efi_part_label)

    # New partition to copy the src image to
    kb_size = int(src_part.size) // 1024
    disks.sgdisk_new(f'+{kb_size}K', dest_part_label, dest_dev, disks.PartType.linux)

    print('\nDisk prep done; resulting partitions:\n')
    disks.sgdisk_print(dest_dev, indent='    ')

    # Ensure unique uuids and new /dev links are present for the partitions
    disks.sgdisk('--randomize-guids', dest_dev)
    utils.sub_run('partprobe', dest_dev)

    dest_part = disks.Partition.from_path(dest_part_label)
    assert Path(dest_part).exists()

    # EFI format and install
    disks.efi_format(efi_part_label)
    disks.efi_refind(efi_part_label, efi_mnt_dir)

    # Image copy
    print(f'\nCopying {src_part.path} to {dest_part.path}:\n')
    utils.sub_run(
        'dd',
        'bs=4M',
        f'if={src_part.path}',
        f'of={dest_part.path}',
        'conv=fdatasync',
        'status=progress',
        'oflag=direct',
    )
