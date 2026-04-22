import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../application/providers.dart';
import '../../core/domain/models/order.dart';
import '../../core/theme/admin_theme.dart';

/// Главная админки: краткая статистика и быстрые действия.
class AdminDashboardScreen extends ConsumerWidget {
  const AdminDashboardScreen({
    super.key,
    required this.onOpenCategories,
    required this.onOpenAllProducts,
    required this.onOpenOrders,
    required this.onOpenSystem,
    required this.onNewProduct,
  });

  final VoidCallback onOpenCategories;
  final VoidCallback onOpenAllProducts;
  final VoidCallback onOpenOrders;
  final VoidCallback onOpenSystem;
  final VoidCallback onNewProduct;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final products = ref.watch(allProductsProvider);
    final categories = ref.watch(categoriesProvider);
    final orders = ref.watch(ordersProvider);
    final newOrders = orders.where((o) => o.status == OrderStatus.newOrder).length;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        Text(
          'Сводка',
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
                color: const Color(0xFF0F172A),
              ),
        ),
        const SizedBox(height: 8),
        Text(
          'Каталог хранится только на этом устройстве.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: const Color(0xFF64748B),
              ),
        ),
        const SizedBox(height: 20),
        if (newOrders > 0) ...[
          Material(
            color: AdminTheme.primarySoft,
            borderRadius: BorderRadius.circular(14),
            child: InkWell(
              borderRadius: BorderRadius.circular(14),
              onTap: onOpenOrders,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                child: Row(
                  children: [
                    Icon(Icons.notifications_active_rounded, color: AdminTheme.primary, size: 24),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        '$newOrders новых заказов — открыть список',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: const Color(0xFF0F172A),
                              fontWeight: FontWeight.w600,
                            ),
                      ),
                    ),
                    Icon(Icons.chevron_right_rounded, color: AdminTheme.primary),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
        ],
        products.when(
          data: (list) {
            final inStock = list.where((e) => e.inStock && e.stockQuantity > 0).length;
            final outOfStock = list.where((e) => e.stockQuantity <= 0).length;
            final lowStock = list.where((e) => e.stockQuantity > 0 && e.stockQuantity < 5).length;
            return categories.when(
              data: (cats) {
                return Column(
                  children: [
                    LayoutBuilder(
                      builder: (context, c) {
                        final w = c.maxWidth;
                        final cross = w >= 520 ? 4 : 2;
                        return GridView.count(
                          crossAxisCount: cross,
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          mainAxisSpacing: 12,
                          crossAxisSpacing: 12,
                          childAspectRatio: w >= 520 ? 1.35 : 1.5,
                          children: [
                            _StatCard(
                              icon: Icons.inventory_2_outlined,
                              label: 'Товаров',
                              value: '${list.length}',
                              accent: AdminTheme.primary,
                              onTap: onOpenAllProducts,
                            ),
                            _StatCard(
                              icon: Icons.check_circle_outline,
                              label: 'В наличии',
                              value: '$inStock',
                              accent: AdminTheme.success,
                              onTap: onOpenAllProducts,
                            ),
                            _StatCard(
                              icon: Icons.warning_amber_rounded,
                              label: 'Мало остатка',
                              value: '$lowStock',
                              subtitle: '< 5 шт.',
                              accent: AdminTheme.warning,
                              onTap: onOpenAllProducts,
                            ),
                            _StatCard(
                              icon: Icons.folder_outlined,
                              label: 'Категорий',
                              value: '${cats.length}',
                              accent: const Color(0xFF7C3AED),
                              onTap: onOpenCategories,
                            ),
                          ],
                        );
                      },
                    ),
                    if (outOfStock > 0) ...[
                      const SizedBox(height: 12),
                      Material(
                        color: const Color(0xFFFFF7ED),
                        borderRadius: BorderRadius.circular(14),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(14),
                          onTap: onOpenAllProducts,
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                            child: Row(
                              children: [
                                Icon(Icons.inventory_outlined, color: AdminTheme.warning, size: 22),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    '$outOfStock без остатка — откройте список и пополните или снимите с витрины.',
                                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                          color: const Color(0xFF9A3412),
                                          height: 1.35,
                                        ),
                                  ),
                                ),
                                const Icon(Icons.chevron_right_rounded, color: Color(0xFF9A3412)),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ],
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (_, __) => const SizedBox.shrink(),
            );
          },
          loading: () => const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator())),
          error: (e, _) => Text('Ошибка: $e'),
        ),
        const SizedBox(height: 28),
        Text(
          'Быстрые действия',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
                color: const Color(0xFF0F172A),
              ),
        ),
        const SizedBox(height: 12),
        _ActionTile(
          icon: Icons.receipt_long_rounded,
          title: 'Заказы',
          subtitle: '${orders.length} всего · $newOrders новых',
          accent: AdminTheme.primary,
          onTap: onOpenOrders,
        ),
        _ActionTile(
          icon: Icons.create_new_folder_outlined,
          title: 'По категориям',
          subtitle: 'Папки: iPhone, MacBook, Samsung…',
          accent: AdminTheme.primary,
          onTap: onOpenCategories,
        ),
        _ActionTile(
          icon: Icons.view_list_rounded,
          title: 'Все товары',
          subtitle: 'Поиск, остатки, редактирование',
          accent: const Color(0xFF0EA5E9),
          onTap: onOpenAllProducts,
        ),
        _ActionTile(
          icon: Icons.add_circle_outline,
          title: 'Новый товар',
          subtitle: 'Создать карточку с нуля',
          accent: AdminTheme.success,
          onTap: onNewProduct,
        ),
        _ActionTile(
          icon: Icons.security_rounded,
          title: 'Система и доступ',
          subtitle: 'PIN, сброс каталога, выход',
          accent: const Color(0xFF64748B),
          onTap: onOpenSystem,
        ),
      ],
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.accent,
    required this.onTap,
    this.subtitle,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color accent;
  final VoidCallback onTap;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AdminTheme.surface,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Ink(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: AdminTheme.border),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                accent.withValues(alpha: 0.07),
                Colors.white,
              ],
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: accent, size: 22),
              ),
              const SizedBox(height: 10),
              Text(
                label,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: const Color(0xFF64748B),
                      fontWeight: FontWeight.w500,
                    ),
              ),
              if (subtitle != null)
                Text(
                  subtitle!,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(color: const Color(0xFF94A3B8)),
                ),
              const SizedBox(height: 4),
              Text(
                value,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                      color: const Color(0xFF0F172A),
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.accent,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color accent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: AdminTheme.surface,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Ink(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AdminTheme.border),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: accent.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(icon, color: accent, size: 24),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        subtitle,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFF64748B)),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right_rounded, color: Color(0xFF94A3B8)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
