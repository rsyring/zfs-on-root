# ------------------
# File templates
# ------------------
from pathlib import Path


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
PARTLABEL={config.boot_partname}           /boot      ext4    defaults,nodev,relatime     0      1
PARTLABEL={config.efi_partname}           /boot/efi  vfat    defaults,nodev,relatime     0      2
""".lstrip()

boot_refind_conf_tpl = """
"Boot" "rw root=ZFS={zfs_os_root_ds}"
"ZFS Debug" "rw root=ZFS={zfs_os_root_ds} zfsdebug=on"
"SD Debug" "rw root=ZFS={zfs_os_root_ds} systemd.log_level=debug systemd.log_target=kmsg log_buf_len=1M printk.devkmsg=on enforcing=0"
""".lstrip()  # noqa: E501

apt_sources_list = """
deb http://archive.ubuntu.com/ubuntu {codename} main restricted universe multiverse
deb-src http://archive.ubuntu.com/ubuntu {codename} main restricted universe multiverse

deb http://security.ubuntu.com/ubuntu {codename}-security main restricted universe multiverse
deb-src http://security.ubuntu.com/ubuntu {codename}-security main restricted universe multiverse

deb http://archive.ubuntu.com/ubuntu {codename}-updates main restricted universe multiverse
deb-src http://archive.ubuntu.com/ubuntu {codename}-updates main restricted universe multiverse
""".lstrip()


def kernels_in_boot(boot_dpath: Path):
    kernel_fpaths = boot_dpath.glob('vmlinuz-*')
    # Path names look like: vmlinuz-5.3.0-24-generic
    # Strip off "vmlinuz-" leaving just the version that can be fed to update-initramfs
    kernel_versions = [fpath.name[8:] for fpath in kernel_fpaths]
    return kernel_versions
