import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../application/providers.dart';
import '../../core/router/safe_navigation.dart';
import '../../common/widgets/app_states.dart';
import '../../common/widgets/product_card.dart';
import '../../core/constants/app_spacing.dart';

class CategoryScreen extends ConsumerWidget {
  const CategoryScreen({super.key, required this.categoryId});

  final String categoryId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(allProductsProvider);
    final cats = ref.watch(categoriesProvider);

    final title = cats.when(
      data: (list) {
        for (final c in list) {
          if (c.id == categoryId) return c.name;
        }
        return 'Категория';
      },
      loading: () => 'Категория',
      error: (_, __) => 'Категория',
    );

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => popOrGo(context),
        ),
      ),
      body: async.when(
        data: (all) {
          final filtered = all.where((p) => p.categoryId == categoryId).toList();
          if (filtered.isEmpty) {
            return const AppEmptyState(
              title: 'Товары не найдены',
              subtitle: 'Попробуйте другую категорию.',
            );
          }
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
        },
        loading: () => const AppLoading(),
        error: (e, _) => AppErrorState(
          message: 'Ошибка загрузки',
          onRetry: () => ref.invalidate(allProductsProvider),
        ),
      ),
    );
  }
}
