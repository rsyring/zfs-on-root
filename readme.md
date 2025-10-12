Ubuntu Root on ZFS
==================

Install
-------

Install with `uv`.

Example: `uv tool install -e ./zfs-on-root`


Usage Steps
-----------

If you are REALLY sure your `zor-config.ini` is accurate:

* zor status
* zor install

The more sensible path is probably to run all these commands one-by-one, which is what `install`
does:

* zor status
* zor disk-wipe
* zor disk-partition
* zor disk-format
* zor efi
* zor zpool
* zor zfs
* zor install-os
* zor install-user
* zor install-desktop
* zor status
* zor unmount
  - Make sure you unmount which exports the zpool.
  - If this errors out the first time you run due to proc, just run it again.


Rescue Image
------------

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


## Dev

### Copier Template

Project structure and tooling mostly derives from the [Coppy](https://github.com/level12/coppy),
see its documentation for context and additional instructions.

This project can be updated from the upstream repo, see
[Updating a Project](https://github.com/level12/coppy?tab=readme-ov-file#updating-a-project).

### Project Setup

From zero to hero (passing tests that is):

1. Ensure [host dependencies](https://github.com/level12/coppy/wiki/Mise) are installed

2. Start docker service dependencies (if applicable):

   `docker compose up -d`

3. Sync [project](https://docs.astral.sh/uv/concepts/projects/) virtualenv w/ lock file:

   `uv sync`

4. Configure pre-commit:

   `pre-commit install`

5. Run tests:

   `nox`

### Versions

Versions are date based.  A `bump` action exists to help manage versions:

```shell

  # Show current version
  mise bump --show

  # Bump version based on date, tag, and push:
  mise bump

  # See other options
  mise bump -- --help
```
