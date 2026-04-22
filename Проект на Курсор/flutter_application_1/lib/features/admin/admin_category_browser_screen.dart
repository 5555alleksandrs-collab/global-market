import 'package:cached_network_image/cached_network_image.dart';
import 'package:collection/collection.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../application/providers.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/domain/models/product.dart';
import '../../core/theme/admin_theme.dart';

/// Товары сгруппированы по категориям (как «папки»).
class AdminCategoryBrowserScreen extends ConsumerWidget {
  const AdminCategoryBrowserScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categories = ref.watch(categoriesProvider);
    final products = ref.watch(allProductsProvider);
    final fmt = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);

    return categories.when(
      data: (cats) {
        return products.when(
          data: (list) {
            final grouped = groupBy(list, (Product p) => p.categoryId);
            return ListView.builder(
              padding: const EdgeInsets.all(AppSpacing.md),
              itemCount: cats.length,
              itemBuilder: (context, i) {
                final cat = cats[i];
                final raw = grouped[cat.id] ?? <Product>[];
                final items = List<Product>.from(raw)
                  ..sort((a, b) => a.name.compareTo(b.name));
                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Material(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(12),
                    child: Theme(
                      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                      child: ExpansionTile(
                        initiallyExpanded: items.length <= 6,
                        tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                        leading: Icon(Icons.folder_outlined, color: AdminTheme.primary),
                        title: Text(
                          cat.name,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                        ),
                        subtitle: Text(
                          '${items.length} товаров · ${cat.subtitle ?? cat.id}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        children: items.isEmpty
                            ? [
                                Padding(
                                  padding: const EdgeInsets.all(16),
                                  child: Text(
                                    'Пусто — добавьте товар в категории «${cat.name}»',
                                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary),
                                  ),
                                ),
                              ]
                            : items.map((p) {
                                return ListTile(
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                                  leading: ClipRRect(
                                    borderRadius: BorderRadius.circular(10),
                                    child: CachedNetworkImage(
                                      imageUrl: p.images.isNotEmpty ? p.images.first : '',
                                      width: 48,
                                      height: 48,
                                      fit: BoxFit.cover,
                                      errorWidget: (_, __, ___) => Container(
                                        width: 48,
                                        height: 48,
                                        color: AppColors.chip,
                                        child: const Icon(Icons.image_not_supported_outlined, size: 20),
                                      ),
                                    ),
                                  ),
                                  title: Text(p.name, maxLines: 2, overflow: TextOverflow.ellipsis),
                                  subtitle: _CategoryProductSubtitle(price: fmt.format(p.price), product: p),
                                  trailing: const Icon(Icons.edit_outlined, size: 20),
                                  onTap: () => context.push('/admin/product?id=${Uri.encodeComponent(p.id)}'),
                                );
                              }).toList(),
                      ),
                    ),
                  ),
                );
              },
            );
          },
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('$e')),
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('$e')),
    );
  }
}

class _CategoryProductSubtitle extends StatelessWidget {
  const _CategoryProductSubtitle({required this.price, required this.product});

  final String price;
  final Product product;

  @override
  Widget build(BuildContext context) {
    final q = product.stockQuantity;
    String stockText;
    Color? stockColor;
    if (q <= 0) {
      stockText = 'Нет в наличии';
      stockColor = AdminTheme.danger;
    } else if (q < 5) {
      stockText = '$q шт. · мало';
      stockColor = AdminTheme.warning;
    } else {
      stockText = '$q шт.';
      stockColor = AdminTheme.success;
    }
    return Text.rich(
      TextSpan(
        children: [
          TextSpan(text: price, style: const TextStyle(fontWeight: FontWeight.w600)),
          const TextSpan(text: ' · '),
          TextSpan(text: stockText, style: TextStyle(color: stockColor, fontWeight: FontWeight.w600)),
        ],
      ),
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );
  }
}
