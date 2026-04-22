import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../application/providers.dart';
import '../../common/widgets/app_states.dart';
import '../../common/widgets/product_card.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/domain/models/product.dart';
import 'application/catalog_query.dart';
import 'domain/catalog_filters.dart';

class CatalogScreen extends ConsumerWidget {
  const CatalogScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(allProductsProvider);
    final query = ref.watch(catalogQueryProvider);
    final brandsAsync = ref.watch(brandsProvider);
    final categoriesAsync = ref.watch(categoriesProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Каталог'),
        actions: [
          IconButton(
            tooltip: query.gridView ? 'Список' : 'Сетка',
            onPressed: () {
              ref.read(catalogQueryProvider.notifier).state =
                  query.copyWith(gridView: !query.gridView);
            },
            icon: Icon(query.gridView ? Icons.view_list_rounded : Icons.grid_view_rounded),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.sm),
            child: TextField(
              decoration: const InputDecoration(
                hintText: 'Поиск по названию',
                prefixIcon: Icon(Icons.search),
              ),
              onChanged: (v) {
                final q = ref.read(catalogQueryProvider);
                ref.read(catalogQueryProvider.notifier).state = q.copyWith(search: v);
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            child: brandsAsync.when(
              data: (list) {
                return SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      FilterChip(
                        label: const Text('В наличии'),
                        selected: query.inStockOnly,
                        showCheckmark: false,
                        selectedColor: AppColors.accent,
                        checkmarkColor: Colors.white,
                        labelStyle: TextStyle(
                          color: query.inStockOnly ? Colors.white : AppColors.textPrimary,
                          fontWeight: FontWeight.w600,
                        ),
                        onSelected: (v) {
                          ref.read(catalogQueryProvider.notifier).state =
                              query.copyWith(inStockOnly: v);
                        },
                      ),
                      const SizedBox(width: 8),
                      ...CatalogSort.values.map(
                        (s) => Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: ChoiceChip(
                            label: Text(s.labelRu),
                            selected: query.sort == s,
                            selectedColor: AppColors.accent,
                            labelStyle: TextStyle(
                              color: query.sort == s ? Colors.white : AppColors.textPrimary,
                              fontWeight: FontWeight.w600,
                            ),
                            onSelected: (_) {
                              ref.read(catalogQueryProvider.notifier).state =
                                  query.copyWith(sort: s);
                            },
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      ...list.map(
                        (b) => Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: FilterChip(
                            label: Text(b.name),
                            selected: query.brandId == b.id,
                            selectedColor: AppColors.accent,
                            checkmarkColor: Colors.white,
                            labelStyle: TextStyle(
                              color: query.brandId == b.id ? Colors.white : AppColors.textPrimary,
                              fontWeight: FontWeight.w600,
                            ),
                            onSelected: (sel) {
                              ref.read(catalogQueryProvider.notifier).state = query.copyWith(
                                brandId: sel ? b.id : null,
                                clearBrand: !sel,
                              );
                            },
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
              loading: () => const SizedBox(height: 44, child: AppLoading()),
              error: (e, _) => Text('Бренды: ошибка', style: Theme.of(context).textTheme.bodyMedium),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            child: categoriesAsync.when(
              data: (cats) {
                return SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      FilterChip(
                        label: const Text('Все категории'),
                        selected: query.categoryId == null,
                        selectedColor: AppColors.accent,
                        checkmarkColor: Colors.white,
                        labelStyle: TextStyle(
                          color: query.categoryId == null ? Colors.white : AppColors.textPrimary,
                          fontWeight: FontWeight.w600,
                        ),
                        onSelected: (_) {
                          ref.read(catalogQueryProvider.notifier).state =
                              query.copyWith(clearCategory: true);
                        },
                      ),
                      ...cats.map(
                        (c) => Padding(
                          padding: const EdgeInsets.only(left: 8),
                          child: FilterChip(
                            label: Text(c.name),
                            selected: query.categoryId == c.id,
                            selectedColor: AppColors.accent,
                            checkmarkColor: Colors.white,
                            labelStyle: TextStyle(
                              color: query.categoryId == c.id ? Colors.white : AppColors.textPrimary,
                              fontWeight: FontWeight.w600,
                            ),
                            onSelected: (sel) {
                              ref.read(catalogQueryProvider.notifier).state = query.copyWith(
                                categoryId: sel ? c.id : null,
                                clearCategory: !sel,
                              );
                            },
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
              loading: () => const SizedBox.shrink(),
              error: (_, __) => const SizedBox.shrink(),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Expanded(
            child: async.when(
              data: (all) {
                final filtered = applyCatalogQuery(all, query);
                if (filtered.isEmpty) {
                  return const AppEmptyState(
                    title: 'Ничего не найдено',
                    subtitle: 'Измените фильтры или поисковый запрос.',
                    icon: Icons.search_off_rounded,
                  );
                }
                if (query.gridView) {
                  return GridView.builder(
                    padding: const EdgeInsets.all(AppSpacing.md),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      mainAxisSpacing: AppSpacing.sm,
                      crossAxisSpacing: AppSpacing.sm,
                      childAspectRatio: 0.62,
                    ),
                    itemCount: filtered.length,
                    itemBuilder: (context, i) => ProductCard(product: filtered[i]),
                  );
                }
                return ListView.separated(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  itemCount: filtered.length,
                  separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                  itemBuilder: (context, i) => _ListProductTile(product: filtered[i]),
                );
              },
              loading: () => const AppLoading(message: 'Загрузка…'),
              error: (e, _) => AppErrorState(
                message: 'Ошибка загрузки',
                onRetry: () => ref.invalidate(allProductsProvider),
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openPriceSheet(context, ref),
        icon: const Icon(Icons.tune_rounded),
        label: const Text('Цена'),
      ),
    );
  }

  Future<void> _openPriceSheet(BuildContext context, WidgetRef ref) async {
    final query = ref.read(catalogQueryProvider);
    final minCtrl = TextEditingController(
      text: query.minPrice?.toStringAsFixed(0) ?? '',
    );
    final maxCtrl = TextEditingController(
      text: query.maxPrice?.toStringAsFixed(0) ?? '',
    );

    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Фильтр по цене', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: AppSpacing.md),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: minCtrl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'От'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: maxCtrl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'До'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () {
                        ref.read(catalogQueryProvider.notifier).state =
                            query.copyWith(clearPrice: true);
                        Navigator.pop(context);
                      },
                      child: const Text('Сбросить'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: () {
                        double? minP;
                        double? maxP;
                        if (minCtrl.text.trim().isNotEmpty) {
                          minP = double.tryParse(minCtrl.text.trim());
                        }
                        if (maxCtrl.text.trim().isNotEmpty) {
                          maxP = double.tryParse(maxCtrl.text.trim());
                        }
                        ref.read(catalogQueryProvider.notifier).state = query.copyWith(
                          minPrice: minP,
                          maxPrice: maxP,
                        );
                        Navigator.pop(context);
                      },
                      child: const Text('Применить'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ListProductTile extends StatelessWidget {
  const _ListProductTile({required this.product});

  final Product product;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(18),
      onTap: () => context.push('/product/${product.id}'),
      child: Ink(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(14),
              child: Image.network(
                product.images.first,
                width: 96,
                height: 96,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => Container(
                  width: 96,
                  height: 96,
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
                  Text(product.brandId.toUpperCase(),
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontSize: 11)),
                  const SizedBox(height: 4),
                  Text(product.name, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Text('${product.price.toStringAsFixed(0)} ₽',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right_rounded, color: AppColors.textSecondary),
          ],
        ),
      ),
    );
  }
}
