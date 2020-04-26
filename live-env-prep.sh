setxkbmap -option "ctrl:swap_lalt_lctl"

echo 'Acquire::http { Proxy "http://server.lan:3142"; };' > /etc/apt/apt.conf.d/01-Proxy

apt update
apt install --yes python3-pip gdisk debootstrap zfs-initramfs

# ToDo: automate answering no to the install to ESP question
apt install --yes refind

pip3 install click sh
