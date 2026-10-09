# WReparse task image.
#
# The task runs on Windows PowerShell 5.1 over an NTFS volume, so the only real
# platform requirement is a Windows Server Core base image of a locked tag.
# Windows PowerShell 5.1, NTFS reparse-point APIs and the cmd.exe built-ins
# (mklink) used by the fixture are all part of that base image, which keeps the
# image reproducible without network access at run time.

FROM mcr.microsoft.com/windows/servercore:ltsc2022

# The task runs on Windows PowerShell 5.1 over an NTFS volume, so the only real
# platform requirement is a Windows Server Core base image of a locked tag.
# Windows PowerShell 5.1, NTFS reparse-point APIs and the cmd.exe built-ins
# (mklink) used by the fixture are all part of that base image, which keeps the
# image reproducible without network access at run time.
#
# Two consumers share this image:
#   * the local Outside Harbor runner bind-mounts the whole task tree at C:\task
#     and only needs the base image plus that WORKDIR;
#   * standard Harbor has no bind mount, so the candidate workspace must be baked
#     into the image at the same place the runner exposes it (C:\testbed, which
#     is also the [environment].workdir declared in task.toml).

WORKDIR C:/task

# Candidate workspace. Kept as its own layer so Harbor-built images and the
# prebuilt local image stay byte-identical in the region the tests read.
COPY ["workspace/", "C:/testbed/"]

CMD ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "C:\\task\\environment\\run.ps1"]
