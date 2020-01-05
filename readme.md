Ubuntu Root on ZFS
==================

Resources
---------

 - [My notes and files on previous ZOR][gist]
 - [Debian Buster Root on ZFS][debzfs]
 
[gist]: https://gist.github.com/rsyring/849d40f828194d124577e4b49abee373
[debzfs]: https://github.com/zfsonlinux/zfs/wiki/Debian-Buster-Root-on-ZFS


Live Env Steps
--------------

1. Mount USB media
2. Touchpad: no click on touch
3. Connect to WiFi
4. `sudo sh live-env-prep.sh`

ToDo
----

* fix update-initramfs so it runs for all installed kernals due to: https://bugs.launchpad.net/ubuntu/+source/initramfs-tools/+bug/1829805
* setup swap partition
* better password for sampro
* Full OS Install
* Configure networking
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
