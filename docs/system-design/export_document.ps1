param(
    [Parameter(Mandatory = $true)][string]$InputDocx,
    [Parameter(Mandatory = $true)][string]$OutputPdf,
    [Parameter(Mandatory = $true)][string]$NavigationManifest,
    [Parameter(Mandatory = $true)][string]$ResultJson,
    [switch]$ExportWithoutFieldRefresh
)

$ErrorActionPreference = 'Stop'
$documentRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $documentRoot '..\..'))
$allowedRoots = @(
    $documentRoot,
    (Join-Path $projectRoot '.local\document-planning'),
    (Join-Path $projectRoot 'artifacts\document-qa')
)
$inputPath = [System.IO.Path]::GetFullPath($InputDocx)
$pdfPath = [System.IO.Path]::GetFullPath($OutputPdf)
$manifestPath = [System.IO.Path]::GetFullPath($NavigationManifest)
$resultPath = [System.IO.Path]::GetFullPath($ResultJson)
foreach ($candidatePath in @($inputPath, $pdfPath, $manifestPath, $resultPath)) {
    $allowedPath = $false
    foreach ($allowedRoot in $allowedRoots) {
        $allowedPrefix = [System.IO.Path]::GetFullPath($allowedRoot).TrimEnd('\') + '\'
        if ($candidatePath.StartsWith($allowedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { $allowedPath = $true }
    }
    if (-not $allowedPath) {
        throw 'Conversion paths must stay within the document directory or its project QA folders.'
    }
}
if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) { throw 'Input DOCX does not exist.' }
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'Navigation manifest does not exist.' }
$manifest = [System.IO.File]::ReadAllText($manifestPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
$wordInstance = $null
$ownedDocument = $null
$ownsInstance = $false
$records = @()
$pageCount = $null
$stage = 'creating-instance'

try {
    $wordInstance = New-Object -ComObject Word.Application
    if ($wordInstance.Documents.Count -ne 0) {
        throw 'Refusing an application instance that already has documents open.'
    }
    $ownsInstance = $true
    $wordInstance.Visible = $false
    $wordInstance.DisplayAlerts = 0
    $wordInstance.ScreenUpdating = $false
    $stage = 'opening-owned-document'
    Write-Output 'Created an empty task-owned Word instance; opening the local document.'
    Unblock-File -LiteralPath $inputPath
    $ownedDocument = $wordInstance.Documents.Open($inputPath, $false, $false, $false)
    Write-Output 'Opened the task-owned document in a hidden Word instance.'
    $diagnostics = [pscustomobject]@{
        document_read_only = [bool]$ownedDocument.ReadOnly
        protection_type = [int]$ownedDocument.ProtectionType
        protected_view_count = [int]$wordInstance.ProtectedViewWindows.Count
        word_version = [string]$wordInstance.Version
        apartment = [string][System.Threading.Thread]::CurrentThread.ApartmentState
    }
    Write-Output ($diagnostics | ConvertTo-Json -Compress)
    [System.IO.File]::WriteAllText(($resultPath + '.state.json'), ($diagnostics | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false)))
    if ($ownedDocument.TablesOfContents.Count -ne 0) {
        throw 'This export path requires a static TOC with no native TOC field.'
    }
    Start-Sleep -Seconds 3
    if (-not $ExportWithoutFieldRefresh) {
        $stage = 'updating-fields'
        $null = $ownedDocument.Fields.Update()
        $stage = 'repaginating'
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                $ownedDocument.Repaginate()
                break
            }
            catch {
                if ($attempt -eq 3 -or $_.Exception.Message -notlike '*macro is currently running*') { throw }
                Write-Output ('Word is not ready for pagination; retry ' + $attempt + ' of 3.')
                Start-Sleep -Seconds 3
            }
        }
    }
    $stage = 'exporting-pdf'
    $ownedDocument.ExportAsFixedFormat($pdfPath, 17, $false, 0, 0, 1, 1, 0, $true, $true, 1, $true, $true, $false)
    $stage = 'collecting-bookmark-pages'
    foreach ($heading in $manifest.headings) {
        if (-not $ownedDocument.Bookmarks.Exists([string]$heading.bookmark)) {
            throw ('Missing heading bookmark: ' + [string]$heading.bookmark)
        }
        $bookmarkObject = $null
        $bookmarkRange = $null
        try {
            $bookmarkObject = $ownedDocument.Bookmarks.Item([string]$heading.bookmark)
            $bookmarkRange = $bookmarkObject.Range
            $records += [pscustomobject]@{
                key = [string]$heading.key
                bookmark = [string]$heading.bookmark
                title = [string]$heading.title
                level = [int]$heading.level
                page = [int]$bookmarkRange.Information(3)
                range_text = [string]$bookmarkRange.Text
            }
        }
        finally {
            if ($null -ne $bookmarkRange) { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($bookmarkRange) }
            if ($null -ne $bookmarkObject) { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($bookmarkObject) }
        }
    }
    $contentRange = $ownedDocument.Content
    try { $pageCount = [int]$contentRange.Information(4) }
    finally { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($contentRange) }
    if (-not $ExportWithoutFieldRefresh) {
        $stage = 'saving-document'
        $ownedDocument.Save()
    }
    $stage = 'recording-result'
    $result = [pscustomobject]@{
        input_docx = $inputPath
        output_pdf = $pdfPath
        page_count = $pageCount
        heading_pages = $records
        word_visible = [bool]$wordInstance.Visible
        native_toc_count = [int]$ownedDocument.TablesOfContents.Count
        explicit_field_refresh = -not [bool]$ExportWithoutFieldRefresh
        page_information_constant = 3
        page_information_source = 'https://learn.microsoft.com/en-us/office/vba/api/word.wdinformation'
    }
    $resultText = $result | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($resultPath, $resultText, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output ('PDF exported. Pages: ' + $pageCount + '; heading bookmarks: ' + $records.Count)
}
catch {
    Write-Error ('Document conversion failed at ' + $stage + ': ' + $_.Exception.Message)
    throw
}
finally {
    if ($null -ne $ownedDocument) {
        try { $ownedDocument.Close(0) }
        finally { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($ownedDocument) }
    }
    if ($null -ne $wordInstance) {
        try { if ($ownsInstance) { $wordInstance.Quit(0) } }
        finally { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordInstance) }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
