import sys, pymupdf
from pathlib import Path
pdf = pymupdf.open(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(exist_ok=True)
# hojas de contacto: 6 páginas por imagen (3x2)
paginas = list(range(len(pdf)))
for s in range(0, len(paginas), 6):
    grupo = paginas[s:s+6]
    W, H = 612*0.55, 792*0.55
    hoja = pymupdf.open(); pg = hoja.new_page(width=W*3, height=H*2)
    for k, i in enumerate(grupo):
        r = pymupdf.Rect((k%3)*W, (k//3)*H, (k%3+1)*W, (k//3+1)*H)
        pg.show_pdf_page(r, pdf, i)
        pg.draw_rect(r, color=(0.7,0.7,0.7), width=0.5)
        pg.insert_text((r.x0+4, r.y0+10), f"p{i+1}", fontsize=8, color=(1,0,0))
    pg.get_pixmap(dpi=110).save(out / f"hoja_{s//6+1:02d}.png")
print("ok", len(pdf))
