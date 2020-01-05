set -x
set -e

SSD_POOL=sampro
ROOT_DS=$SSD_POOL/xubu1910
SSD_MNT=/mnt/$SSD_POOL
HOSTNAME=precision1219
RELEASE_CODENAME=eoan
DB_TARBALL=/media/xubuntu/6BDE-9A86/debootstrap.tar

zfs set devices=on $SSD_POOL

if [ -z "$(find /var/cache/apt/pkgcache.bin -mmin -60)" ]; then
  apt update
fi

if [ ! -f $DB_TARBALL ]; then
    debootstrap --make-tarball=$DB_TARBALL $RELEASE_CODENAME /tmp/not-there
fi

debootstrap --unpack-tarball=$DB_TARBALL $RELEASE_CODENAME $SSD_MNT
zfs set devices=off $SSD_POOL

echo $HOSTNAME > $SSD_MNT/etc/hostname

cat >$SSD_MNT/etc/hosts <<EOL
127.0.0.1 localhost
127.0.1.1 ${HOSTNAME}

# The following lines are desirable for IPv6 capable hosts
::1     ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
ff02::3 ip6-allhosts
EOL

cat >$SSD_MNT/etc/fstab <<EOL
# <device>               <dir>      <type>  <options>                   <dump> <fsck>
PARTLABEL=boot           /boot      ext4    defaults,nodev,relatime     0      1
PARTLABEL=EFI            /boot/efi  vfat    defaults,nodev,relatime     0      2
EOL

mkdir -p $SSD_MNT/boot
mount /dev/disk/by-partlabel/boot $SSD_MNT/boot

mount --rbind /dev  $SSD_MNT/dev --make-rslave
mount --rbind /proc $SSD_MNT/proc --make-rslave
mount --rbind /sys  $SSD_MNT/sys --make-rslave

chroot $SSD_MNT apt update

chroot $SSD_MNT locale-gen --purge en_US.UTF-8
chroot $SSD_MNT update-locale LANG="en_US.UTF-8" LANGUAGE="en_US:en"

chroot $SSD_MNT ln -fs /usr/share/zoneinfo/US/Eastern /etc/localtime
chroot $SSD_MNT dpkg-reconfigure -f noninteractive tzdata

chroot $SSD_MNT apt install --yes --no-install-recommends linux-image-generic
chroot $SSD_MNT apt install --yes zfs-initramfs

#$ sudo apt-add-repository ppa:rodsmith/refind
#$ sudo apt-get update
#$ sudo apt-get install refind

# If you want a tmpfs for /tmp, only used if you DID NOT create a /tmpo zfs dataset
#cp /usr/share/systemd/tmp.mount /etc/systemd/system/
#systemctl enable tmp.mount

