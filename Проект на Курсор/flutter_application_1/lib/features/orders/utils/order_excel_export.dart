import 'package:excel/excel.dart';
import 'package:file_saver/file_saver.dart';
import 'package:flutter/foundation.dart';
import 'package:intl/intl.dart';

import '../../../core/domain/models/order.dart';

/// Собирает `.xlsx` с текущим (отфильтрованным) списком заказов и отдаёт в диалог «Сохранить» / загрузку.
class OrderExcelExport {
  static Future<void> saveToFile(
    List<Order> orders, {
    required String periodLabel,
  }) async {
    if (orders.isEmpty) {
      throw ArgumentError('Список заказов пуст');
    }
    final excel = Excel.createExcel();
    excel.rename('Sheet1', 'Заказы');
    final sheet = excel['Заказы'];
    final dateFmt = DateFormat('dd.MM.yyyy HH:mm');
    sheet.appendRow([TextCellValue('Период: $periodLabel')]);
    sheet.appendRow([
      TextCellValue('№'),
      TextCellValue('Код'),
      TextCellValue('Дата и время'),
      TextCellValue('Статус'),
      TextCellValue('Сумма'),
      TextCellValue('Валюта'),
      TextCellValue('Доставка'),
      TextCellValue('Оплата'),
      TextCellValue('Адрес'),
      TextCellValue('Позиций'),
      TextCellValue('Состав (кратко)'),
    ]);
    for (var i = 0; i < orders.length; i++) {
      final o = orders[i];
      final count = o.items.fold<int>(0, (s, e) => s + e.quantity);
      final linePreview = o.items.map((e) {
        final v = (e.variantLabel != null && e.variantLabel!.isNotEmpty)
            ? ' (${e.variantLabel})'
            : '';
        return '${e.title}$v × ${e.quantity}';
      }).join('; ');
      sheet.appendRow([
        IntCellValue(i + 1),
        TextCellValue('GM-${o.number}'),
        TextCellValue(dateFmt.format(o.createdAt)),
        TextCellValue(o.status.labelRu),
        DoubleCellValue(o.total),
        TextCellValue(o.currency),
        TextCellValue(o.deliveryMethod ?? '—'),
        TextCellValue(o.paymentMethod ?? '—'),
        TextCellValue(
          (o.addressLine != null && o.addressLine!.trim().isNotEmpty) ? o.addressLine! : '—',
        ),
        IntCellValue(count),
        TextCellValue(linePreview),
      ]);
    }
    final encoded = excel.encode();
    if (encoded == null) {
      throw StateError('Не удалось сформировать файл Excel');
    }
    final stamp = DateFormat('yyyyMMdd_HHmmss').format(DateTime.now());
    await FileSaver.instance.saveFile(
      name: 'zakazy_$stamp',
      bytes: Uint8List.fromList(encoded),
      fileExtension: 'xlsx',
      mimeType: MimeType.microsoftExcel,
    );
  }
}
