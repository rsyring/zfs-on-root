
# https://github.com/zfsonlinux/zfs/wiki/Debian-Buster-Root-on-ZFS
set -e
set -x

ZFS_DISK_PART=/dev/disk/by-id/nvme-Samsung_SSD_960_PRO_1TB_S3EVNX0J802831N-part3
SSD_POOL=sampro
ROOT_DS=$SSD_POOL/xubu1910
SSD_MNT=/mnt/$SSD_POOL

read -r -p "Delete the ZFS pool ${SSD_POOL}? [y/N] " response
if [[ $response == "y" || $response == "Y" || $response == "yes" || $response == "Yes" ]]
then
    # Start with a mostly clean slate.  Destroy the ROOT_DS and not the pool itself so as to 
    # not destroy home/shared data if this script is run on an existing zpool.
    zfs umount -a
    zpool destroy -f $SSD_POOL
    rm -rf $SSD_MNT

    zpool create -o ashift=12 \
        -o acltype=posixacl \
        -O canmount=off \
        -O compression=lz4 \
        -O dnodesize=auto \
        -O normalization=formD \
        -O relatime=on \
        -O xattr=sa \
        -O encryption=aes-256-gcm \
        -O keylocation=prompt \
        -O keyformat=passphrase \
        -O mountpoint=none \
        -R $SSD_MNT $SSD_POOL \
        $ZFS_DISK_PART
        
        # Non-OS datasets, these could possibly be shared across different OSs
        # running on the same system
        zfs create -o mountpoint=/home $SSD_POOL/home
        zfs create -o mountpoint=/root $SSD_POOL/home/root
        zfs create -o mountpoint=/shared $SSD_POOL/shared
        zfs create -o mountpoint=/var/lib/docker $SSD_POOL/shared
else
    echo "exiting without change to ${SSD_POOL}"
fi


