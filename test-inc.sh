# https://www.rodsbooks.com/gdisk/sgdisk-walkthrough.html
# http://manpages.ubuntu.com/manpages/eoan/man8/sgdisk.8.html
# https://github.com/zfsonlinux/zfs/wiki/Debian-Buster-Root-on-ZFS

set -e
# set -x

. $(dirname $0)/inc-vars.sh
[[ -z "$DISK" ]] && { echo 'Environment variables not loaded, $DISK is empty' ; exit 1; }

echo '$DISK' is: 

