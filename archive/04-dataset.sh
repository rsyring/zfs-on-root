
# https://github.com/zfsonlinux/zfs/wiki/Debian-Buster-Root-on-ZFS
set -x
set -e

SSD_POOL=sampro
ROOT_DS=$SSD_POOL/xubu1910
SSD_MNT=/mnt/$SSD_POOL

# Start with a clean slate
umount -q $SSD_MNT/boot || true
zfs umount -a
zfs destroy -r $ROOT_DS
rm -rf $SSD_MNT

# Just a container that gives children mountpoints through inheritance
zfs create -o canmount=off -o mountpoint=/ $ROOT_DS

# Have to create and mount this now, or the mounts that happen later prevent this mount from happening
# b/c the directory is not empty
zfs create -o canmount=noauto -o mountpoint=/ $ROOT_DS/os
zfs mount $ROOT_DS/os

# Another container, has to be present to create the other var datasets below, but we will never mount this
zfs create -o canmount=off $ROOT_DS/var

# Separate dataset for logs so that if we rollback a snapshot, we don't lose logs for troubleshooting.
zfs create $ROOT_DS/var/log

# Datasets that should not be in a snapshot
zfs create -o com.sun:auto-snapshot=false $ROOT_DS/var/cache
zfs create -o com.sun:auto-snapshot=false $ROOT_DS/var/tmp

# Special settings see Arch wiki for details: https://wiki.archlinux.org/index.php/ZFS
zfs create -o recordsize=8K \
             -o primarycache=metadata \
             -o mountpoint=/var/lib/postgresql \
             -o logbias=throughput \
              $ROOT_DS/postgresql
              
# Custom settings for /tmp
zfs create -o com.sun:auto-snapshot=false -o setuid=off -o devices=off -o sync=disabled $ROOT_DS/tmp

chmod 1777 $SSD_MNT/var/tmp
chmod 1777 $SSD_MNT/tmp


# re-mount non-OS mounts
zfs mount $SSD_POOL/home
zfs mount $SSD_POOL/home/root


zfs list -r  -o name,canmount,mountpoint $SSD_POOL

