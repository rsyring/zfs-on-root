# https://www.rodsbooks.com/gdisk/sgdisk-walkthrough.html
# http://manpages.ubuntu.com/manpages/eoan/man8/sgdisk.8.html
# https://github.com/zfsonlinux/zfs/wiki/Debian-Buster-Root-on-ZFS

mkdir -p $EFI_MNT
umount $EFI_MNT
umount /mnt/memtest86

mount $EFI_DEV $EFI_MNT
rm -rf $EFI_MNT/*

mkdir -p $EFI_MNT/EFI

# Make refind the default loader by naming convention so that we don't have
# to worry about EFI variables being set correctly
cp -r /usr/share/refind/refind $EFI_MNT/EFI/BOOT
mv $EFI_MNT/EFI/BOOT/refind_x64.efi $EFI_MNT/EFI/BOOT/bootx64.efi
mv $EFI_MNT/EFI/BOOT/refind.conf-sample $EFI_MNT/EFI/BOOT/refind.conf

if [ ! -f /tmp/memtest86-usb.zip ]; then
    wget -O /tmp/memtest86-usb.zip https://www.memtest86.com/downloads/memtest86-usb.zip
    
fi

rm -rf /tmp/memtest86-efi
mkdir /tmp/memtest86-efi
unzip /tmp/memtest86-usb.zip -d /tmp/memtest86-efi

mkdir -p /mnt/memtest86
# for getting offset, see https://askubuntu.com/a/236284
mount -o loop,ro,offset=263192576 /tmp/memtest86-efi/memtest86-usb.img /mnt/memtest86

cp -r /mnt/memtest86/EFI/BOOT $EFI_MNT/EFI/memtest86
rm $EFI_MNT/EFI/memtest86/BOOTIA32.efi
mv $EFI_MNT/EFI/memtest86/BOOTX64.efi $EFI_MNT/EFI/memtest86/memtestx64.efi

