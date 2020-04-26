Ubuntu Root on ZFS
==================

Resources
---------

- [My notes and files on previous ZOR][gist]
- [Debian Buster Root on ZFS][debzfs]
- [Ubuntu 18.04 root on ZFS][ubuzfs]

[gist]: https://gist.github.com/rsyring/849d40f828194d124577e4b49abee373
[debzfs]: https://github.com/zfsonlinux/zfs/wiki/Debian-Buster-Root-on-ZFS
[ubuzfs]: https://github.com/zfsonlinux/zfs/wiki/Ubuntu-18.04-Root-on-ZFS

Live Env Steps
--------------

1. Mount USB media
2. Touchpad: no click on touch
3. Connect to WiFi
4. `sudo sh live-env-prep.sh`

Usage Steps
-----------

* sudo python3 zor.py status
* sudo python3 zor.py disk-wipe
* sudo python3 zor.py disk-partition
* sudo python3 zor.py disk-format
* sudo python3 zor.py efi
* sudo python3 zor.py zpool
* sudo python3 zor.py zfs
* sudo python3 zor.py install-os
* sudo python3 zor.py install-user
* sudo python3 zor.py install-desktop
* sudo python3 zor.py status
* sudo python3 zor.py unmount

* sudo python3 zor.py recover
* sudo python3 zor.py chroot
* sudo python3 zor.py unmount


ToDo
----

* Configure swap
  - should be encrypted
  - /etc/sysctl.conf:
    vm.swappiness=1
    vm.vfs_cache_pressure=50
* Disable log compression
* Set ZFS trim

Commands
--------

CTRL / ALT swap:

`$ setxkbmap -option "ctrl:swap_lalt_lctl"`


Zero out the drive:

`$ sudo dd bs=10M count=1024 if=/dev/zero of=/dev/disk/by-id/nvme-Samsung_SSD_960_PRO_1TB_S3EVNX0J802831N conv=fdatasync status=progress`


Find processes that prevent unmount:

`$ sudo fuser -vm /mnt/sampro`
