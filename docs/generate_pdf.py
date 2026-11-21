"""
FrontierAtlas Data Intelligence Pipeline
Architecture Document PDF Generator
Compiles architecture.md into a high-fidelity, production-grade PDF using ReportLab.
"""

import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Adds running headers and 'Page X of Y' footers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))

        # Header
        self.drawString(54, letter[1] - 36, "FrontierAtlas Data Intelligence Pipeline | Architecture & Production Design")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Footer
        self.drawString(54, 36, "CONFIDENTIAL & PROPRIETARY — GraphOne / FrontierAtlas Assessment")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 36, page_str)
        self.line(54, 46, letter[0] - 54, 46)
        self.restoreState()

def build_pdf(md_path: str, output_pdf_path: str):
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A202C"),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=14
    )

    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=12,
        spaceAfter=6
    )

    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#2D3748"),
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#2D3748"),
        leftIndent=14,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'CodeBlock',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#1A202C"),
        backColor=colors.HexColor("#EDF2F7"),
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=6
    )

    story = []

    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Document Header
    story.append(Paragraph("Technical Architecture & Production Design", title_style))
    story.append(Paragraph("<b>FrontierAtlas Global Intelligence Graph Ingestion Engine</b> | Target Scale: 500,000+ Multi-Dimensional Entities", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=10))

    in_code_block = False
    code_lines = []

    def clean_xml(text: str) -> str:
        # Protect intentional <b> tags
        text = text.replace("<b>", "___B_OPEN___").replace("</b>", "___B_CLOSE___")
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace("___B_OPEN___", "<b>").replace("___B_CLOSE___", "</b>")
        return text

    for line in lines:
        raw_line = line.strip()

        # Handle Code blocks
        if raw_line.startswith("```"):
            if in_code_block:
                code_text = "<br/>".join([c.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace(' ', '&nbsp;') for c in code_lines])
                story.append(Paragraph(code_text, code_style))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line.rstrip("\r\n"))
            continue

        if not raw_line:
            continue

        # Skip main markdown title as we already formatted it
        if raw_line.startswith("# Technical Architecture"):
            continue
        if raw_line.startswith("**FrontierAtlas"):
            continue
        if raw_line.startswith("*Document Version"):
            continue
        if raw_line == "---":
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceAfter=6, spaceBefore=4))
            continue

        # Headings
        if raw_line.startswith("## "):
            story.append(Paragraph(clean_xml(raw_line[3:]), h1_style))
        elif raw_line.startswith("### "):
            story.append(Paragraph(clean_xml(raw_line[4:]), h2_style))
        elif raw_line.startswith("- ") or raw_line.startswith("* "):
            formatted_bullet = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', raw_line[2:])
            story.append(Paragraph(f"• {clean_xml(formatted_bullet)}", bullet_style))
        elif raw_line.startswith("1. ") or raw_line.startswith("2. ") or raw_line.startswith("3. ") or raw_line.startswith("4. "):
            formatted_num = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', raw_line)
            story.append(Paragraph(clean_xml(formatted_num), bullet_style))
        elif raw_line.startswith("|"):
            continue
        else:
            formatted_body = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', raw_line)
            story.append(Paragraph(clean_xml(formatted_body), body_style))

    # Add Storage Table explicitly
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Table 1: Storage Layer Architecture Justification</b>", h2_style))
    table_data = [
        ["Storage Tier", "Technology", "Workload & Architectural Justification"],
        ["Primary Relational", "PostgreSQL / TiDB", "ACID System of Record: Stores core entity metadata, source provenance URLs, and audit logs. TiDB scales horizontally for 500k+ records."],
        ["Intelligence Graph", "Neo4j / Amazon Neptune", "Deep Relationship Traversal: Models multi-hop links (Startup -> Product -> Paper -> GitHub) with O(1) pointer-chasing performance."],
        ["Semantic Vector", "Qdrant / Milvus", "Vector Embeddings: Dense 1536-dim embeddings for paper abstracts, product features, and startup descriptions enabling semantic dedup."]
    ]
    t = Table(table_data, colWidths=[110, 110, 284])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2B6CB0")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 4),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#F7FAFC")),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor("#2D3748")),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF: {output_pdf_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    md_file = os.path.join(base_dir, "architecture.md")
    pdf_file = os.path.join(base_dir, "architecture.pdf")
    build_pdf(md_file, pdf_file)
