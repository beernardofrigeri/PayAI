import cv2
import numpy as np
from PIL import Image, ImageDraw


def cv2_para_pil(frame):
    # -- Compatibilidade com o módulo draw: converte BGR->RGB:
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


def pil_para_cv2(img):
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def rect_r(draw, x1, y1, x2, y2, r, fill=None, outline=None, width=1):
    if fill:
        draw.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=fill)
    if outline:
        draw.rounded_rectangle([x1, y1, x2, y2], radius=r, outline=outline, width=width)


def texto_c(draw, texto, cx, y, fonte, cor):
    w = fonte.getlength(texto)
    draw.text((cx - w / 2, y), texto, font=fonte, fill=cor)


def desenhar_contornos(draw, contornos_snapshot, fontes, cores):
    for (top_left, bottom_right), texto, _, tipo in contornos_snapshot:
        alpha = 255 if tipo in ('VALOR', 'QRCODE') else 220
        cor = cores['ACENTO'] if tipo == 'QRCODE' else cores['AMARELO']

        draw.rectangle([top_left, bottom_right], outline=(*cor, alpha), width=2)
        tx = top_left[0]
        ty = max(top_left[1] - 22, 44)
        bw = int(fontes['contorno'].getlength(texto)) + 12
        rect_r(draw, tx, ty, tx + bw, ty + 18, r=3, fill=(*cor, min(alpha, 210)))

        draw.text(
            (tx + 6, ty + 3),
            texto,
            font=fontes['contorno'],
            fill=cores['PRETO'],
        )


def desenhar_interface(
    frame,
    estatisticas,
    agora,
    *,
    fontes,
    cores,
    idiomas,
    fps_atual,
    modo_atual,
    idioma_atual,
    tempo_ocr,
    regioes_detectadas,
    contornos_snapshot,
):
    img = cv2_para_pil(frame)
    draw = ImageDraw.Draw(img)
    W, H = img.size

    # -- Header:
    draw.rectangle([0, 0, W, 42], fill=cores['BG'])
    draw.line(
        [(0, 42), (W, 42)],
        fill=cores['BORDA'],
        width=1,
    )

    # -- Logo:
    lp = int(fontes['logo_pay'].getlength('PAY'))
    draw.text((14, 11), 'PAY', font=fontes['logo_pay'], fill=cores['ACENTO'])
    draw.text((14 + lp + 4, 11), 'AI', font=fontes['logo_ai'], fill=cores['TEXTO_PRIM'])

    # -- Separador vertical:
    draw.line(
        [(14 + lp + 4 + 26, 13), (14 + lp + 4 + 26, 30)],
        fill=cores['BORDA'],
        width=1,
    )

    # -- Subtitulo:
    draw.text(
        (14 + lp + 4 + 33, 14),
        'Sistema Inteligente',
        font=fontes['subtitulo'],
        fill=cores['TEXTO_SEC'],
    )

    # -- Modo e idioma --
    modos_cfg = {
        0: ('AUTO', cores['ACENTO']),
        1: ('VALORES', cores['AMARELO']),
        2: ('QR CODE', cores['AZUL']),
    }

    # -- Obter rótulo e cor do modo atual --
    modo_label, cor_modo = modos_cfg.get(
        modo_atual,
        ('AUTO', cores['ACENTO']),
    )

    # -- Obter rótulo do idioma atual --
    idioma_label = 'PT-BR' if idioma_atual == idiomas['PT_BR'] else 'ES-CO'

    # -- Bagde Modo --
    modo_x1 = W - 235
    modo_y1 = 8
    modo_x2 = W - 145
    modo_y2 = 32

    # -- Desenhar retângulo arredondado para o modo --
    rect_r(
        draw,
        modo_x1,
        modo_y1,
        modo_x2,
        modo_y2,
        r=6,
        fill=cores['CARD_BG'],
        outline=cor_modo,
        width=1,
    )

    # -- Desenhar o texto do modo centralizado --
    texto_c(
        draw,
        modo_label,
        (modo_x1 + modo_x2) // 2,
        modo_y1 + 5,
        fontes['modo'],
        cor_modo,
    )

    # -- Bagde Idioma --
    idioma_x1 = W - 135
    idioma_y1 = 8
    idioma_x2 = W - 20
    idioma_y2 = 32

    # -- Desenhar retângulo arredondado para o idioma --
    rect_r(
        draw,
        idioma_x1,
        idioma_y1,
        idioma_x2,
        idioma_y2,
        r=6,
        fill=cores['CARD_BG'],
        outline=cores['AZUL'],
        width=1,
    )

    # -- Desenhar o texto do idioma centralizado --
    texto_c(
        draw,
        idioma_label,
        (idioma_x1 + idioma_x2) // 2,
        idioma_y1 + 5,
        fontes['badge'],
        cores['TEXTO_PRIM'],
    )

    # -- Estatísticas --
    if estatisticas:
        stats = estatisticas.obter_estatisticas()
        itens = [
            ('Valores', str(stats['valores_detectados'])),
            ('QR Codes', str(stats['qrcodes_detectados'])),
            ('Taxa', f"{stats['detectoes_por_minuto']:.1f}/min"),
            ('FPS', f'{fps_atual:.1f}'),
            ('OCR', f'{tempo_ocr:.0f}ms'),
            ('Regioes', str(regioes_detectadas)),
        ]
        sy = 50
        for label, valor in itens:

            # Desenhar rótulo à esquerda:
            draw.text(
                (14, sy),
                f'{label}:',
                font=fontes['pequena'],
                fill=cores['TEXTO_SEC'],
            )
            lw = int(fontes['pequena'].getlength(f'{label}:')) + 6

            # Desenhar valor à direita do rótulo:
            draw.text(
                (14 + lw, sy),
                valor,
                font=fontes['corpo_b'],
                fill=cores['TEXTO_PRIM'],
            )
            sy += 16

    # -- Contornos ativos (valores e QR Codes) --
    desenhar_contornos(draw, contornos_snapshot, fontes, cores)

    # -- Footer com botões de atalho --
    footer_y = H - 72

    # -- Desenhar retângulo de fundo do footer:
    draw.rectangle([0, footer_y, W, H], fill=cores['BG'])

    draw.line(
        [(0, footer_y), (W, footer_y)],
        fill=cores['BORDA'],
        width=1,
    )

    # -- Botões de atalho:
    botoes = [
        ('ESC', 'SAIR'),
        ('V', 'VALORES'),
        ('Q', 'QR CODE'),
        ('A', 'AUTO'),
        ('I', 'IDIOMA'),
        ('R', 'REPETIR'),
        ('S', 'PRINT'),
    ]

    # -- Calcular largura total dos botões e posição inicial para centralizar:
    card_w = 72
    gap = 4
    total_w = len(botoes) * card_w + (len(botoes) - 1) * gap
    bx_ini = (W - total_w) // 2

    for i, (tecla, desc) in enumerate(botoes):

        # -- Calcular posição do botão:
        cx1 = bx_ini + i * (card_w + gap)
        cx2 = cx1 + card_w
        cy1 = footer_y + 8
        cy2 = H - 8

        # -- Determinar se o botão está ativo (modo atual):
        ativo = (
            (tecla == 'A' and modo_atual == 0) or
            (tecla == 'V' and modo_atual == 1) or
            (tecla == 'Q' and modo_atual == 2)
        )

        cor_fill = cores['ACENTO_DIM'] if ativo else cores['CARD_BG']
        cor_borda = cores['ACENTO'] if ativo else cores['BORDA']

        rect_r(
            draw,
            cx1,
            cy1,
            cx2,
            cy2,
            r=6,
            fill=cor_fill,
            outline=cor_borda,
            width=1,
        )

        # -- Tecla:
        tw = fontes['hotkey'].getlength(tecla)

        # -- Desenhar a tecla centralizada no botão:
        draw.text(
            (cx1 + (card_w - tw) / 2, cy1 + 5),
            tecla,
            font=fontes['hotkey'],
            fill=cores['ACENTO'] if ativo else cores['TEXTO_PRIM'],
        )

        # -- Label
        dw = fontes['hotlabel'].getlength(desc)

        # -- Desenhar a descrição centralizada abaixo da tecla:
        draw.text(
            (cx1 + (card_w - dw) / 2, cy2 - 17),
            desc,
            font=fontes['hotlabel'],
            fill=cores['ACENTO'] if ativo else cores['TEXTO_SEC'],
        )

    # -- Retornar a imagem final como array OpenCV:
    return pil_para_cv2(img)

