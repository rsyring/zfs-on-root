# https://www.rodsbooks.com/gdisk/sgdisk-walkthrough.html
# http://manpages.ubuntu.com/manpages/eoan/man8/sgdisk.8.html
# https://github.com/zfsonlinux/zfs/wiki/Debian-Buster-Root-on-ZFS

set -e
set -x

. $(dirname $0)/env-vars.sh
[[ -z "$DISK" ]] && { echo 'Environment variables not loaded, $DISK is empty' ; exit 1; }

sgdisk --zap-all $DISK
wipefs -a $DISK
sgdisk -og $DISK

# UEFI partition
sgdisk -n 1:1M:+512M -c 1:EFI -t 1:EF00 $DISK

# ext2 boot partition
sgdisk -n 2:0:+2G -c 2:boot -t 2:8300 $DISK

# zfs rpool partition
sgdisk -n 3:0:0 -c 3:zfs -t 3:BF01 $DISK

sgdisk -p $DISK

# have to give time or the part2 won't be seen by the OS yet
sleep 1

# format EFI
mkdosfs -F 32 -s 1 -n EFI ${DISK}-part1

# format boot
mkfs.ext4 -qF -L boot $DISK-part2

