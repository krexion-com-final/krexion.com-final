This folder holds cached installers.

On the FIRST install, the wizard will download:

   * DockerDesktopInstaller.exe   (~520 MB)
   * Git-Installer.exe            (~50 MB)

and save them here. On subsequent installs (on this PC or any other
PC if you copy this whole folder via USB), the wizard will detect
the cached files and SKIP the downloads -- saving 10-20 minutes and
working completely offline.

DO NOT DELETE this folder if you plan to reinstall or share the
installer with another PC.

If the cached file is corrupt or partial, the wizard will detect it
(it checks size > 200 MB for Docker and > 10 MB for Git) and
re-download it automatically.
