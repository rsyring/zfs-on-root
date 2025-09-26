Ubuntu Root on ZFS
==================

Usage Steps
-----------

If you are REALLY sure your `zor-config.ini` is accurate:

* sudo python3 zor.py status
* sudo python3 zor.py install

The more sensible path is probably to run all these commands one-by-one, whic is what `install`
does:

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
  - If this errors out the first time you run due to proc, just run it again.

### Rescue Image

If you have a separate hard drive, zor can WIPE IT and make it bootable with the current
live image.  Example:

 ❯ sudo zor create-rescue xubu2404 /dev/disk/by-id/nvme-TOSHIBA-RC100_487PA0XRPW7S --part-prefix toshd

 This will:

 * WIPE the given drive
 * Create an EFI partition and install refind as the default boot image
 * Create a second partition and clone the partition given.  Most commonly, the one that represents
   the current live environment running.

Troubleshooting
----------------

* sudo python3 zor.py recover [--chroot]
* sudo python3 zor.py install-os [--wipe-first]
* sudo python3 zor.py chroot
* sudo python3 zor.py unmount


Copier Template
------------------

Project structure and tooling mostly derives from the [copier-py-package](https://github.com/level12/copier-py-package),
see its documentation for context and additional instructions.

This project can be updated from the upstream repo, see [updates](https://github.com/level12/copier-py-package?tab=readme-ov-file#updates)


## Versions

Versions are date based.  Tools:

- Current version: `hatch version`
- Bump version based on date, tag, push: `mise run bump`
   - Options: `mise run bump -- --help`
