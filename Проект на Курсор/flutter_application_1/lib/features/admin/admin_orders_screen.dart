import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../application/providers.dart';
import '../../core/domain/models/order.dart';
import '../../core/theme/admin_theme.dart';

/// Управление заказами: просмотр, смена статуса (данные в [ordersProvider] / SharedPreferences).
class AdminOrdersScreen extends ConsumerStatefulWidget {
  const AdminOrdersScreen({super.key});

  @override
  ConsumerState<AdminOrdersScreen> createState() => _AdminOrdersScreenState();
}

class _AdminOrdersScreenState extends ConsumerState<AdminOrdersScreen> {
  OrderStatus? _filter;

  @override
  Widget build(BuildContext context) {
    final orders = ref.watch(ordersProvider);
    final money = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);
    final fmt = DateFormat('dd.MM.yyyy HH:mm');

    var list = [...orders]..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    if (_filter != null) {
      list = list.where((e) => e.status == _filter).toList();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          child: Text(
            'Статусы обновляются на этом устройстве и видны клиенту в «Мои заказы».',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFF64748B)),
          ),
        ),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Row(
            children: [
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: FilterChip(
                  label: const Text('Все'),
                  selected: _filter == null,
                  onSelected: (_) => setState(() => _filter = null),
                ),
              ),
              for (final s in OrderStatus.values)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(s.labelRu),
                    selected: _filter == s,
                    onSelected: (_) => setState(() => _filter = s),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: list.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Text(
                      _filter == null ? 'Заказов пока нет' : 'Нет заказов с этим статусом',
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: const Color(0xFF94A3B8)),
                    ),
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  itemCount: list.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (context, i) {
                    final o = list[i];
                    return Material(
                      color: AdminTheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(16),
                        onTap: () => _openSheet(context, o),
                        child: Ink(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: AdminTheme.border),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Text(
                                    '№ ${o.number}',
                                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                          fontWeight: FontWeight.w800,
                                          color: const Color(0xFF0F172A),
                                        ),
                                  ),
                                  const Spacer(),
                                  _StatusBadge(status: o.status),
                                ],
                              ),
                              const SizedBox(height: 6),
                              Text(
                                fmt.format(o.createdAt),
                                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFF64748B)),
                              ),
                              const SizedBox(height: 10),
                              Text(
                                o.items.map((e) => '${e.title} × ${e.quantity}').join(' · '),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: const Color(0xFF334155)),
                              ),
                              const SizedBox(height: 10),
                              Text(
                                money.format(o.total),
                                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                      fontWeight: FontWeight.w900,
                                      color: AdminTheme.primary,
                                    ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Future<void> _openSheet(BuildContext context, Order order) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => _OrderManageSheet(initial: order),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});

  final OrderStatus status;

  Color get _c {
    switch (status) {
      case OrderStatus.newOrder:
        return AdminTheme.primary;
      case OrderStatus.processing:
        return AdminTheme.warning;
      case OrderStatus.shipped:
        return const Color(0xFF0EA5E9);
      case OrderStatus.delivered:
        return AdminTheme.success;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: _c.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: _c.withValues(alpha: 0.35)),
      ),
      child: Text(
        status.labelRu,
        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: _c),
      ),
    );
  }
}

class _OrderManageSheet extends ConsumerStatefulWidget {
  const _OrderManageSheet({required this.initial});

  final Order initial;

  @override
  ConsumerState<_OrderManageSheet> createState() => _OrderManageSheetState();
}

class _OrderManageSheetState extends ConsumerState<_OrderManageSheet> {
  late OrderStatus _status;

  @override
  void initState() {
    super.initState();
    _status = widget.initial.status;
  }

  @override
  Widget build(BuildContext context) {
    final o = widget.initial;
    final money = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);
    final fmt = DateFormat('dd.MM.yyyy HH:mm');
    final bottom = MediaQuery.paddingOf(context).bottom;

    return Padding(
      padding: EdgeInsets.only(bottom: bottom + 8),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: const Color(0xFFE2E8F0),
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Заказ № ${o.number}',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                  ),
                ),
                _StatusBadge(status: _status),
              ],
            ),
            const SizedBox(height: 8),
            Text(fmt.format(o.createdAt), style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFF64748B))),
            const SizedBox(height: 16),
            Text('Сумма', style: Theme.of(context).textTheme.labelSmall?.copyWith(color: const Color(0xFF64748B))),
            Text(
              money.format(o.total),
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900, color: AdminTheme.primary),
            ),
            if (o.addressLine != null && o.addressLine!.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('Адрес', style: Theme.of(context).textTheme.labelSmall?.copyWith(color: const Color(0xFF64748B))),
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
            Text('Состав', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            ...o.items.map(
              (e) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(e.title, style: Theme.of(context).textTheme.bodyMedium),
                    ),
                    Text(
                      '× ${e.quantity} · ${money.format(e.lineTotal)}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFF64748B)),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text('Статус заказа', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              decoration: BoxDecoration(
                border: Border.all(color: AdminTheme.border),
                borderRadius: BorderRadius.circular(8),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<OrderStatus>(
                  value: _status,
                  isExpanded: true,
                  items: OrderStatus.values
                      .map(
                        (s) => DropdownMenuItem(
                          value: s,
                          child: Text(s.labelRu),
                        ),
                      )
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setState(() => _status = v);
                  },
                ),
              ),
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: () async {
                final updated = o.copyWith(status: _status);
                await ref.read(ordersProvider.notifier).updateOrder(updated);
                if (!context.mounted) return;
                Navigator.of(context).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Статус сохранён')),
                );
              },
              style: FilledButton.styleFrom(
                backgroundColor: AdminTheme.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: const Text('Сохранить статус'),
            ),
          ],
        ),
      ),
    );
  }
}
