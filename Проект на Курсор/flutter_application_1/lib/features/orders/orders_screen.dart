import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../application/providers.dart';
import '../../core/router/safe_navigation.dart';
import '../../common/widgets/app_states.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/domain/models/order.dart';

class OrdersScreen extends ConsumerWidget {
  const OrdersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final orders = ref.watch(ordersProvider);
    final fmt = DateFormat('dd.MM.yyyy HH:mm');
    final money = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => popOrGo(context),
        ),
        title: const Text('Мои заказы'),
      ),
      body: orders.isEmpty
          ? const AppEmptyState(
              title: 'Заказов пока нет',
              subtitle: 'Оформите заказ — и он появится здесь.',
              icon: Icons.receipt_long_outlined,
            )
          : ListView.separated(
              padding: const EdgeInsets.all(AppSpacing.md),
              itemCount: orders.length,
              separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
              itemBuilder: (context, i) {
                final o = orders[i];
                return Material(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(18),
                  child: Ink(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text('№ ${o.number}', style: Theme.of(context).textTheme.titleMedium),
                              const Spacer(),
                              _StatusPill(status: o.status),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Text(
                            fmt.format(o.createdAt),
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                          const SizedBox(height: 10),
                          Text(
                            o.items.map((e) => '${e.title} × ${e.quantity}').join(', '),
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.bodyLarge,
                          ),
                          const SizedBox(height: 10),
                          Text(
                            money.format(o.total),
                            style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.status});

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
