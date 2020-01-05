import configparser
import getpass
import json
import os
import pathlib
from types import SimpleNamespace
import sys

import click
import psutil
import sh

# ------------------
# Configuration
# ------------------

CWD = pathlib.Path(__file__).parent.resolve()
config = None
config_tpl = f"""
[zor]
# Device path to the disk that will be used for the EFI, boot, and ZFS partitions
# Assume ALL DATA WILL BE DESTROYED on this device, even though that may not always be true
# Example: /dev/disk/by-id/nvme-Samsung_SSD_960_PRO_1TB_...
DISK_DEV =

# The name of the ZFS root pool
Examples: "rpool" or "sampro" if you want it named after the disk
POOL_NAME =

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
# Examples "/tmp" or "{CWD}/cache"
CACHE_DPATH =
"""


def config_prep(click_ctx):
    config_keys = ('DISK_DEV', 'POOL_NAME', 'OS_DATASET', 'RELEASE_CODENAME', 'HOSTNAME', 'CACHE_DPATH')

    config_fpath = CWD / 'zor-config.ini'
    config = configparser.ConfigParser()

    if not config_fpath.exists():
        config_fpath.write_text(config_tpl)

    config.read(config_fpath)

    rv = SimpleNamespace()
    for key in config_keys:
        value = config['zor'].get(key)
        if not value:
            click_ctx.fail(f'Edit the file {config_fpath} so that all variables are defined.  {key} is blank or missing')
        setattr(rv, key.lower(), value)

    rv.cache_dpath = pathlib.Path(rv.cache_dpath)
    rv.efi_dev = f'/dev/disk/by-partlabel/EFI'
    rv.boot_dev = f'/dev/disk/by-partlabel/boot'
    rv.swap_dev = f'/dev/disk/by-partlabel/swap'
    rv.zfs_dev = f'/dev/disk/by-partlabel/zfs'

    rv.os_ds = f'{rv.pool_name}/{rv.os_dataset}'
    rv.os_root_ds = f'{rv.os_ds}/root'

    return rv

# ------------------
# File templates
# ------------------
etc_hosts_tpl = """
127.0.0.1 localhost
127.0.1.1 {hostname}

# The following lines are desirable for IPv6 capable hosts
::1     ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
ff02::3 ip6-allhosts
""".lstrip()

etc_fstab_tpl = """
# <device>               <dir>      <type>  <options>                   <dump> <fsck>
PARTLABEL=boot           /boot      ext4    defaults,nodev,relatime     0      1
PARTLABEL=EFI            /boot/efi  vfat    defaults,nodev,relatime     0      2
""".lstrip()

boot_refind_conf_tpl = """
"Boot" "rw root=ZFS={zfs_os_root_ds}"
"ZFS Debug" "rw root=ZFS={zfs_os_root_ds} zfsdebug=on"
"SD Debug" "rw root=ZFS={zfs_os_root_ds} systemd.log_level=debug systemd.log_target=kmsg log_buf_len=1M printk.devkmsg=on enforcing=0"
""".lstrip()

apt_sources_list = """
deb http://archive.ubuntu.com/ubuntu {codename} main restricted universe multiverse
deb-src http://archive.ubuntu.com/ubuntu {codename} main restricted universe multiverse

deb http://security.ubuntu.com/ubuntu {codename}-security main restricted universe multiverse
deb-src http://security.ubuntu.com/ubuntu {codename}-security main restricted universe multiverse

deb http://archive.ubuntu.com/ubuntu {codename}-updates main restricted universe multiverse
deb-src http://archive.ubuntu.com/ubuntu {codename}-updates main restricted universe multiverse
""".lstrip()

# ------------------
# Filesystem Paths
# ------------------

paths = SimpleNamespace()

paths.mnt = pathlib.Path('/mnt')

paths.efi_mnt = paths.mnt / 'efi'
paths.efi = paths.efi_mnt / 'EFI'
paths.efi_boot = paths.efi / 'BOOT'
paths.efi_memtest = paths.efi / 'memtest86'

paths.zroot = paths.mnt / 'sampro'
paths.boot = paths.zroot / 'boot'
paths.dev = paths.zroot / 'dev'
paths.proc = paths.zroot / 'proc'
paths.sys = paths.zroot / 'sys'

paths.memtest_mnt = paths.mnt / 'memtest86'
paths.memtest_boot = paths.memtest_mnt / 'EFI' / 'BOOT'


# ------------------
# Utilities
# ------------------


class Partitions:

    def __init__(self):
        self.partitions = psutil.disk_partitions(all=True)
        self.mounts = [p.mountpoint for p in self.partitions if p.mountpoint]

    def is_mounted(self, fspath):
        return str(fspath) in self.mounts

    def unmount(self, fspath):
        if self.is_mounted(fspath):
            print(f'Unmounting: {fspath}')
            sh.umount('-Rn', fspath)

    def recursive_unmount(self, fspath):
        for mp in mps:
            sh.umount(mp)


def memtest_extract():
    zip_fpath = config.cache_dpath / 'memtest86-usb.zip'
    unzip_fpath = config.cache_dpath / 'memtest86-usb'
    img_fpath = unzip_fpath / 'memtest86-usb.img'
    zip_url = 'https://www.memtest86.com/downloads/memtest86-usb.zip'

    if not zip_fpath.exists():
        print('Downloading:', zip_url, 'to', zip_fpath)
        sh.wget('-O', zip_fpath, zip_url)

    if not img_fpath.exists():
        print('Extracting zip to', unzip_fpath)
        sh.unzip('-d', unzip_fpath, zip_fpath)

    output = sh.sgdisk('-p', img_fpath)
    lines = output.strip().splitlines()
    # Second line should look like:
    #   Sector size (logical): 512 bytes
    sector_size = lines[1].split(':')[1].replace('bytes', '').strip()
    sector_size = sector_size

    json_output = sh.sfdisk('--json', img_fpath)
    partitions = json.loads(str(json_output))['partitiontable']['partitions']
    efi_part = [p for p in partitions if p['name'] == 'EFI System Partition'].pop()
    efi_start_sector = efi_part['start']

    efi_start_bytes = int(sector_size) * (efi_start_sector)

    return img_fpath, efi_start_bytes


def zfs_create(wipe_first):
    os_ds = config.os_ds
    os_root_ds = config.os_root_ds

    if wipe_first:
        unmount_everything()

        sh.zfs.destroy('-R', os_ds, _ok_code=[0,1])
        sh.zfs.destroy('-R', f'{config.pool_name}/docker', _ok_code=[0,1])
        sh.zfs.destroy('-R', f'{config.pool_name}/home', _ok_code=[0,1])
        sh.zfs.destroy('-R', f'{config.pool_name}/postgresql', _ok_code=[0,1])
        sh.zfs.destroy('-R', f'{config.pool_name}/shared', _ok_code=[0,1])
        sh.rm('-rf', paths.zroot)

    # --------------------
    # OS specific datasets
    # --------------------

    # Just a container that gives children mountpoints through inheritanc
    sh.zfs.create('-o', 'canmount=off', '-o', 'mountpoint=/', os_ds)

    # The root dataset, e.g. the mount that is actually "/"
    sh.zfs.create('-o', 'canmount=noauto', '-o', 'mountpoint=/', os_root_ds)
    # Have mount this now, or the mounts that happen later prevent this mount from happening
    # b/c the directory is not empty
    sh.zfs.mount(os_root_ds)

    # Another container, has to be present to create the other var datasets below, but we will never mount this
    sh.zfs.create('-o', 'canmount=off', f'{os_ds}/var')

    # Separate dataset for logs so that if we rollback a snapshot, we don't lose logs for troubleshooting.
    sh.zfs.create(f'{os_ds}/var/log')

    # Datasets that should not be in a snapshot
    sh.zfs.create('-o', 'com.sun:auto-snapshot=false', f'{os_ds}/var/cache')
    sh.zfs.create('-o', 'com.sun:auto-snapshot=false', f'{os_ds}/var/tmp')

    # Custom settings for /tmp
    sh.zfs.create('-o', 'com.sun:auto-snapshot=false', '-o', 'setuid=off', '-o', 'devices=off', '-o', 'sync=disabled', f'{os_ds}/tmp')

    # Security for tmp directories
    sh.chmod('1777', f'{paths.zroot}/var/tmp')
    sh.chmod('1777', f'{paths.zroot}/tmp')

    # --------------------
    # Shared datasets
    # --------------------
    # these could possibly be shared across different OSs running on the same system.  Create these second
    # or they will prevent os_root_ds from mounting b/c directories will already exist.

    sh.zfs.create('-o', 'mountpoint=/home', f'{config.pool_name}/home')
    sh.zfs.create('-o', 'mountpoint=/root', f'{config.pool_name}/home/root')
    sh.zfs.create('-o', 'mountpoint=/shared', f'{config.pool_name}/shared')
    sh.zfs.create('-o', 'mountpoint=/var/lib/docker', f'{config.pool_name}/docker')

    # Special settings see Arch wiki for details: https://wiki.archlinux.org/index.php/ZFS
    sh.zfs.create(
        '-o', 'recordsize=8K',
        '-o', 'primarycache=metadata',
        '-o', 'mountpoint=/var/lib/postgresql',
        '-o', 'logbias=throughput',
        f'{config.pool_name}/postgresql'
    )


def other_mounts():
    sh.mount('/dev/disk/by-partlabel/boot', f'{paths.zroot}/boot')
    sh.mount('--rbind', '/dev', f'{paths.zroot}/dev', '--make-rslave')
    sh.mount('--rbind', '/proc', f'{paths.zroot}/proc', '--make-rslave')
    sh.mount('--rbind', '/sys', f'{paths.zroot}/sys', '--make-rslave')


def unmount_everything():
    partitions = Partitions()
    partitions.unmount(paths.dev)
    partitions.unmount(paths.proc)
    partitions.unmount(paths.sys)
    partitions.unmount(paths.boot)
    partitions.unmount(paths.efi_mnt)
    partitions.unmount(paths.memtest_mnt)
    sh.zfs.umount('-a')

    # zfs doesn't seem to want to give up this mount with the -a option above
    zfs_mounts = sh.zfs.mount()
    if str(paths.zroot) in zfs_mounts:
        sh.zfs.umount(paths.zroot)
        sh.rmdir(paths.zroot)

def kernels_in_boot():
    boot_dpath = pathlib.Path(f'{paths.zroot}/boot')
    kernel_fpaths = boot_dpath.glob('vmlinuz-*')
    # Path names look like: vmlinuz-5.3.0-24-generic
    # Strip off "vmlinuz-" leaving just the version that can be fed to update-initramfs
    kernel_versions = [fpath.name[8:] for fpath in kernel_fpaths]
    return kernel_versions

# ------------------
# CLI Commands Below
# ------------------


@click.group()
@click.pass_context
def zor(ctx):
    global config
    config = config_prep(ctx)

    if os.getuid() != 0:
        ctx.fail('You must be root')


@zor.command('config')
def _config():
    print(config)


@zor.command()
def kernel_versions():
    print(kernels_in_boot())


@zor.command()
def status():
    print(f'$ config values --------------------\n')
    print(config)

    print(f'\n$ sgdisk --print {config.disk_dev} --------------------\n')
    sh.sgdisk('--print', config.disk_dev, _out=sys.stdout, _ok_code=[0,2])

    print(f'\n$ blkid --------------------------\n')
    sh.blkid(_out=sys.stdout,)

    print('\n$ zpool list ---------------------------\n')
    sh.zpool('list', _out=sys.stdout)

    print('\n$ zfs list ---------------------------\n')
    sh.zfs('list', _out=sys.stdout)

    print('\n$ zfs mount ---------------------------\n')
    sh.zfs('mount', _out=sys.stdout)


@zor.command()
@click.option('--chroot', is_flag=True, default=False)
def recover(chroot):
    """ Import pool and mount filesystem in prep for recovery efforts """
    sh.zpool.export('-a', _fg=True)
    sh.zpool('import', '-Nf', '-R', paths.zroot, config.pool_name, _fg=True)
    sh.zfs('load-key', '-a', _fg=True)
    sh.zfs.mount(config.os_root_ds, _fg=True)
    sh.zfs.mount('-a', _fg=True)

    other_mounts()

    if chroot:
        sh.chroot(paths.zroot, '/bin/bash', '--login', _fg=True)


@zor.command()
def chroot():
    """ Import pool and mount filesystem in prep for recovery efforts """
    sh.chroot(paths.zroot, '/bin/bash', '--login', _fg=True)


@zor.command()
def unmount():
    """ Cleanup all the mounts we created"""
    unmount_everything()


@zor.command('disk-partition')
def disk_partition():
    """ Partition a presumably blank disk """
    # format disk as GPT
    sh.sgdisk('-Z', config.disk_dev, _ok_code=[0,2])

    # UEFI partition
    sh.sgdisk('-n', '1:1M:+512M', '-c', '1:EFI', '-t', '1:EF00', config.disk_dev)

    # boot partition
    sh.sgdisk('-n', '2:0:+2G', '-c', '2:boot', '-t', '2:8300', config.disk_dev)

    # swap partition
    sh.sgdisk('-n', '0:0:+16G', '-c', '0:swap', '-t', '0:8200', config.disk_dev)

    # zfs root pool partition
    sh.sgdisk('-n', '0:0:0', '-c', '0:zfs', '-t', '0:BF01', config.disk_dev)


@zor.command('disk-format')
def disk_format():
    # format EFI
    sh.mkdosfs('-F', '32', '-s', '1', '-n', 'EFI', config.efi_dev)

    # format boot
    mkfsext4 = sh.Command("mkfs.ext4")
    mkfsext4('-qF', '-L', 'boot', config.boot_dev)


@zor.command('disk-wipe')
def disk_wipe():
    """ Wipe all filesystem and parition data from the disk.  """
    print('Destroying filesystem and partition data')
    sh.wipefs('-a', config.disk_dev)
    sh.sgdisk('--zap-all', config.disk_dev)
    sh.sgdisk('-og', config.disk_dev)
    print('Writing 10GB of zeros to the drive, this may take seconds or minutes depending on disk speed')
    sh.dd('bs=10M', 'count=1024', 'if=/dev/zero', f'of={config.disk_dev}', 'conv=fdatasync', _out=sys.stdout)


@zor.command()
def efi():
    """ Write programs to EFI partition """
    partitions = Partitions()

    paths.efi_mnt.mkdir(exist_ok=True)

    if not partitions.is_mounted(paths.efi_mnt):
        sh.mount(config.efi_dev, paths.efi_mnt)
    paths.efi.mkdir(exist_ok=True)

    # clean slate
    sh.rm('-rf', paths.efi_boot)

    # Make refind the default loader by naming convention so that we don't have
    # to worry about EFI variables being set correctly
    sh.cp('-r', '/usr/share/refind/refind', paths.efi_boot)
    sh.mv(paths.efi_boot / 'refind_x64.efi', paths.efi_boot / 'bootx64.efi')

    # Memtest
    paths.memtest_mnt.mkdir(exist_ok=True)
    if not partitions.is_mounted(paths.memtest_mnt):
        img_fpath, efi_start_bytes = memtest_extract()
        sh.mount('-o', f'loop,ro,offset={efi_start_bytes}', img_fpath, paths.memtest_mnt)


    # clean slate and copy files to our EFI partition
    sh.rm('-rf', paths.efi_memtest)
    sh.cp('-r', paths.memtest_boot, paths.efi_memtest)
    sh.mv(paths.efi_memtest / 'BOOTX64.efi', paths.efi_memtest / 'memtestx64.efi')


@zor.command()
@click.option('--wipe-first', is_flag=True, default=False)
def zpool(wipe_first):
    """ Create ZFS pool and datasets """
    if wipe_first:
        sh.zfs.umount('-a')
        sh.zpool.destroy(config.pool_name, _ok_code=(0,1))

    sh.zpool.create(
        '-o', 'ashift=12',
        '-O', 'acltype=posixacl',
        '-O', 'canmount=off',
        '-O', 'compression=lz4',
        '-O', 'dnodesize=auto',
        '-O', 'normalization=formD',
        '-O', 'relatime=on',
        '-O', 'xattr=sa',
        '-O', 'encryption=aes-256-gcm',
        '-O', 'keylocation=prompt',
        '-O', 'keyformat=passphrase',
        '-O', 'mountpoint=none',
        '-R', paths.zroot,
        config.pool_name,
        config.zfs_dev,
        _fg=True,
    )


@zor.command()
@click.option('--wipe-first', is_flag=True, default=False)
def zfs(wipe_first):
    """ Create ZFS pool and dataset """
    zfs_create(wipe_first)


@zor.command('install-os')
@click.option('--wipe-first', is_flag=True, default=False)
def install_os(wipe_first):
    """ Install the OS into the presumably mounted datasets """
    if wipe_first:
        zfs_create(wipe_first)

    username = input('Admin user\'s username?: ')
    password = getpass.getpass('Admin user\'s password?: ')
    password2 = getpass.getpass('Confirm password: ')

    assert password == password2, 'Passwords did not match'

    db_tarball_fpath = config.cache_dpath / 'debootstrap.tar'
    if not db_tarball_fpath.exists():
        sh.debootstrap('--make-tarball', db_tarball_fpath, config.release_codename, '/tmp/not-there', _fg=True)

    if not paths.zroot.joinpath('bin').exists():
        sh.zfs('set', 'devices=on', config.os_root_ds)
        sh.debootstrap('--unpack-tarball', db_tarball_fpath, config.release_codename, paths.zroot, _fg=True)
        sh.zfs('set', 'devices=off', config.os_root_ds)

    boot_dpath = paths.zroot / 'boot'
    boot_dpath.joinpath('refind_linux.conf').write_text(boot_refind_conf_tpl.format(zfs_os_root_ds=config.os_root_ds))

    etc_fpath = paths.zroot / 'etc'
    etc_fpath.joinpath('apt', 'sources.list').write_text(apt_sources_list.format(codename=config.release_codename))
    etc_fpath.joinpath('fstab').write_text(etc_fstab_tpl)
    etc_fpath.joinpath('hostname').write_text(config.hostname)
    etc_fpath.joinpath('hosts').write_text(etc_hosts_tpl.format(hostname=config.hostname))

    other_mounts()

    # Customize OS in chroot
    # ----------------------
    chroot = sh.chroot.bake(paths.zroot)

    chroot('apt', 'update')

    chroot('locale-gen', '--purge', 'en_US.UTF-8', _fg=True)
    chroot('update-locale', LANG="en_US.UTF-8", LANGUAGE="en_US:en", _fg=True)

    chroot('ln', '-fs', '/usr/share/zoneinfo/US/Eastern', '/etc/localtime', _fg=True)
    chroot('dpkg-reconfigure', '-f', 'noninteractive', 'tzdata', _fg=True)

    # Have to install the kernel and zfs-initramfs so that ZFS is installed and creating the user's
    # dataset below works.
    chroot('apt', 'install', '--yes', '--no-install-recommends', 'linux-image-generic', _fg=True)
    chroot('apt', 'install', '--yes', 'zfs-initramfs', _fg=True)

    # `update-initramfs -uk all` doesn't work, see:
    # https://bugs.launchpad.net/ubuntu/+source/initramfs-tools/+bug/1829805
    for kernel_version in kernels_in_boot():
        chroot('update-initramfs', '-uk', kernel_version, _fg=True)

    # Create user
    # Todo should each user have their own dataset for their home directory?
    # chroot.zfs.create(f'{config.pool_name}/home/{username}')
    chroot.adduser('--disabled-login', '--gecos=,', username)
    chroot.chpasswd(_in=f'{username}:{password}')

    chroot.addgroup('--system', 'lpadmin')
    chroot.addgroup('--system', 'sambashare')
    chroot.addgroup('--system', 'netdev')
    chroot.usermod('-a', '-G', 'adm,cdrom,dip,lpadmin,netdev,plugdev,sambashare,sudo', username)

    # Full OS Install
    # apt dist-upgrade --yes
    # apt install --yes xubuntu-desktop
    
    # reset password on sampro pools
    # Configure networking
    # Disable log compression
    # Set ZFS trim
    # Swap

if __name__ == '__main__':
    zor()
