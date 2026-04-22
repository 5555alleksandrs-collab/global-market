import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../application/providers.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_shadows.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/domain/models/cart_item.dart';
import '../../core/domain/models/product.dart';
import 'price_display.dart';

class ProductCard extends ConsumerWidget {
  const ProductCard({
    super.key,
    required this.product,
    this.compact = false,
  });

  final Product product;
  final bool compact;

  Future<void> _quickAddToCart(WidgetRef ref) async {
    final v = product.variants.isEmpty
        ? null
        : product.variants.firstWhere((e) => e.inStock, orElse: () => product.variants.first);
    final price = product.effectivePriceForVariant(v);
    final item = CartItem(
      id: const Uuid().v4(),
      productId: product.id,
      variantId: v?.id,
      title: product.name,
      imageUrl: product.images.first,
      unitPrice: price,
      currency: product.currency,
      quantity: 1,
      variantLabel: v?.label,
      selectedAttributes: v?.attributes ?? const {},
    );
    await ref.read(cartProvider.notifier).addOrUpdate(item);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fav = ref.watch(favoritesProvider);
    final isFav = fav.contains(product.id);
    final canBuy = product.inStock && product.stockQuantity > 0;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: () => context.push('/product/${product.id}'),
        child: Ink(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AppColors.border.withValues(alpha: 0.55)),
            boxShadow: AppShadows.card,
          ),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.sm + 2),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(
                  child: Stack(
                    clipBehavior: Clip.antiAlias,
                    fit: StackFit.expand,
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(16),
                        child: CachedNetworkImage(
                          imageUrl: product.images.first,
                          fit: BoxFit.cover,
                          width: double.infinity,
                          height: double.infinity,
                          placeholder: (_, __) => Container(
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: [
                                  AppColors.chip,
                                  AppColors.surfaceElevated,
                                ],
                              ),
                            ),
                          ),
                          errorWidget: (_, __, ___) => const Icon(Icons.image_not_supported_outlined),
                        ),
                      ),
                      Positioned(
                        right: 6,
                        top: 6,
                        child: Material(
                          color: AppColors.surface.withValues(alpha: 0.92),
                          shape: const CircleBorder(),
                          elevation: 1,
                          shadowColor: Colors.black26,
                          child: IconButton(
                            visualDensity: VisualDensity.compact,
                            onPressed: () => ref.read(favoritesProvider.notifier).toggle(product.id),
                            icon: Icon(
                              isFav ? Icons.favorite_rounded : Icons.favorite_border_rounded,
                              size: 20,
                              color: isFav ? AppColors.danger : AppColors.textSecondary,
                            ),
                          ),
                        ),
                      ),
                      if (product.isNew)
                        Positioned(
                          left: 8,
                          top: 8,
                          child: _badge('Новинка', AppColors.textPrimary, AppColors.surface),
                        ),
                      if (product.hasDiscount)
                        Positioned(
                          left: 8,
                          bottom: 8,
                          child: _badge('Скидка', Colors.white, AppColors.accent),
                        ),
                      Positioned(
                        right: 6,
                        bottom: 6,
                        child: Material(
                          color: AppColors.accent,
                          shape: const CircleBorder(),
                          elevation: 2,
                          shadowColor: AppColors.accentGlow,
                          child: InkWell(
                            customBorder: const CircleBorder(),
                            onTap: canBuy
                                ? () async {
                                    await _quickAddToCart(ref);
                                    if (!context.mounted) return;
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(
                                        content: Text('Добавлено в корзину'),
                                        behavior: SnackBarBehavior.floating,
                                      ),
                                    );
                                  }
                                : null,
                            child: Padding(
                              padding: const EdgeInsets.all(10),
                              child: Icon(
                                Icons.add_rounded,
                                color: canBuy ? Colors.white : AppColors.textTertiary,
                                size: 22,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  product.brandId.toUpperCase(),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontSize: 10,
                        letterSpacing: 1.1,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textTertiary,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  product.name,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontSize: compact ? 14 : 15,
                        height: 1.2,
                        fontWeight: FontWeight.w600,
                      ),
                ),
                const SizedBox(height: 6),
                PriceDisplay(
                  price: product.price,
                  oldPrice: product.oldPrice,
                  currency: product.currency,
                  compact: compact,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _badge(String text, Color fg, Color bg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: bg.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.border.withValues(alpha: 0.5)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.25),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w800,
          letterSpacing: 0.3,
          color: fg,
        ),
      ),
    );
  }
}
