function NG-CountValue($Value) {
    $parsed = 0
    if ($null -eq $Value -or -not [int]::TryParse([string]$Value, [ref]$parsed) -or $parsed -lt 0) {
        throw 'Candidate FileCount must be a nonnegative Int32 decimal value'
    }
    return $parsed
}

function NG-AceBytes($Ace) {
    $bytes = New-Object byte[] $Ace.BinaryLength
    $Ace.GetBinaryForm($bytes, 0)
    return [Convert]::ToBase64String($bytes)
}

function NG-DaclBlocks($Acl) {
    if ($null -eq $Acl) { return 'NULL' }
    $blocks = [Collections.Generic.List[string]]::new()
    $index = 0
    while ($index -lt $Acl.Count) {
        $ace = $Acl[$index]
        if ($ace.AceType -eq [Security.AccessControl.AceType]::AccessAllowed) {
            $inherited = [int]$ace.AceFlags -band 16
            $members = [Collections.Generic.List[string]]::new()
            while ($index -lt $Acl.Count -and $Acl[$index].AceType -eq [Security.AccessControl.AceType]::AccessAllowed -and ([int]$Acl[$index].AceFlags -band 16) -eq $inherited) {
                $members.Add((NG-AceBytes $Acl[$index]))
                $index++
            }
            $sorted = $members.ToArray()
            [Array]::Sort($sorted, [StringComparer]::Ordinal)
            $blocks.Add('ALLOW:' + $inherited + ':' + ($sorted -join ','))
        } else {
            $blocks.Add('FIXED:' + (NG-AceBytes $ace))
            $index++
        }
    }
    return $blocks -join '|'
}
