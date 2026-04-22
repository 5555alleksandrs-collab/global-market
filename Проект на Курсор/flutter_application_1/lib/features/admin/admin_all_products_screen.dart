import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../application/providers.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/domain/models/product.dart';
import '../../core/theme/admin_theme.dart';

/// Полный список товаров с поиском (плоский вид).
class AdminAllProductsScreen extends ConsumerStatefulWidget {
  const AdminAllProductsScreen({super.key});

  @override
  ConsumerState<AdminAllProductsScreen> createState() => _AdminAllProductsScreenState();
}

class _AdminAllProductsScreenState extends ConsumerState<AdminAllProductsScreen> {
  final _search = TextEditingController();

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _confirmDelete(Product p) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Удалить товар?'),
        content: Text(p.name),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Отмена')),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (ok == true && mounted) {
      await ref.read(adminCatalogServiceProvider).deleteProduct(p.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Удалено')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(allProductsProvider);
    final fmt = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.sm),
          child: TextField(
            controller: _search,
            decoration: const InputDecoration(
              hintText: 'Поиск по названию, SKU или id',
              prefixIcon: Icon(Icons.search),
            ),
            onChanged: (_) => setState(() {}),
          ),
        ),
        Expanded(
          child: async.when(
            data: (list) {
              final q = _search.text.trim().toLowerCase();
              final filtered = q.isEmpty
                  ? list
                  : list
                      .where(
                        (p) =>
                            p.name.toLowerCase().contains(q) ||
                            p.sku.toLowerCase().contains(q) ||
                            p.id.toLowerCase().contains(q),
                      )
                      .toList();
              filtered.sort((a, b) => a.name.compareTo(b.name));
              if (filtered.isEmpty) {
                return const Center(child: Text('Нет товаров'));
              }
              return ListView.separated(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                itemCount: filtered.length,
                separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                itemBuilder: (context, i) {
                  final p = filtered[i];
                  return Material(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(16),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(16),
                      onTap: () => context.push('/admin/product?id=${Uri.encodeComponent(p.id)}'),
                      child: Ink(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: AppColors.border),
                        ),
                        child: Row(
                          children: [
                            ClipRRect(
                              borderRadius: BorderRadius.circular(12),
                              child: CachedNetworkImage(
                                imageUrl: p.images.isNotEmpty ? p.images.first : '',
                                width: 64,
                                height: 64,
                                fit: BoxFit.cover,
                                errorWidget: (_, __, ___) => Container(
                                  width: 64,
                                  height: 64,
                                  color: AppColors.chip,
                                  child: const Icon(Icons.image_not_supported_outlined),
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    p.name,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: Theme.of(context).textTheme.titleMedium,
                                  ),
                                  const SizedBox(height: 8),
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 6,
                                    crossAxisAlignment: WrapCrossAlignment.center,
                                    children: [
                                      Text(
                                        fmt.format(p.price),
                                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                              fontWeight: FontWeight.w700,
                                              color: const Color(0xFF0F172A),
                                            ),
                                      ),
                                      _StockChip(product: p),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: const Color(0xFFF1F5F9),
                                          borderRadius: BorderRadius.circular(8),
                                        ),
                                        child: Text(
                                          p.categoryId,
                                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                                color: const Color(0xFF64748B),
                                                fontWeight: FontWeight.w600,
                                              ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.delete_outline_rounded),
                              onPressed: () => _confirmDelete(p),
                            ),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              );
            },
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('Ошибка: $e')),
          ),
        ),
      ],
    );
  }
}

class _StockChip extends StatelessWidget {
  const _StockChip({required this.product});

  final Product product;

  @override
  Widget build(BuildContext context) {
    final q = product.stockQuantity;
    Color bg;
    Color fg;
    String text;
    if (q <= 0) {
      bg = const Color(0xFFFEE2E2);
      fg = AdminTheme.danger;
      text = 'Нет в наличии';
    } else if (q < 5) {
      bg = const Color(0xFFFFF7ED);
      fg = AdminTheme.warning;
      text = '$q шт. · мало';
    } else {
      bg = const Color(0xFFD1FAE5);
      fg = AdminTheme.success;
      text = '$q шт.';
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: fg,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}
