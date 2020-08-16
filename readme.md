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

1. Mount USB media (or use automount)
2. Touchpad: no click on touch
3. Connect to WiFi
4. `sudo sh live-env-prep.sh`
5. edit zor-config.ini

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
  - Make sure you unmount which exports the zpool.
  - This errors out the first time you run due to proc, just run it again.

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

Find processes that prevent unmount:

`$ sudo fuser -vm /mnt/sampro`
