
# OCR脚本 - 使用Windows.Media.Ocr
param([string]$ImagePath)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

try {
    # 加载必要的程序集
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    Add-Type -AssemblyName System.WindowsRuntime
    Add-Type -AssemblyName System.Drawing
    
    # 加载WinRT类型
    $null = [Windows.Media.Ocr.OcrEngine, Windows.Media, ContentType=WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
    $null = [Windows.Storage.Streams.RandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
    $null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType=WindowsRuntime]
    
    # 读取文件
    $fileBytes = [System.IO.File]::ReadAllBytes($ImagePath)
    
    # 转换为IRandomAccessStream
    $stream = New-Object System.IO.MemoryStream(, $fileBytes)
    $randomStream = [Windows.Storage.Streams.RandomAccessStream]::new()
    $writer = New-Object Windows.Storage.Streams.DataWriter($randomStream)
    $writer.WriteBytes($fileBytes)
    $writer.StoreAsync().GetResults() | Out-Null
    $randomStream.Seek(0)
    
    # 解码图像
    $decoderTask = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($randomStream)
    $decoder = $decoderTask.GetResults()
    
    $bitmapTask = $decoder.GetSoftwareBitmapAsync()
    $bitmap = $bitmapTask.GetResults()
    
    # 创建OCR引擎
    $ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    
    if ($ocrEngine) {
        $ocrTask = $ocrEngine.RecognizeAsync($bitmap)
        $result = $ocrTask.GetResults()
        
        if ($result) {
            $text = $result.Text
            if ([string]::IsNullOrWhiteSpace($text)) {
                Write-Output "OCR_NO_TEXT"
            } else {
                Write-Output $text
            }
        } else {
            Write-Output "OCR_NO_RESULT"
        }
    } else {
        Write-Output "OCR_ENGINE_NULL"
    }
} catch {
    Write-Output "OCR_ERROR: $($_.Exception.Message)"
}
