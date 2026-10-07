import zipfile, os

root = 'wfflab__wfmt-215-交付-20261007'
out = 'wfflab__wfmt-215-交付包-20261007.zip'

with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f)
            arc = p.replace(os.sep, '/')
            z.write(p, arc)

print('rebuilt', out)
z = zipfile.ZipFile(out)
for n in z.namelist():
    i = z.getinfo(n)
    print('%9d  %s' % (i.file_size, n))
