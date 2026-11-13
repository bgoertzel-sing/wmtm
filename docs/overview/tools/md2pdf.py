"""Minimal Markdown -> PDF for WMTM_OVERVIEW.md (headings, paragraphs, nested bullets, numbered lists, tables).
Usage: PYTHONPATH=<reportlab dir> python3 md2pdf.py IN.md OUT.pdf"""
import re, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", D + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", D + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVI", D + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVM", D + "DejaVuSansMono.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")
base = ParagraphStyle("b", fontName="DV", fontSize=9.5, leading=13, spaceAfter=4)
H = {1: ParagraphStyle("h1", parent=base, fontName="DVB", fontSize=16, leading=20, spaceAfter=8),
     2: ParagraphStyle("h2", parent=base, fontName="DVB", fontSize=13, leading=17, spaceBefore=10, spaceAfter=6),
     3: ParagraphStyle("h3", parent=base, fontName="DVB", fontSize=11, leading=14, spaceBefore=8, spaceAfter=4)}
cell = ParagraphStyle("c", parent=base, fontSize=8, leading=10, spaceAfter=0)
def inline(t):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    codes = []
    def keep(m):
        codes.append(m.group(1)); return "\x00%d\x00" % (len(codes) - 1)
    t = re.sub(r"`([^`]+)`", keep, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub("\x00(\\d+)\x00", lambda m: '<font name="DVM">%s</font>' % codes[int(m.group(1))], t)
    return t
lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
out, i, para = [], 0, []
def flush():
    if para: out.append(Paragraph(inline(" ".join(para)), base)); para.clear()
item_re = re.compile(r"^(\s*)(- |\d+\. )(.*)$")
while i < len(lines):
    l = lines[i]
    m = re.match(r"^(#{1,3}) (.*)$", l)
    if m: flush(); out.append(Paragraph(inline(m.group(2)), H[len(m.group(1))])); i += 1; continue
    if l.startswith("|"):
        flush(); rows = []
        while i < len(lines) and lines[i].startswith("|"):
            r = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-+:?", c) for c in r): rows.append(r)
            i += 1
        n = max(len(r) for r in rows); W = 17.0 * cm
        data = [[Paragraph(("<b>%s</b>" if k == 0 else "%s") % inline(c), cell) for c in r + [""] * (n - len(r))] for k, r in enumerate(rows)]
        t = Table(data, colWidths=[W / n] * n, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        out += [t, Spacer(1, 6)]; continue
    m = item_re.match(l)
    if m:
        flush(); ind, mark, txt = len(m.group(1)), m.group(2), [m.group(3)]; i += 1
        while i < len(lines) and lines[i].strip() and not item_re.match(lines[i]) and not lines[i].startswith(("#", "|")) and lines[i].startswith(" "):
            txt.append(lines[i].strip()); i += 1
        lvl = ind // 2
        st = ParagraphStyle("li", parent=base, leftIndent=14 + 14 * lvl, bulletIndent=4 + 14 * lvl, spaceAfter=2)
        out.append(Paragraph(inline(" ".join(txt)), st, bulletText="•" if mark == "- " else mark.strip())); continue
    if not l.strip(): flush(); i += 1; continue
    para.append(l.strip()); i += 1
flush()
def foot(c, d):
    c.saveState(); c.setFont("DV", 8); c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, "WMTM overview - page %d" % d.page); c.restoreState()
doc = SimpleDocTemplate(sys.argv[2], pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                        title="WMTM overview", author="ProtomegaTron")
doc.build(out, onFirstPage=foot, onLaterPages=foot)
print("pages", doc.page)
