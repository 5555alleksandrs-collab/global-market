import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../application/providers.dart';
import '../../common/widgets/app_states.dart';
import '../../common/widgets/product_card.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/domain/models/category.dart';
import '../../core/domain/models/product.dart';
import 'application/catalog_query.dart';
import 'domain/catalog_filters.dart';

int _sheetFilterCount(CatalogQuery q) {
  var n = 0;
  if (q.brandId != null) n++;
  if (q.minPrice != null || q.maxPrice != null) n++;
  return n;
}

class CatalogScreen extends ConsumerWidget {
  const CatalogScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(allProductsProvider);
    final query = ref.watch(catalogQueryProvider);
    final categoriesAsync = ref.watch(categoriesProvider);
    final nSheetFilters = _sheetFilterCount(query);

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
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(AppSpacing.md, 8, AppSpacing.md, 0),
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Поиск по каталогу',
                prefixIcon: const Icon(Icons.search_rounded, color: AppColors.textSecondary),
                filled: true,
                fillColor: AppColors.surface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide: const BorderSide(color: AppColors.border),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide: const BorderSide(color: AppColors.border),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide: const BorderSide(color: AppColors.accent, width: 1.4),
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              ),
              onChanged: (v) {
                final q = ref.read(catalogQueryProvider);
                ref.read(catalogQueryProvider.notifier).state = q.copyWith(search: v);
              },
            ),
          ),
          const SizedBox(height: 6),
          categoriesAsync.when(
            data: (cats) => _CategoryStrip(categories: cats),
            loading: () => const SizedBox(height: 8),
            error: (_, __) => const SizedBox.shrink(),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(AppSpacing.md, 10, AppSpacing.md, 6),
            child: _ControlBar(
              nSheetFilters: nSheetFilters,
            ),
          ),
          if (nSheetFilters > 0 || query.inStockOnly)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: 4),
              child: _ActiveFilterChips(),
            ),
          const SizedBox(height: 4),
          Expanded(
            child: async.when(
              data: (all) {
                final filtered = applyCatalogQuery(all, query);
                if (filtered.isEmpty) {
                  return const AppEmptyState(
                    title: 'Ничего не найдено',
                    subtitle: 'Смените категорию, фильтры или запрос.',
                    icon: Icons.search_off_rounded,
                  );
                }
                if (query.gridView) {
                  return GridView.builder(
                    padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.lg),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      mainAxisSpacing: AppSpacing.sm,
                      crossAxisSpacing: AppSpacing.sm,
                      childAspectRatio: 0.7,
                    ),
                    itemCount: filtered.length,
                    itemBuilder: (context, i) => ProductCard(product: filtered[i]),
                  );
                }
                return ListView.separated(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.lg),
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
    );
  }
}

/// Горизонтальная лента категорий с заголовком секции.
class _CategoryStrip extends ConsumerWidget {
  const _CategoryStrip({required this.categories});

  final List<Category> categories;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = ref.watch(catalogQueryProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
          child: Row(
            children: [
              Text(
                'Категории',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      color: AppColors.textSecondary,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.3,
                    ),
              ),
              if (query.categoryId != null) ...[
                const Spacer(),
                TextButton(
                  onPressed: () {
                    ref.read(catalogQueryProvider.notifier).state =
                        ref.read(catalogQueryProvider).copyWith(clearCategory: true);
                  },
                  child: const Text('Сбросить'),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 40,
          child: ListView(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            scrollDirection: Axis.horizontal,
            children: [
              _CategoryChip(
                label: 'Все',
                selected: query.categoryId == null,
                onTap: () {
                  ref.read(catalogQueryProvider.notifier).state =
                      ref.read(catalogQueryProvider).copyWith(clearCategory: true);
                },
              ),
              for (final c in categories) ...[
                const SizedBox(width: 8),
                _CategoryChip(
                  label: c.name,
                  selected: query.categoryId == c.id,
                  onTap: () {
                    final q = ref.read(catalogQueryProvider);
                    ref.read(catalogQueryProvider.notifier).state = q.copyWith(
                      categoryId: c.id,
                      clearCategory: false,
                    );
                  },
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _CategoryChip extends StatelessWidget {
  const _CategoryChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? AppColors.accent.withValues(alpha: 0.18) : AppColors.surface,
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(999),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Text(
            label,
            style: TextStyle(
              color: selected ? AppColors.accent : AppColors.textPrimary,
              fontWeight: FontWeight.w600,
              fontSize: 13,
            ),
          ),
        ),
      ),
    );
  }
}

/// Сортировка, «в наличии», кнопка «Фильтры».
class _ControlBar extends ConsumerWidget {
  const _ControlBar({required this.nSheetFilters});

  final int nSheetFilters;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = ref.watch(catalogQueryProvider);
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        PopupMenuButton<CatalogSort>(
          initialValue: query.sort,
          onSelected: (s) {
            ref.read(catalogQueryProvider.notifier).state = query.copyWith(sort: s);
          },
          itemBuilder: (c) => CatalogSort.values
              .map(
                (s) => PopupMenuItem<CatalogSort>(
                  value: s,
                  child: Text(
                    s.labelRu,
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500),
                  ),
                ),
              )
              .toList(),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.sort_rounded, size: 18, color: AppColors.textSecondary),
                const SizedBox(width: 6),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 150),
                  child: Text(
                    query.sort.labelRu,
                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const Icon(Icons.expand_more_rounded, color: AppColors.textSecondary, size: 20),
              ],
            ),
          ),
        ),
        FilterChip(
          label: const Text('В наличии'),
          selected: query.inStockOnly,
          showCheckmark: true,
          selectedColor: AppColors.accent,
          checkmarkColor: Colors.white,
          labelStyle: TextStyle(
            color: query.inStockOnly ? Colors.white : AppColors.textPrimary,
            fontWeight: FontWeight.w600,
            fontSize: 13,
          ),
          onSelected: (v) {
            ref.read(catalogQueryProvider.notifier).state = query.copyWith(inStockOnly: v);
          },
        ),
        FilledButton.tonalIcon(
          onPressed: () => _openFullFiltersSheet(context, ref),
          icon: Stack(
            clipBehavior: Clip.none,
            children: [
              const Icon(Icons.tune_rounded, size: 20),
              if (nSheetFilters > 0)
                Positioned(
                  right: -4,
                  top: -4,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: const BoxDecoration(
                      color: AppColors.accent,
                      shape: BoxShape.circle,
                    ),
                    child: Text(
                      '$nSheetFilters',
                      style: const TextStyle(color: Colors.black, fontSize: 9, fontWeight: FontWeight.w800),
                    ),
                  ),
                ),
            ],
          ),
          label: const Text('Фильтры'),
          style: FilledButton.styleFrom(
            foregroundColor: AppColors.textPrimary,
            backgroundColor: AppColors.surfaceElevated,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: const BorderSide(color: AppColors.border),
            ),
          ),
        ),
      ],
    );
  }
}

class _ActiveFilterChips extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = ref.watch(catalogQueryProvider);
    final brands = ref.watch(brandsProvider);
    return brands.when(
      data: (list) {
        final chips = <Widget>[];
        if (query.brandId != null) {
          var name = query.brandId!;
          for (final b in list) {
            if (b.id == query.brandId) {
              name = b.name;
              break;
            }
          }
          chips.add(
            _DismissChip(
              label: 'Бренд: $name',
              onDeleted: () {
                final q = ref.read(catalogQueryProvider);
                ref.read(catalogQueryProvider.notifier).state = q.copyWith(clearBrand: true);
              },
            ),
          );
        }
        if (query.minPrice != null || query.maxPrice != null) {
          final a = query.minPrice?.toStringAsFixed(0) ?? '…';
          final b = query.maxPrice?.toStringAsFixed(0) ?? '…';
          chips.add(
            _DismissChip(
              label: 'Цена: $a–$b ₽',
              onDeleted: () {
                final q = ref.read(catalogQueryProvider);
                ref.read(catalogQueryProvider.notifier).state = q.copyWith(clearPrice: true);
              },
            ),
          );
        }
        if (query.inStockOnly) {
          chips.add(
            _DismissChip(
              label: 'В наличии',
              onDeleted: () {
                final q = ref.read(catalogQueryProvider);
                ref.read(catalogQueryProvider.notifier).state = q.copyWith(inStockOnly: false);
              },
            ),
          );
        }
        if (chips.isEmpty) return const SizedBox.shrink();
        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (var i = 0; i < chips.length; i++) ...[
                if (i > 0) const SizedBox(width: 6),
                chips[i],
              ],
            ],
          ),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}

class _DismissChip extends StatelessWidget {
  const _DismissChip({required this.label, required this.onDeleted});

  final String label;
  final VoidCallback onDeleted;

  @override
  Widget build(BuildContext context) {
    return InputChip(
      label: Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
      deleteIcon: const Icon(Icons.close_rounded, size: 16),
      onDeleted: onDeleted,
      backgroundColor: AppColors.chip,
      side: const BorderSide(color: AppColors.border),
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      visualDensity: VisualDensity.compact,
    );
  }
}

Future<void> _openFullFiltersSheet(BuildContext context, WidgetRef ref) async {
  final q0 = ref.read(catalogQueryProvider);
  final minCtrl = TextEditingController(text: q0.minPrice?.toStringAsFixed(0) ?? '');
  final maxCtrl = TextEditingController(text: q0.maxPrice?.toStringAsFixed(0) ?? '');

  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    backgroundColor: AppColors.background,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) {
      return DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.75,
        minChildSize: 0.45,
        maxChildSize: 0.92,
        builder: (context, scrollController) {
          return Consumer(
            builder: (context, ref, _) {
              final query = ref.watch(catalogQueryProvider);
              final brandsAsync = ref.watch(brandsProvider);

              return ListView(
                controller: scrollController,
                padding: EdgeInsets.fromLTRB(
                  AppSpacing.md,
                  0,
                  AppSpacing.md,
                  16 + MediaQuery.paddingOf(ctx).bottom,
                ),
                children: [
                  Text(
                    'Фильтры',
                    style: Theme.of(ctx).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Бренд и диапазон цены',
                    style: Theme.of(ctx).textTheme.bodySmall?.copyWith(color: AppColors.textTertiary),
                  ),
                  const SizedBox(height: 20),
                  brandsAsync.when(
                    data: (brands) {
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Бренд',
                            style: Theme.of(ctx).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 10),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              for (final b in brands)
                                FilterChip(
                                  label: Text(b.name),
                                  selected: query.brandId == b.id,
                                  selectedColor: AppColors.accent,
                                  checkmarkColor: Colors.white,
                                  labelStyle: TextStyle(
                                    color: query.brandId == b.id ? Colors.white : AppColors.textPrimary,
                                    fontWeight: FontWeight.w600,
                                    fontSize: 13,
                                  ),
                                  onSelected: (sel) {
                                    ref.read(catalogQueryProvider.notifier).state = query.copyWith(
                                      brandId: sel ? b.id : null,
                                      clearBrand: !sel,
                                    );
                                  },
                                ),
                            ],
                          ),
                        ],
                      );
                    },
                    loading: () => const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator())),
                    error: (e, _) => Text('Ошибка брендов: $e'),
                  ),
                  const SizedBox(height: 24),
                  Text(
                    'Цена, ₽',
                    style: Theme.of(ctx).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: minCtrl,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                            labelText: 'От',
                            filled: true,
                            fillColor: AppColors.surface,
                            border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(12))),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextField(
                          controller: maxCtrl,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                            labelText: 'До',
                            filled: true,
                            fillColor: AppColors.surface,
                            border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(12))),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 28),
                  Row(
                    children: [
                      Expanded(
                      child: OutlinedButton(
                        onPressed: () {
                            final q = ref.read(catalogQueryProvider);
                            ref.read(catalogQueryProvider.notifier).state = q.copyWith(
                              clearBrand: true,
                              clearPrice: true,
                              inStockOnly: false,
                            );
                            minCtrl.clear();
                            maxCtrl.clear();
                            Navigator.pop(ctx);
                          },
                          child: const Text('Сбросить всё'),
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
                            ref.read(catalogQueryProvider.notifier).state = ref
                                .read(catalogQueryProvider)
                                .copyWith(minPrice: minP, maxPrice: maxP);
                            Navigator.pop(ctx);
                          },
                          style: FilledButton.styleFrom(backgroundColor: AppColors.accent, foregroundColor: Colors.black),
                          child: const Text('Применить'),
                        ),
                      ),
                    ],
                  ),
                ],
              );
            },
          );
        },
      );
    },
  );
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
                  Text(
                    product.brandId.toUpperCase(),
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontSize: 11),
                  ),
                  const SizedBox(height: 4),
                  Text(product.name, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Text(
                    '${product.price.toStringAsFixed(0)} ₽',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
                  ),
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
