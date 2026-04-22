import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../application/providers.dart';
import '../../common/widgets/app_states.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/domain/models/cart_item.dart';

class CartScreen extends ConsumerWidget {
  const CartScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final items = ref.watch(cartProvider);
    final fmt = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);
    final total = items.fold<double>(0, (s, e) => s + e.lineTotal);

    return Scaffold(
      appBar: AppBar(title: const Text('Корзина')),
      body: items.isEmpty
          ? const AppEmptyState(
              title: 'Корзина пуста',
              subtitle: 'Добавьте товары из каталога или главной.',
              icon: Icons.shopping_bag_outlined,
            )
          : Column(
              children: [
                Expanded(
                  child: ListView.separated(
                    padding: const EdgeInsets.all(AppSpacing.md),
                    itemCount: items.length,
                    separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                    itemBuilder: (context, i) {
                      final it = items[i];
                      return _CartTile(
                        item: it,
                        onMinus: () => ref.read(cartProvider.notifier).setQuantity(it.id, it.quantity - 1),
                        onPlus: () => ref.read(cartProvider.notifier).setQuantity(it.id, it.quantity + 1),
                        onRemove: () => ref.read(cartProvider.notifier).remove(it.id),
                      );
                    },
                  ),
                ),
                Container(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  decoration: const BoxDecoration(
                    color: AppColors.surface,
                    border: Border(top: BorderSide(color: AppColors.border)),
                  ),
                  child: SafeArea(
                    top: false,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Row(
                          children: [
                            Text('Итого', style: Theme.of(context).textTheme.titleMedium),
                            const Spacer(),
                            Text(
                              fmt.format(total),
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        FilledButton(
                          onPressed: () => context.push('/checkout'),
                          child: const Text('Оформление заказа'),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}

class _CartTile extends StatelessWidget {
  const _CartTile({
    required this.item,
    required this.onMinus,
    required this.onPlus,
    required this.onRemove,
  });

  final CartItem item;
  final VoidCallback onMinus;
  final VoidCallback onPlus;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);

    return Material(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(18),
      child: Ink(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.border),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: CachedNetworkImage(
                  imageUrl: item.imageUrl,
                  width: 92,
                  height: 92,
                  fit: BoxFit.cover,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(item.title, style: Theme.of(context).textTheme.titleMedium),
                    if (item.variantLabel != null && item.variantLabel!.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(
                        item.variantLabel!,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ],
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Text(fmt.format(item.unitPrice), style: Theme.of(context).textTheme.titleMedium),
                        const Spacer(),
                        IconButton(
                          onPressed: onRemove,
                          icon: const Icon(Icons.delete_outline_rounded),
                          color: AppColors.textSecondary,
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        _QtyButton(icon: Icons.remove_rounded, onPressed: onMinus),
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                          child: Text('${item.quantity}', style: Theme.of(context).textTheme.titleMedium),
                        ),
                        _QtyButton(icon: Icons.add_rounded, onPressed: onPlus),
                        const Spacer(),
                        Text(
                          fmt.format(item.lineTotal),
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _QtyButton extends StatelessWidget {
  const _QtyButton({required this.icon, required this.onPressed});

  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.chip,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onPressed,
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Icon(icon, size: 18),
        ),
      ),
    );
  }
}
