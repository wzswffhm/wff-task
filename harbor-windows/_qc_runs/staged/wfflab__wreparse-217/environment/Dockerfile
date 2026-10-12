# WReparse task image.
#
# The task runs on Windows PowerShell 5.1 over an NTFS volume, so the only real
# platform requirement is a Windows Server Core base image of a locked tag.
# Windows PowerShell 5.1, NTFS reparse-point APIs and the cmd.exe built-ins
# (mklink) used by the fixture are all part of that base image, which keeps the
# image reproducible without network access at run time.

FROM mcr.microsoft.com/windows/servercore:ltsc2022

# Fixed payload location so every entry point can use absolute paths and never
# depends on the caller's working directory.
WORKDIR C:/task

CMD ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "C:\\task\\environment\\run.ps1"]

# QC adaptation: harbor runs the task from an image, not from a
# bind-mounted task tree, so the candidate workspace must be baked in.
COPY ["workspace/", "C:/testbed/"]
