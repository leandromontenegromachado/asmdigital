from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer


def main() -> None:
    path = Path("README.md")
    try:
        readme = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        readme = path.read_text(encoding="cp1252")
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    heading = styles["Heading2"]
    code_style = styles["Code"]

    story = []
    lines = readme.splitlines()
    code_block = False
    code_lines: list[str] = []

    for line in lines:
        if line.strip().startswith("```"):
            if not code_block:
                code_block = True
                code_lines = []
            else:
                code_block = False
                story.append(Preformatted("\n".join(code_lines), code_style))
                story.append(Spacer(1, 8))
            continue

        if code_block:
            code_lines.append(line)
            continue

        if line.startswith("# "):
            story.append(Paragraph(line[2:].strip(), styles["Title"]))
            story.append(Spacer(1, 8))
            continue
        if line.startswith("## "):
            story.append(Paragraph(line[3:].strip(), heading))
            story.append(Spacer(1, 6))
            continue
        if not line.strip():
            story.append(Spacer(1, 6))
            continue

        if line.lstrip().startswith("- "):
            text = "&bull; " + line.lstrip()[2:].strip()
        else:
            text = line

        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(text, normal))

    output = Path("README.pdf")
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    doc.build(story)
    print(str(output))


if __name__ == "__main__":
    main()
