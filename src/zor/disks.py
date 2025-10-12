from dataclasses import dataclass
import enum
import json
from pathlib import Path
import subprocess

import psutil

from . import utils


class PartType(enum.Enum):
    linux = '8300'
    efi = 'ef00'
    zfs = 'bf00'


def disk_wipe(disk_dev: str | Path, write_zeros: bool = True):
    """Wipe all filesystem and parition data from the disk."""

    if not destroy_confirm(disk_dev):
        return False

    print('Destroying filesystem and partition data on:', disk_dev)
    utils.sub_run('wipefs', '-a', disk_dev)
    utils.sub_run('sgdisk', '--zap-all', disk_dev)
    utils.sub_run('sgdisk', '-og', disk_dev)

    if not write_zeros:
        return True

    print(
        'Writing 10GB of zeros to disk.'
        '  This may take seconds or minutes depending on disk speed...',
    )
    utils.sub_run(
        'dd',
        'bs=10M',
        'count=1024',
        'if=/dev/zero',
        f'of={disk_dev}',
        'conv=fdatasync',
    )

    return True


def disk_partition(
    disk_dev,
    *,
    efi_label: str,
    boot_label: str | None = None,
    zfs_label: str | None = None,
):
    """Partition a presumably blank disk"""
    # format disk as GPT
    utils.sub_run('sgdisk', '-Z', disk_dev, returns=(0, 2))

    # UEFI partition
    utils.sub_run('sgdisk', '-n', '1:1M:+512M', '-c', f'1:{efi_label}', '-t', '1:EF00', disk_dev)

    if boot_label:
        utils.sub_run('sgdisk', '-n', '0:0:+2G', '-c', f'0:{boot_label}', '-t', '2:8300', disk_dev)

    # zfs root pool partition with 20G left at the end for swap, live boot images, etc.
    if zfs_label:
        utils.sub_run('sgdisk', '-n', '0:0:-20G', '-c', f'0:{zfs_label}', '-t', '0:BF01', disk_dev)


def efi_format(part_label: str):
    dev = partlabel_dev(part_label)
    utils.sub_run('mkdosfs', '-F', '32', '-s', '1', '-n', part_label, dev)
    return dev


def partlabel_dev(part_label: str):
    return f'/dev/disk/by-partlabel/{part_label}'


def efi_mount(efi_partlabel: Path, efi_mnt_dir: Path):
    efi_dpath = efi_mnt_dir.joinpath('EFI')

    if Mounts().is_mounted(efi_mnt_dir):
        print('EFI already mounted at:', efi_mnt_dir)
        return efi_dpath

    efi_dev = partlabel_dev(efi_partlabel)

    print('Mounting efi:', efi_dev, efi_mnt_dir)
    efi_mnt_dir.mkdir(exist_ok=True)
    utils.sub_run('mount', efi_dev, efi_mnt_dir)

    efi_dpath.mkdir(exist_ok=True)

    return efi_dpath


def efi_refind(efi_partlabel: str, efi_mnt_dir: Path, as_boot: bool = True):
    """Write refind to EFI partition"""

    efi_dpath = efi_mount(efi_partlabel, efi_mnt_dir)

    refind_dname = 'BOOT' if as_boot else 'refind'
    efi_refind = efi_dpath / refind_dname

    # clean slate
    print('Refind EFI delete:', efi_refind)
    utils.sub_run('rm', '-rf', efi_refind)

    print('Copying refind to EFI')
    utils.sub_run('cp', '-r', '/usr/share/refind/refind', efi_refind)

    if as_boot:
        # Make refind the default loader by naming convention so that we don't have
        # to worry about EFI variables being set correctly
        utils.sub_run('mv', efi_refind / 'refind_x64.efi', efi_refind / 'bootx64.efi')

    utils.sub_run('mv', efi_refind / 'refind.conf-sample', efi_refind / 'refind.conf')
    print('Refind installed to:', efi_refind)


def efi_memtest(efi_dev: Path, efi_mnt_dir: Path, cache_dir: Path):
    """Write memtest to EFI partition"""
    efi_dpath = efi_mount(efi_dev, efi_mnt_dir)

    # Mount the memtest image so we can copy the files
    img_dpath = Path('/mnt/memtest-img')
    img_dpath.mkdir(exist_ok=True)

    if not Mounts().is_mounted(img_dpath):
        img_fpath, efi_start_bytes = memtest_extract(cache_dir)
        utils.sub_run('mount', '-o', f'loop,ro,offset={efi_start_bytes}', img_fpath, img_dpath)
        print('Memtest image mounted at:', img_dpath)

    memtest_src: Path = img_dpath / 'EFI' / 'BOOT'
    memtest_dest = efi_dpath / 'memtest86'

    # Remove anything existing
    print('Clearing:', memtest_dest)
    utils.sub_run('rm', '-rf', memtest_dest)

    # Copy files from image
    print('Copying:', memtest_src, memtest_dest)
    utils.sub_run('cp', '-r', memtest_src, memtest_dest)
    utils.sub_run('mv', memtest_dest / 'BOOTX64.efi', memtest_dest / 'memtest86_x64.efi')


def memtest_extract(cache_dpath: Path):
    zip_fpath = cache_dpath / 'memtest86-usb.zip'
    unzip_fpath = cache_dpath / 'memtest86-usb'
    img_fpath = unzip_fpath / 'memtest86-usb.img'
    zip_url = 'https://www.memtest86.com/downloads/memtest86-usb.zip'

    cache_dpath.mkdir(exist_ok=True)

    if not zip_fpath.exists():
        print('Downloading:', zip_url, 'to', zip_fpath)
        utils.sub_run('wget', '-O', zip_fpath, zip_url)

    if not img_fpath.exists():
        print('Extracting zip to', unzip_fpath)
        utils.sub_run('unzip', '-d', unzip_fpath, zip_fpath)

    output = utils.sub_run('sgdisk', '-p', img_fpath)
    lines = output.strip().splitlines()
    # Second line should look like:
    #   Sector size (logical): 512 bytes
    sector_size = lines[1].split(':')[1].replace('bytes', '').strip()
    sector_size = sector_size

    json_output = utils.sub_run('sfdisk', '--json', img_fpath)
    partitions = json.loads(str(json_output))['partitiontable']['partitions']
    efi_part = [p for p in partitions if p['name'] == 'EFI System Partition'].pop()
    efi_start_sector = efi_part['start']

    efi_start_bytes = int(sector_size) * (efi_start_sector)

    return img_fpath, efi_start_bytes


class Mounts:
    def __init__(self):
        self.partitions = psutil.disk_partitions(all=True)
        self.mounts = [p.mountpoint for p in self.partitions if p.mountpoint]

    def is_mounted(self, fspath):
        return str(fspath) in self.mounts

    def unmount(self, fspath):
        if self.is_mounted(fspath):
            print(f'Unmounting: {fspath}')
            utils.sub_run('umount', '-Rn', fspath)


def sgdisk(*args, **kwargs):
    return utils.sub_run('sgdisk', *args, **kwargs)


def sgdisk_new(size: str, label: str, disk_dev: str, ptype: PartType):
    return sgdisk(
        '--new',
        f'0:0:{size}',
        '--change-name',
        f'0:{label}',
        '--typecode',
        f'0:{ptype.value}',
        disk_dev,
    )


def sgdisk_print_result(result: subprocess.CompletedProcess, *, indent=''):
    if result.returncode == 2:
        print(result.stderr)
        return

    lines = result.stdout.splitlines()
    lines = (f'{indent}{line}' for line in (lines[0:1] + lines[7:]))
    print('\n'.join(lines))


def sgdisk_print(disk_dev, *, indent=''):
    result = sgdisk('--print', disk_dev, returns=(0, 2), capture=True)
    sgdisk_print_result(result, indent=indent)


def destroy_confirm(disk_dev: Path):
    print('\nThis will COMPLETELY DESTROY ALL DATA on:\n')
    sgdisk_print(disk_dev, indent='    ')
    print('\n')

    while True:
        response = input('DESTROY ALL DATA and proceed?  "destroy" or "no": ').strip().lower()
        match response:
            case 'destroy':
                return True
            case 'no':
                return False


@dataclass
class Partition:
    path: str
    dev: str
    parent_dev: str
    label: str
    size: str

    @classmethod
    def from_path(cls, path: str):
        if '/' not in 'path':
            path = f'/dev/disk/by-partlabel/{path}'
        result = utils.sub_run('lsblk', '-Jnblo', 'NAME,PKNAME,PARTLABEL,SIZE', path, capture=True)
        entry = json.loads(result.stdout)['blockdevices'][0]
        pkname = entry.get('pkname')
        return cls(
            path=path,
            dev=entry['name'],
            parent_dev='/dev/' + pkname if pkname else None,
            label=entry['partlabel'],
            size=entry['size'],
        )

    def lsblk_parent(self):
        result = utils.sub_run('lsblk', '-o', 'NAME,PARTLABEL,SIZE', self.parent_dev, capture=True)
        lines = (f'    {line}' for line in result.stdout.splitlines())
        print('\n'.join(lines))

    def __fspath__(self):
        return self.path


def mount(*args, **kwargs):
    return utils.sub_run('mount', *args, **kwargs)


def mounts(config, paths):
    mount(config.boot_dev, f'{paths.zroot}/boot')
    mount('--rbind', '/dev', f'{paths.zroot}/dev', '--make-rslave')
    mount('--rbind', '/proc', f'{paths.zroot}/proc', '--make-rslave')
    mount('--rbind', '/sys', f'{paths.zroot}/sys', '--make-rslave')
    mount('--bind', paths.apt_cache_host, paths.apt_cache)


def unmounts(paths):
    mounts = Mounts()
    mounts.unmount(paths.dev)
    mounts.unmount(paths.proc)
    mounts.unmount(paths.sys)
    mounts.unmount(paths.boot)
    mounts.unmount(paths.efi_mnt)
    mounts.unmount('/mnt/memtest86')
    mounts.unmount(paths.apt_cache)
    print('Unmounted paths')
