from flask import Blueprint, render_template, jsonify, session, redirect, url_for, send_file, make_response
import json
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.platypus.flowables import PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend
import io

report_bp = Blueprint('report', __name__)

def get_report_data():
    """Carrega os dados do relatório"""
    try:
        arquivo_contadores = "contadores.json"
        
        if os.path.exists(arquivo_contadores):
            with open(arquivo_contadores, 'r') as file:
                dados = json.load(file)
        else:
            dados = {
                "total_hd_encontrado": 0,
                "total_matriculas_encontradas": 0,
                "total_hd_nao_encontrado": 0,
                "total_mensagens_invalidas": 0,
                "total_respostas_link": 0,
                "total_matriculas_nao_encontrada": 0,
                "total_mesagens_respondidas": 0,
                "ultima_data": str(datetime.now().date())
            }
        
        # Gerar relatório
        total_geral = (
            dados.get("total_hd_encontrado", 0) +
            dados.get("total_matriculas_encontradas", 0) +
            dados.get("total_hd_nao_encontrado", 0) +
            dados.get("total_matriculas_nao_encontrada", 0) +
            dados.get("total_mensagens_invalidas", 0) +
            dados.get("total_respostas_link", 0)
        )

        report_data = {
            'hd_encontrado': dados.get("total_hd_encontrado", 0),
            'matriculas_encontradas': dados.get("total_matriculas_encontradas", 0),
            'hd_nao_encontrado': dados.get("total_hd_nao_encontrado", 0),
            'matriculas_nao_encontradas': dados.get("total_matriculas_nao_encontrada", 0),
            'mensagens_invalidas': dados.get("total_mensagens_invalidas", 0),
            'respostas_link': dados.get("total_respostas_link", 0),
            'mensagens_respondidas': dados.get("total_mesagens_respondidas", 0),
            'total_geral': total_geral,
            'ultima_data': dados.get("ultima_data", "N/A")
        }
        
        return report_data, None
        
    except Exception as e:
        return None, str(e)

@report_bp.route('/')
def report():
    report_data, error = get_report_data()
    
    if error:
        return render_template('report.html', error=error)
    else:
        return render_template('report.html', report=report_data)

@report_bp.route('/data')
def report_data():
    try:
        arquivo_contadores = "contadores.json"
        
        if os.path.exists(arquivo_contadores):
            with open(arquivo_contadores, 'r') as file:
                dados = json.load(file)
        else:
            dados = {}
        
        return jsonify(dados)
        
    except Exception as e:
        return jsonify({'error': str(e)})

@report_bp.route('/download-pdf')
def download_pdf():
    """Gera e baixa o relatório em PDF"""
    try:
        report_data, error = get_report_data()
        
        if error:
            return jsonify({'error': error}), 500
        
        # Criar buffer para o PDF
        buffer = io.BytesIO()
        
        # Configurar documento PDF
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2c3e50')
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.HexColor('#34495e')
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=6
        )
        
        # Conteúdo do PDF
        story = []
        
        # Título
        story.append(Paragraph("Relatório VCGA - Sistema WhatsApp Bot", title_style))
        story.append(Spacer(1, 20))
        
        # Data de geração
        data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        story.append(Paragraph(f"<b>Relatório gerado em:</b> {data_geracao}", normal_style))
        story.append(Spacer(1, 20))
        
        # Resumo Geral
        story.append(Paragraph("Resumo Geral", heading_style))
        
        resumo_data = [
            ['Métrica', 'Valor'],
            ['Consultas Bem-sucedidas', str(report_data['hd_encontrado'] + report_data['matriculas_encontradas'])],
            ['Não Encontrados', str(report_data['hd_nao_encontrado'] + report_data['matriculas_nao_encontradas'])],
            ['Links Enviados', str(report_data['respostas_link'])],
            ['Total de Respostas', str(report_data['mensagens_respondidas'])],
        ]
        
        resumo_table = Table(resumo_data, colWidths=[3*inch, 2*inch])
        resumo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        story.append(resumo_table)
        story.append(Spacer(1, 30))
        
        # Detalhes por Categoria
        story.append(Paragraph("Detalhes por Categoria", heading_style))
        
        detalhes_data = [
            ['Categoria', 'Quantidade'],
            ['HDs Encontrados', str(report_data['hd_encontrado'])],
            ['Matrículas Encontradas', str(report_data['matriculas_encontradas'])],
            ['HDs Não Encontrados', str(report_data['hd_nao_encontrado'])],
            ['Matrículas Não Encontradas', str(report_data['matriculas_nao_encontradas'])],
            ['Mensagens Inválidas', str(report_data['mensagens_invalidas'])],
            ['Respostas de Link', str(report_data['respostas_link'])],
        ]
        
        detalhes_table = Table(detalhes_data, colWidths=[3*inch, 2*inch])
        detalhes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        story.append(detalhes_table)
        story.append(Spacer(1, 30))
        
        # Informações Adicionais
        story.append(Paragraph("Informações Adicionais", heading_style))
        
        taxa_sucesso = 0
        if report_data['total_geral'] > 0:
            taxa_sucesso = (report_data['hd_encontrado'] + report_data['matriculas_encontradas']) / report_data['total_geral'] * 100
        
        info_data = [
            ['Informação', 'Valor'],
            ['Última Atualização', str(report_data['ultima_data'])],
            ['Total de Interações', str(report_data['total_geral'])],
            ['Taxa de Sucesso', f"{taxa_sucesso:.1f}%"],
            ['Mensagens Respondidas', str(report_data['mensagens_respondidas'])],
        ]
        
        info_table = Table(info_data, colWidths=[3*inch, 2*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 30))
        
        # Rodapé
        story.append(Spacer(1, 50))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.grey
        )
        story.append(Paragraph("Sistema VCGA - WhatsApp Bot Administrativo", footer_style))
        story.append(Paragraph("Desenvolvido por Alisson Cardozo Varela", footer_style))
        
        # Construir PDF
        doc.build(story)
        
        # Preparar resposta
        buffer.seek(0)
        
        filename = f"relatorio_vcga_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        buffer.close()
        
        return response
        
    except Exception as e:
        return jsonify({'error': f'Erro ao gerar PDF: {str(e)}'}), 500
