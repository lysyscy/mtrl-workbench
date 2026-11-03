"""Synthetic PDFs only; generated in memory, never based on business originals."""
from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject, TextStringObject

CARD = '1000111400012345678'
NUMBER = '20261031000000000001'


def invoice_pdf(*, number=NUMBER, card=CARD, amount='3000.00', subtotal='2654.87', tax='345.13', variant='', bank='4100501111000000469', buyer='合成测试购买方'):
    lines = ['电子发票（增值税专用发票）', '成品油', f'发票号码：{number}', '开票日期：2026年10月31日',
        f'购买方名称：{buyer}', '销售方名称：中国石化销售股份有限公司合成测试分公司', '项目名称 柴油', f'合 计 ¥{subtotal} ¥{tax}',
        '价税合计（大写） 合成金额', f'（小写）¥{amount}', '备 注', f'销方开户银行：合成测试银行；银行账号：{bank}；', card]
    writer = PdfWriter()
    if variant:
        writer.add_metadata({'/Subject': variant})
    page = writer.add_blank_page(width=595, height=842)
    descendant = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/CIDFontType0'),
        NameObject('/BaseFont'): NameObject('/STSong-Light'), NameObject('/DW'): NumberObject(1000),
        NameObject('/CIDSystemInfo'): DictionaryObject({NameObject('/Registry'): TextStringObject('Adobe'), NameObject('/Ordering'): TextStringObject('GB1'), NameObject('/Supplement'): NumberObject(4)})})
    cmap = DecodedStreamObject()
    cmap.set_data(b'/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def /CMapName /Identity-UCS def /CMapType 2 def 1 begincodespacerange <0000> <FFFF> endcodespacerange 1 beginbfrange <0000> <FFFF> <0000> endbfrange endcmap CMapName currentdict /CMap defineresource pop end end')
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type0'),
        NameObject('/BaseFont'): NameObject('/STSong-Light'), NameObject('/Encoding'): NameObject('/UniGB-UCS2-H'),
        NameObject('/DescendantFonts'): ArrayObject([writer._add_object(descendant)]), NameObject('/ToUnicode'): writer._add_object(cmap)})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    commands = ['BT /F1 11 Tf 38 795 Td 22 TL']
    for line in lines:
        commands.extend([f'<{line.encode("utf-16-be").hex()}> Tj', 'T*'])
    stream.set_data(('\n'.join(commands) + '\nET').encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO(); writer.write(output)
    return output.getvalue()
