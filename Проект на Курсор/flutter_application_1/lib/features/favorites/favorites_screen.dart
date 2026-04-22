import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../application/providers.dart';
import '../../common/widgets/app_states.dart';
import '../../common/widgets/product_card.dart';
import '../../core/domain/models/product.dart';

final favoriteProductsProvider = Provider<AsyncValue<List<Product>>>((ref) {
  final ids = ref.watch(favoritesProvider);
  final products = ref.watch(allProductsProvider);
  return products.when(
    data: (all) {
      final map = {for (final p in all) p.id: p};
      final list = ids.map((id) => map[id]).whereType<Product>().toList();
      return AsyncValue.data(list);
    },
    loading: () => const AsyncValue.loading(),
    error: (e, st) => AsyncValue<List<Product>>.error(e, st),
  );
});

class FavoritesScreen extends ConsumerWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(favoriteProductsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Избранное')),
      body: async.when(
        data: (list) {
          if (list.isEmpty) {
            return AppEmptyState(
              title: 'Нет избранных товаров',
              subtitle: 'Нажмите на сердечко на карточке товара.',
              actionLabel: 'В каталог',
              onAction: () => context.go('/catalog'),
              icon: Icons.favorite_border_rounded,
            );
          }
          return GridView.builder(
            padding: const EdgeInsets.all(16),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 0.62,
            ),
            itemCount: list.length,
            itemBuilder: (context, i) => ProductCard(product: list[i]),
          );
        },
        loading: () => const AppLoading(),
        error: (e, _) => AppErrorState(
          message: 'Ошибка',
          onRetry: () => ref.invalidate(allProductsProvider),
        ),
      ),
    );
  }
}
