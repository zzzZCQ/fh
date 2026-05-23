using System;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices.WindowsRuntime;
using Windows.Graphics.Imaging;
using Windows.Media.Ocr;
using Windows.Storage;
using Windows.Storage.Streams;

namespace WindowsOcr
{
    class Program
    {
        static int Main(string[] args)
        {
            try
            {
                if (args.Length == 0)
                {
                    Console.WriteLine("ERROR: No image path provided");
                    return 1;
                }

                string imagePath = args[0];

                if (!File.Exists(imagePath))
                {
                    Console.WriteLine($"ERROR: File not found: {imagePath}");
                    return 1;
                }

                OcrEngine ocrEngine = OcrEngine.TryCreateFromUserProfileLanguages();
                if (ocrEngine == null)
                {
                    Console.WriteLine("ERROR: OCR engine not available");
                    return 1;
                }

                var file = StorageFile.GetFileFromPathAsync(imagePath).AsTask().GetAwaiter().GetResult();
                using (IRandomAccessStream stream = file.OpenAsync(FileAccessMode.Read).AsTask().GetAwaiter().GetResult())
                {
                    BitmapDecoder decoder = BitmapDecoder.CreateAsync(stream).AsTask().GetAwaiter().GetResult();
                    SoftwareBitmap bitmap = decoder.GetSoftwareBitmapAsync().AsTask().GetAwaiter().GetResult();
                    OcrResult result = ocrEngine.RecognizeAsync(bitmap).AsTask().GetAwaiter().GetResult();
                    
                    if (!string.IsNullOrEmpty(result.Text))
                    {
                        Console.WriteLine(result.Text);
                    }
                    
                    bitmap.Dispose();
                }

                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"ERROR: {ex.Message}");
                return 1;
            }
        }
    }
}
