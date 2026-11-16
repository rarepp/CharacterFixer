import os
import pymupdf as pdmf  # PyMuPDF

STRETCH = 0.4
MAX_SCALE = 1.3  # max stretch


def fix_romanian_pdf_fonts(input_pdf: str, output_pdf: str, font_dir: str = r"C:\Windows\Fonts"):
    doc = pdmf.open(input_pdf)

    char_map = {"ş": "ș", "Ş": "Ș", "ţ": "ț", "Ţ": "Ț"}
    targets = set(char_map) | set("șȘțȚ")

    font_variants = {
        (False, False): ("TNR_Reg", os.path.join(font_dir, "times.ttf")),
        (True, False): ("TNR_Bold", os.path.join(font_dir, "timesbd.ttf")),
        (False, True): ("TNR_Ital", os.path.join(font_dir, "timesi.ttf")),
        (True, True): ("TNR_BI", os.path.join(font_dir, "timesbi.ttf")),
    }
    font_cache = {}

    def get_font(style):
        name, path = font_variants[style]
        if not os.path.exists(path):
            name, path = font_variants[(False, False)]
        if path not in font_cache:
            font_cache[path] = pdmf.Font(fontfile=path)
        return name, path, font_cache[path]

    for page in doc:
        raw = page.get_text("rawdict")
        items = []

        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    flags = span.get("flags", 0)
                    fname = span.get("font", "").lower()
                    style = (
                        bool(flags & 16) or "bold" in fname,
                        bool(flags & 2) or "italic" in fname or "oblique" in fname,
                    )
                    size = span["size"]

                    for ch in span.get("chars", []):
                        c = ch["c"]
                        if c not in targets:
                            continue
                        bbox = pdmf.Rect(ch["bbox"])
                        items.append({
                            "bbox": bbox,
                            "origin": pdmf.Point(ch["origin"]),
                            "old_w": bbox.width,
                            "text": char_map.get(c, c),
                            "size": size,
                            "color": pdmf.sRGB_to_pdf(span["color"]),
                            "style": style,
                        })

        for it in items:
            r = it["bbox"]
            dx = r.width * 0.25
            dy = r.height * 0.15
            page.add_redact_annot(
                pdmf.Rect(r.x0 + dx, r.y0 + dy, r.x1 - dx, r.y1 - dy),
                fill=False,
            )

        if items:
            page.apply_redactions(
                images=pdmf.PDF_REDACT_IMAGE_NONE,
                graphics=pdmf.PDF_REDACT_LINE_ART_NONE,
            )

        for it in items:
            name, path, font = get_font(it["style"])
            new_w = font.text_length(it["text"], fontsize=it["size"])

            sx = 1 + STRETCH * (it["old_w"] / new_w - 1) if new_w else 1
            sx = max(1.0, min(MAX_SCALE, sx))
            final_w = new_w * sx

            x = it["origin"].x + (it["old_w"] - final_w) / 2
            pos = pdmf.Point(x, it["origin"].y)

            page.insert_text(
                pos,
                it["text"],
                fontname=name,
                fontfile=path,
                fontsize=it["size"],
                color=it["color"],
                morph=(pos, pdmf.Matrix(sx, 1)),
            )

    doc.subset_fonts()
    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()
    print(f"Saved fixed PDF to: {output_pdf}")


if __name__ == "__main__":
    fix_romanian_pdf_fonts("input.pdf", "output_fixed.pdf")