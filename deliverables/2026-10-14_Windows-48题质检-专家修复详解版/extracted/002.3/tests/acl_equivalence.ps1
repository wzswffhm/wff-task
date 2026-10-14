$ErrorActionPreference = 'Stop'
function ConvertTo-AceBytes($Ace) {
    $bytes = New-Object byte[] $Ace.BinaryLength
    $Ace.GetBinaryForm($bytes, 0)
    [Convert]::ToBase64String($bytes)
}
function ConvertTo-AclBlocks($Acl) {
    if ($null -eq $Acl) { return 'NULL' }
    $blocks = [Collections.Generic.List[string]]::new()
    $index = 0
    while ($index -lt $Acl.Count) {
        $ace = $Acl[$index]
        if ($ace.AceType -eq [Security.AccessControl.AceType]::AccessAllowed) {
            $inherited = $ace.AceFlags.value__ -band 16
            $members = [Collections.Generic.List[string]]::new()
            while ($index -lt $Acl.Count -and $Acl[$index].AceType -eq [Security.AccessControl.AceType]::AccessAllowed -and ($Acl[$index].AceFlags.value__ -band 16) -eq $inherited) {
                $members.Add((ConvertTo-AceBytes $Acl[$index]))
                $index++
            }
            $sorted = $members.ToArray()
            [Array]::Sort($sorted, [StringComparer]::Ordinal)
            $blocks.Add(('ALLOW:' + $inherited + ':' + ($sorted -join ',')))
        } else {
            $blocks.Add(('FIXED:' + (ConvertTo-AceBytes $ace)))
            $index++
        }
    }
    return ($blocks -join '|')
}
function ConvertTo-DescriptorSignature([Security.AccessControl.RawSecurityDescriptor]$Descriptor) {
    $owner = if ($null -eq $Descriptor.Owner) { 'NULL' } else { $Descriptor.Owner.Value }
    $group = if ($null -eq $Descriptor.Group) { 'NULL' } else { $Descriptor.Group.Value }
    $sacl = if ($null -eq $Descriptor.SystemAcl) { 'NULL' } else {
        $bytes = New-Object byte[] $Descriptor.SystemAcl.BinaryLength
        $Descriptor.SystemAcl.GetBinaryForm($bytes, 0)
        [Convert]::ToBase64String($bytes)
    }
    return ([ordered]@{owner=$owner; group=$group; control=[int]$Descriptor.ControlFlags; sacl=$sacl; dacl=(ConvertTo-AclBlocks $Descriptor.DiscretionaryAcl)} | ConvertTo-Json -Compress)
}
function Get-DescriptorSignature([string]$Path) {
    ConvertTo-DescriptorSignature (Read-ShapeDescriptor $Path)
}
