import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../application/providers.dart';
import '../../common/widgets/app_states.dart';
import '../../common/widgets/price_display.dart';
import '../../core/constants/app_colors.dart';
import '../../core/router/safe_navigation.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/domain/models/cart_item.dart';
import '../../core/domain/models/product.dart';
import '../../core/domain/models/product_variant.dart';

class ProductScreen extends ConsumerStatefulWidget {
  const ProductScreen({super.key, required this.productId});

  final String productId;

  @override
  ConsumerState<ProductScreen> createState() => _ProductScreenState();
}

class _ProductScreenState extends ConsumerState<ProductScreen> {
  final _pageController = PageController();
  int _imageIndex = 0;

  /// Если null — берём дефолтный вариант из [Product].
  ProductVariant? _userVariant;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  ProductVariant? _resolvedVariant(Product p) {
    if (p.variants.isEmpty) return null;
    if (_userVariant != null) return _userVariant;
    return p.variants.firstWhere(
      (e) => e.inStock,
      orElse: () => p.variants.first,
    );
  }

  Future<void> _addToCart(Product p) async {
    final v = _resolvedVariant(p);
    final price = p.effectivePriceForVariant(v);
    final item = CartItem(
      id: const Uuid().v4(),
      productId: p.id,
      variantId: v?.id,
      title: p.name,
      imageUrl: p.images.first,
      unitPrice: price,
      currency: p.currency,
      quantity: 1,
      variantLabel: v?.label,
      selectedAttributes: v?.attributes ?? const {},
    );
    await ref.read(cartProvider.notifier).addOrUpdate(item);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Добавлено в корзину')),
    );
  }

  Future<void> _buyNow(Product p) async {
    await _addToCart(p);
    if (!mounted) return;
    context.push('/checkout');
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(productProvider(widget.productId));

    return async.when(
      data: (p) {
        if (p == null) {
          return Scaffold(
            appBar: AppBar(leading: IconButton(icon: const Icon(Icons.arrow_back_rounded), onPressed: () => popOrGo(context))),
            body: const AppEmptyState(
              title: 'Товар не найден',
              subtitle: 'Возможно, он был удалён из каталога.',
            ),
          );
        }
        final v = _resolvedVariant(p);
        final inStock = p.inStock && (v?.inStock ?? true);

        return Scaffold(
          appBar: AppBar(
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_rounded),
              onPressed: () => popOrGo(context),
            ),
            actions: [
              IconButton(
                tooltip: 'Избранное',
                onPressed: () => ref.read(favoritesProvider.notifier).toggle(p.id),
                icon: Icon(
                  ref.watch(favoritesProvider).contains(p.id)
                      ? Icons.favorite_rounded
                      : Icons.favorite_border_rounded,
                  color: ref.watch(favoritesProvider).contains(p.id) ? AppColors.danger : null,
                ),
              ),
            ],
          ),
          bottomNavigationBar: SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.md, 8, AppSpacing.md, AppSpacing.md),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: !inStock ? null : () => _addToCart(p),
                      child: const Text('В корзину'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: !inStock ? null : () => _buyNow(p),
                      child: const Text('Купить сейчас'),
                    ),
                  ),
                ],
              ),
            ),
          ),
          body: ListView(
            padding: const EdgeInsets.only(bottom: 24),
            children: [
              SizedBox(
                height: 420,
                child: Stack(
                  children: [
                    PageView.builder(
                      controller: _pageController,
                      itemCount: p.images.length,
                      onPageChanged: (i) => setState(() => _imageIndex = i),
                      itemBuilder: (context, i) {
                        final url = (v?.imageOverride != null && i == 0) ? v!.imageOverride! : p.images[i];
                        return CachedNetworkImage(
                          imageUrl: url,
                          fit: BoxFit.cover,
                          placeholder: (_, __) => Container(color: AppColors.chip),
                        );
                      },
                    ),
                    Positioned(
                      bottom: 12,
                      left: 0,
                      right: 0,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: List.generate(
                          p.images.length,
                          (i) => AnimatedContainer(
                            duration: const Duration(milliseconds: 200),
                            margin: const EdgeInsets.symmetric(horizontal: 3),
                            height: 6,
                            width: i == _imageIndex ? 18 : 6,
                            decoration: BoxDecoration(
                              color: i == _imageIndex ? AppColors.textPrimary : Colors.white.withValues(alpha: 0.55),
                              borderRadius: BorderRadius.circular(999),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      p.brandId.toUpperCase(),
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            letterSpacing: 0.8,
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    const SizedBox(height: 6),
                    Text(p.name, style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: AppColors.chip,
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            p.categoryId.replaceAll('_', ' '),
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Icon(Icons.star_rounded, color: Colors.amber.shade700, size: 20),
                        const SizedBox(width: 4),
                        Text('${p.rating.toStringAsFixed(1)}', style: Theme.of(context).textTheme.titleMedium),
                        const Spacer(),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: inStock ? AppColors.success.withValues(alpha: 0.12) : AppColors.danger.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            inStock ? 'В наличии' : 'Нет в наличии',
                            style: TextStyle(
                              color: inStock ? AppColors.success : AppColors.danger,
                              fontWeight: FontWeight.w700,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    PriceDisplay(
                      price: p.effectivePriceForVariant(v),
                      oldPrice: p.effectiveOldPriceForVariant(v),
                      currency: p.currency,
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    if (p.variants.isNotEmpty) ...[
                      Text('Варианты', style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 10),
                      DropdownButtonFormField<ProductVariant>(
                        value: v,
                        decoration: const InputDecoration(labelText: 'Комплектация'),
                        items: p.variants
                            .map(
                              (e) => DropdownMenuItem(
                                value: e,
                                child: Text(
                                  e.label,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            )
                            .toList(),
                        onChanged: !inStock
                            ? null
                            : (nv) {
                                setState(() => _userVariant = nv);
                              },
                      ),
                      const SizedBox(height: AppSpacing.lg),
                    ],
                    Text('Описание', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Text(p.description, style: Theme.of(context).textTheme.bodyLarge),
                    const SizedBox(height: AppSpacing.lg),
                    Text('Характеристики', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 10),
                    ..._specRows(p),
                    const SizedBox(height: AppSpacing.sm),
                    Text('SKU: ${v?.sku ?? p.sku}', style: Theme.of(context).textTheme.bodyMedium),
                  ],
                ),
              ),
            ],
          ),
        );
      },
      loading: () => const Scaffold(body: AppLoading(message: 'Загрузка товара…')),
      error: (e, _) => Scaffold(
        appBar: AppBar(leading: IconButton(icon: const Icon(Icons.arrow_back_rounded), onPressed: () => popOrGo(context))),
        body: AppErrorState(
          message: 'Не удалось загрузить товар',
          onRetry: () => ref.invalidate(productProvider(widget.productId)),
        ),
      ),
    );
  }

  List<Widget> _specRows(Product p) {
    final map = {
      ...p.specifications.toDisplayMap(),
      ...p.specificationsMap,
    };
    if (map.isEmpty) {
      return const [
        Text('Подробные характеристики появятся после подключения API.'),
      ];
    }
    return map.entries
        .map(
          (e) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 140,
                  child: Text(
                    e.key,
                    style: const TextStyle(color: AppColors.textSecondary, fontWeight: FontWeight.w600),
                  ),
                ),
                Expanded(child: Text(e.value)),
              ],
            ),
          ),
        )
        .toList();
  }
}
