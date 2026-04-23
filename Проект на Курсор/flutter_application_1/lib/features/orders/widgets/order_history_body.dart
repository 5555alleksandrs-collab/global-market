import 'package:collection/collection.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';

import '../../../application/providers.dart';
import '../../../common/widgets/app_states.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_spacing.dart';
import '../../../core/domain/models/cart_item.dart';
import '../../../core/domain/models/order.dart';
import '../utils/order_excel_export.dart';

/// Фильтр по периоду (отсечка от «сейчас» назад).
enum OrderHistoryFilter {
  all,
  days7,
  days30,
  days90,
}

extension on OrderHistoryFilter {
  String get label {
    switch (this) {
      case OrderHistoryFilter.all:
        return 'Все';
      case OrderHistoryFilter.days7:
        return '7 дней';
      case OrderHistoryFilter.days30:
        return '30 дней';
      case OrderHistoryFilter.days90:
        return '90 дней';
    }
  }
}

List<Order> _applyFilter(List<Order> orders, OrderHistoryFilter f) {
  if (f == OrderHistoryFilter.all) return orders;
  final now = DateTime.now();
  final d = switch (f) {
    OrderHistoryFilter.days7 => 7,
    OrderHistoryFilter.days30 => 30,
    OrderHistoryFilter.days90 => 90,
    OrderHistoryFilter.all => 0,
  };
  final from = now.subtract(Duration(days: d));
  return orders.where((o) => o.createdAt.isAfter(from)).toList();
}

/// Список заказов по дням, с группами по месяцу и фильтром по периоду.
class OrderHistoryBody extends ConsumerStatefulWidget {
  const OrderHistoryBody({
    super.key,
    this.padding = const EdgeInsets.all(AppSpacing.md),
    this.topSliverOverlap = 0,
    this.showDocumentsHeader = true,
  });

  final EdgeInsets padding;
  final double topSliverOverlap;

  /// Заголовок «Документы» + иконки (как в референсе). На отдельном экране «Мои заказы» лучше `false`.
  final bool showDocumentsHeader;

  @override
  ConsumerState<OrderHistoryBody> createState() => _OrderHistoryBodyState();
}

class _OrderHistoryBodyState extends ConsumerState<OrderHistoryBody> {
  OrderHistoryFilter _filter = OrderHistoryFilter.all;
  bool _exportingExcel = false;

  @override
  Widget build(BuildContext context) {
    final allOrders = ref.watch(ordersProvider);
    final orders = _applyFilter(allOrders, _filter);
    orders.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    if (allOrders.isEmpty) {
      return const AppEmptyState(
        title: 'Заказов пока нет',
        subtitle: 'Оформите заказ из корзины — он появится здесь, сгруппированный по дням и месяцам.',
        icon: Icons.receipt_long_outlined,
      );
    }
    if (orders.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Text(
            'В выбранном периоде заказов нет',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
      );
    }

    final byDay = groupBy<Order, DateTime>(
      orders,
      (o) => DateTime(o.createdAt.year, o.createdAt.month, o.createdAt.day),
    );
    final days = byDay.keys.toList()..sort((a, b) => b.compareTo(a));
    final now = DateTime.now();
    final money = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);
    final totalSum = orders.fold<double>(0, (s, o) => s + o.total);

    return RefreshIndicator(
      color: AppColors.accent,
      onRefresh: () async {
        ref.read(ordersProvider.notifier).reloadFromPrefs();
        await Future<void>.delayed(const Duration(milliseconds: 200));
      },
      child: ListView(
        padding: widget.padding.copyWith(top: widget.padding.top + widget.topSliverOverlap),
        children: [
          if (widget.showDocumentsHeader) ...[
            _HistoryToolbar(
              onOpenPeriod: () => _showPeriodSheet(context),
            ),
            const SizedBox(height: 8),
          ],
          _FilterRow(
            selected: _filter,
            onChanged: (f) => setState(() => _filter = f),
          ),
          const SizedBox(height: AppSpacing.md),
          _SummaryBar(
            orderCount: orders.length,
            total: totalSum,
            money: money,
            filtered: _filter != OrderHistoryFilter.all,
            exporting: _exportingExcel,
            onExportExcel: () => _exportToExcel(context, orders),
          ),
          const SizedBox(height: AppSpacing.lg),
          ..._buildDaySections(context, byDay, days, now, ref),
        ],
      ),
    );
  }

  Future<void> _exportToExcel(BuildContext context, List<Order> orders) async {
    if (_exportingExcel) return;
    setState(() => _exportingExcel = true);
    try {
      await OrderExcelExport.saveToFile(orders, periodLabel: _filter.label);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Файл Excel сохранён')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Не удалось сохранить: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _exportingExcel = false);
      }
    }
  }

  void _showPeriodSheet(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.surface,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 12),
              child: Text('Период', style: Theme.of(ctx).textTheme.titleMedium),
            ),
            for (final f in OrderHistoryFilter.values)
              ListTile(
                title: Text(f.label),
                leading: Icon(
                  _filter == f ? Icons.check_circle : Icons.radio_button_unchecked,
                  color: _filter == f ? AppColors.accent : AppColors.textTertiary,
                ),
                onTap: () {
                  setState(() => _filter = f);
                  Navigator.pop(ctx);
                },
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildDaySections(
    BuildContext context,
    Map<DateTime, List<Order>> byDay,
    List<DateTime> days,
    DateTime now,
    WidgetRef ref,
  ) {
    final out = <Widget>[];
    for (var i = 0; i < days.length; i++) {
      final day = days[i];
      out.add(_SectionDateHeader(day: day, now: now));
      out.add(const SizedBox(height: 10));
      for (final o in [...byDay[day]!]..sort((a, b) => b.createdAt.compareTo(a.createdAt))) {
        out.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: _OrderCard(
              order: o,
              onTap: () => _showOrderDetail(context, ref, o),
            ),
          ),
        );
      }
      out.add(const SizedBox(height: 8));
    }
    return out;
  }
}

/// Родительный падеж для даты вида «6 апреля 2026 г.»
const _ruMonthGenitive = <int, String>{
  1: 'января',
  2: 'февраля',
  3: 'марта',
  4: 'апреля',
  5: 'мая',
  6: 'июня',
  7: 'июля',
  8: 'августа',
  9: 'сентября',
  10: 'октября',
  11: 'ноября',
  12: 'декабря',
};

String _formatDateGenitive(DateTime d) {
  final m = _ruMonthGenitive[d.month] ?? '${d.month}';
  return '${d.day} $m ${d.year} г.';
}

class _HistoryToolbar extends StatelessWidget {
  const _HistoryToolbar({required this.onOpenPeriod});

  final VoidCallback onOpenPeriod;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(
          'Документы',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w800,
                letterSpacing: -0.3,
              ),
        ),
        const Spacer(),
        IconButton(
          icon: const Icon(Icons.date_range_outlined, color: AppColors.textSecondary),
          onPressed: onOpenPeriod,
          tooltip: 'Период',
        ),
        IconButton(
          icon: const Icon(Icons.tune_rounded, color: AppColors.textSecondary),
          onPressed: onOpenPeriod,
          tooltip: 'Фильтр',
        ),
      ],
    );
  }
}

class _SectionDateHeader extends StatelessWidget {
  const _SectionDateHeader({required this.day, required this.now});

  final DateTime day;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    final t0 = DateTime(now.year, now.month, now.day);
    final y = t0.subtract(const Duration(days: 1));
    final String label;
    if (day == t0) {
      label = 'Сегодня';
    } else if (day == y) {
      label = 'Вчера';
    } else {
      label = _formatDateGenitive(day);
    }
    return Padding(
      padding: const EdgeInsets.only(top: 4, bottom: 2),
      child: Text(
        label,
        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: AppColors.textTertiary,
              fontWeight: FontWeight.w600,
            ),
      ),
    );
  }
}

class _FilterRow extends StatelessWidget {
  const _FilterRow({required this.selected, required this.onChanged});

  final OrderHistoryFilter selected;
  final ValueChanged<OrderHistoryFilter> onChanged;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (var i = 0; i < OrderHistoryFilter.values.length; i++) ...[
            if (i > 0) const SizedBox(width: 8),
            FilterChip(
              showCheckmark: false,
              selected: selected == OrderHistoryFilter.values[i],
              label: Text(OrderHistoryFilter.values[i].label),
              selectedColor: AppColors.accent,
              checkmarkColor: Colors.black,
              labelStyle: TextStyle(
                color: selected == OrderHistoryFilter.values[i] ? Colors.black : AppColors.textPrimary,
                fontWeight: FontWeight.w700,
                fontSize: 13,
              ),
              onSelected: (_) => onChanged(OrderHistoryFilter.values[i]),
            ),
          ],
        ],
      ),
    );
  }
}

class _SummaryBar extends StatelessWidget {
  const _SummaryBar({
    required this.orderCount,
    required this.total,
    required this.money,
    required this.filtered,
    required this.exporting,
    required this.onExportExcel,
  });

  final int orderCount;
  final double total;
  final NumberFormat money;
  final bool filtered;
  final bool exporting;
  final VoidCallback onExportExcel;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 12, 4, 12),
      decoration: BoxDecoration(
        color: AppColors.surfaceElevated,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          const Icon(Icons.analytics_outlined, color: AppColors.textSecondary, size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  filtered ? 'В выбранном периоде' : 'Всего в истории',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(color: AppColors.textSecondary),
                ),
                const SizedBox(height: 2),
                Text(
                  '$orderCount ${_ordersWordRu(orderCount)} · ${money.format(total)}',
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w800),
                ),
              ],
            ),
          ),
          if (exporting)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 4),
              child: SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.accent),
              ),
            )
          else
            IconButton(
              tooltip: 'Выгрузка в Excel',
              icon: const Icon(Icons.table_chart_outlined, color: AppColors.textSecondary, size: 22),
              onPressed: onExportExcel,
            ),
        ],
      ),
    );
  }
}

double _statusProgress(OrderStatus s) {
  switch (s) {
    case OrderStatus.newOrder:
      return 0.18;
    case OrderStatus.processing:
      return 0.45;
    case OrderStatus.shipped:
      return 0.78;
    case OrderStatus.delivered:
      return 1.0;
  }
}

({Color color, String line}) _statusUi(OrderStatus s) {
  switch (s) {
    case OrderStatus.newOrder:
      return (color: AppColors.accent, line: 'Заказ принят');
    case OrderStatus.processing:
      return (color: AppColors.textPrimary, line: 'В обработке');
    case OrderStatus.shipped:
      return (color: const Color(0xFF0A84FF), line: 'Отправлен');
    case OrderStatus.delivered:
      return (color: AppColors.success, line: 'Доставлен');
  }
}

class _OrderCard extends ConsumerWidget {
  const _OrderCard({required this.order, required this.onTap});

  final Order order;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final time = DateFormat('HH:mm');
    final money = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);
    final count = order.items.fold<int>(0, (s, e) => s + e.quantity);
    final user = ref.watch(userProfileProvider);
    final buyer = (user != null && user.name.trim().isNotEmpty) ? user.name : 'Покупатель';
    final progress = _statusProgress(order.status);
    final paid = order.total * progress;
    final ui = _statusUi(order.status);
    final idLabel = 'GM-${order.number}';

    return Material(
      color: AppColors.surfaceElevated,
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: AppColors.border.withValues(alpha: 0.85)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.35),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        idLabel,
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              color: AppColors.accent,
                              fontWeight: FontWeight.w900,
                              letterSpacing: 0.2,
                            ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'МСК · ${time.format(order.createdAt)}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.textTertiary,
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  ui.line,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: ui.color,
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    const Icon(Icons.person_outline_rounded, size: 18, color: AppColors.textTertiary),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        buyer,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: AppColors.textSecondary,
                            ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Text(
                  money.format(order.total),
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.5,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  '$count шт',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textTertiary),
                ),
                const SizedBox(height: 10),
                ClipRRect(
                  borderRadius: BorderRadius.circular(999),
                  child: LinearProgressIndicator(
                    value: progress,
                    minHeight: 5,
                    backgroundColor: AppColors.border,
                    color: const Color(0xFF0A84FF),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '${money.format(paid)} из ${money.format(order.total)} · ${(progress * 100).round()}%',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(color: AppColors.textSecondary),
                ),
                const SizedBox(height: 4),
                Text(
                  _previewShort(order),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textTertiary),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _previewShort(Order o) {
    return o.items.map((e) => e.title).join(' · ');
  }
}

class OrderStatusPill extends StatelessWidget {
  const OrderStatusPill({super.key, required this.status});

  final OrderStatus status;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.chip,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.border),
      ),
      child: Text(
        status.labelRu,
        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
      ),
    );
  }
}

void _showOrderDetail(BuildContext context, WidgetRef ref, Order o) {
  final rootContext = context;
  final money = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);
  final when = DateFormat('dd.MM.yyyy HH:mm');
  const uuid = Uuid();

  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (sheetContext) {
      return DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.72,
        minChildSize: 0.35,
        maxChildSize: 0.92,
        builder: (context, scroll) {
          return ListView(
            controller: scroll,
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppColors.border,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Text('№ ${o.number}', style: Theme.of(context).textTheme.titleLarge),
                  const Spacer(),
                  OrderStatusPill(status: o.status),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                when.format(o.createdAt),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textSecondary),
              ),
              if (o.addressLine != null && o.addressLine!.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text('Адрес', style: Theme.of(context).textTheme.labelLarge),
                const SizedBox(height: 4),
                Text(o.addressLine!, style: Theme.of(context).textTheme.bodyMedium),
              ],
              if (o.deliveryMethod != null) ...[
                const SizedBox(height: 8),
                Text('Доставка: ${o.deliveryMethod}', style: Theme.of(context).textTheme.bodySmall),
              ],
              if (o.paymentMethod != null) ...[
                Text('Оплата: ${o.paymentMethod}', style: Theme.of(context).textTheme.bodySmall),
              ],
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: () async {
                  for (final it in o.items) {
                    final newItem = CartItem(
                      id: uuid.v4(),
                      productId: it.productId,
                      variantId: it.variantId,
                      title: it.title,
                      imageUrl: it.imageUrl,
                      unitPrice: it.unitPrice,
                      currency: it.currency,
                      quantity: it.quantity,
                      variantLabel: it.variantLabel,
                      selectedAttributes: it.selectedAttributes,
                    );
                    await ref.read(cartProvider.notifier).addOrUpdate(newItem);
                  }
                  if (sheetContext.mounted) Navigator.of(sheetContext).pop();
                  if (rootContext.mounted) {
                    ScaffoldMessenger.of(rootContext).showSnackBar(
                      const SnackBar(content: Text('Товары добавлены в корзину')),
                    );
                  }
                },
                icon: const Icon(Icons.shopping_bag_outlined, size: 20),
                label: const Text('Повторить в корзине'),
              ),
              const SizedBox(height: 20),
              Text('Состав', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              for (final it in o.items) ...[
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(it.title, style: Theme.of(context).textTheme.bodyLarge),
                          if (it.variantLabel != null && it.variantLabel!.isNotEmpty)
                            Text(
                              it.variantLabel!,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                        ],
                      ),
                    ),
                    Text(
                      '${it.quantity} × ${money.format(it.unitPrice)}',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
                const SizedBox(height: 10),
              ],
              const Divider(color: AppColors.border),
              Row(
                children: [
                  Text('Итого', style: Theme.of(context).textTheme.titleMedium),
                  const Spacer(),
                  Text(
                    money.format(o.total),
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
                  ),
                ],
              ),
            ],
          );
        },
      );
    },
  );
}

String _ordersWordRu(int n) {
  if (n % 100 >= 11 && n % 100 <= 19) return 'заказов';
  switch (n % 10) {
    case 1:
      return 'заказ';
    case 2:
    case 3:
    case 4:
      return 'заказа';
    default:
      return 'заказов';
  }
}

/// Упрощённая плюрализация «позиций» для русского
String positionWordRu(int n) {
  if (n % 100 >= 11 && n % 100 <= 19) return '$n позиций';
  switch (n % 10) {
    case 1:
      return '$n позиция';
    case 2:
    case 3:
    case 4:
      return '$n позиции';
    default:
      return '$n позиций';
  }
}
