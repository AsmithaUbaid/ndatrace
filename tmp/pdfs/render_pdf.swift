import AppKit
import PDFKit

let args = CommandLine.arguments
guard args.count == 3 else {
    fputs("usage: render_pdf input.pdf output-dir\n", stderr)
    exit(2)
}

let input = URL(fileURLWithPath: args[1])
let output = URL(fileURLWithPath: args[2], isDirectory: true)
guard let document = PDFDocument(url: input) else {
    fputs("cannot open PDF\n", stderr)
    exit(1)
}

try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
print("pages \(document.pageCount)")

for index in 0..<document.pageCount {
    guard let page = document.page(at: index) else { continue }
    let text = page.string ?? ""
    if text.localizedCaseInsensitiveContains("Table 4") ||
       text.localizedCaseInsensitiveContains("Stage 1") ||
       text.localizedCaseInsensitiveContains("Stage 5") ||
       text.localizedCaseInsensitiveContains("Table 5") {
        print("marker page \(index + 1): \(text.prefix(100).replacingOccurrences(of: "\n", with: " | "))")
    }
    let bounds = page.bounds(for: .mediaBox)
    let scale: CGFloat = 2.0
    let width = Int(bounds.width * scale)
    let height = Int(bounds.height * scale)
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: width,
        pixelsHigh: height,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ) else { continue }
    NSGraphicsContext.saveGraphicsState()
    guard let context = NSGraphicsContext(bitmapImageRep: bitmap) else { continue }
    NSGraphicsContext.current = context
    context.cgContext.setFillColor(NSColor.white.cgColor)
    context.cgContext.fill(CGRect(x: 0, y: 0, width: width, height: height))
    context.cgContext.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: context.cgContext)
    NSGraphicsContext.restoreGraphicsState()
    if let data = bitmap.representation(using: .png, properties: [:]) {
        try data.write(to: output.appendingPathComponent(String(format: "page-%02d.png", index + 1)))
    }
}
