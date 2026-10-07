import argparse
import os
from PIL import Image

def png_to_pdf_with_dpi(input_path, output_path, dpi=300, target_width=None, target_height=None):
    """
    Convert PNG -> PDF with specified DPI, with optional scaling to target pixel size.
    """
    # open PNG image
    img = Image.open(input_path)
    print(f"🖼️  Opened {input_path} ({img.width}x{img.height} px, mode={img.mode})")

    # convert to RGB if image has alpha channel
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    else:
        img = img.convert("RGB")

    # scale image if requested
    if target_width or target_height:
        # if only one dimension is set, preserve aspect ratio
        if target_width and not target_height:
            ratio = target_width / img.width
            target_height = int(img.height * ratio)
        elif target_height and not target_width:
            ratio = target_height / img.height
            target_width = int(img.width * ratio)

        img = img.resize((target_width, target_height), Image.LANCZOS)

    # save to PDF with DPI metadata
    img.save(output_path, "PDF", resolution=dpi)
    print(f"✅ Saved {output_path} ({img.width}x{img.height} px at {dpi} DPI)")


def main():
    parser = argparse.ArgumentParser(
        description="Convert PNG to PDF with 300 DPI and optional scaling."
    )
    parser.add_argument("input", help="Input PNG file")
    parser.add_argument("output", help="Output PDF file")
    parser.add_argument("--workdir", help="Working directory", default="")
    parser.add_argument("--dpi", type=int, default=300, help="Target DPI (default: 300)")
    parser.add_argument("--width", type=int, help="Target width in pixels")
    parser.add_argument("--height", type=int, help="Target height in pixels")

    args = parser.parse_args()

    png_to_pdf_with_dpi(
        os.path.join(args.workdir, args.input),
        os.path.join(args.workdir, args.output),
        dpi=args.dpi,
        target_width=args.width,
        target_height=args.height,
    )


if __name__ == "__main__":
    main()
