import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/app_spacing.dart';
import '../../core/theme/admin_theme.dart';
import 'admin_all_products_screen.dart';
import 'admin_category_browser_screen.dart';
import 'admin_dashboard_screen.dart';
import 'admin_orders_screen.dart';
import 'admin_system_screen.dart';

enum _AdminSection { dashboard, orders, categories, allProducts, system }

/// Оболочка админки: боковое меню и разделы.
class AdminShell extends ConsumerStatefulWidget {
  const AdminShell({super.key});

  @override
  ConsumerState<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends ConsumerState<AdminShell> {
  _AdminSection _section = _AdminSection.dashboard;

  String get _title {
    switch (_section) {
      case _AdminSection.dashboard:
        return 'Обзор';
      case _AdminSection.orders:
        return 'Заказы';
      case _AdminSection.categories:
        return 'По категориям';
      case _AdminSection.allProducts:
        return 'Все товары';
      case _AdminSection.system:
        return 'Система';
    }
  }

  void _go(_AdminSection s) {
    setState(() => _section = s);
    Navigator.of(context).maybePop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_title),
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(height: 1, thickness: 1, color: AdminTheme.border),
        ),
      ),
      drawer: _AdminDrawer(
        section: _section,
        onSelect: _go,
      ),
      floatingActionButton: (_section == _AdminSection.allProducts || _section == _AdminSection.dashboard)
          ? FloatingActionButton.extended(
              onPressed: () => context.push('/admin/product'),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Новый товар'),
            )
          : null,
      body: IndexedStack(
        index: _section.index,
        children: [
          AdminDashboardScreen(
            onOpenCategories: () => setState(() => _section = _AdminSection.categories),
            onOpenAllProducts: () => setState(() => _section = _AdminSection.allProducts),
            onOpenOrders: () => setState(() => _section = _AdminSection.orders),
            onOpenSystem: () => setState(() => _section = _AdminSection.system),
            onNewProduct: () => context.push('/admin/product'),
          ),
          const AdminOrdersScreen(),
          const AdminCategoryBrowserScreen(),
          const AdminAllProductsScreen(),
          const AdminSystemScreen(),
        ],
      ),
    );
  }
}

class _AdminDrawer extends StatelessWidget {
  const _AdminDrawer({
    required this.section,
    required this.onSelect,
  });

  final _AdminSection section;
  final void Function(_AdminSection) onSelect;

  @override
  Widget build(BuildContext context) {
    return Drawer(
      backgroundColor: AdminTheme.sidebarBg,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Icon(Icons.dashboard_customize_rounded, color: Colors.white, size: 28),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Каталог',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.3,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Управление товарами',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AdminTheme.sidebarMuted),
                  ),
                ],
              ),
            ),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: Divider(color: Color(0xFF334155), height: 1),
            ),
            const SizedBox(height: 8),
            _DrawerTile(
              icon: Icons.insights_rounded,
              label: 'Обзор',
              selected: section == _AdminSection.dashboard,
              onTap: () => onSelect(_AdminSection.dashboard),
            ),
            _DrawerTile(
              icon: Icons.receipt_long_rounded,
              label: 'Заказы',
              selected: section == _AdminSection.orders,
              onTap: () => onSelect(_AdminSection.orders),
            ),
            _DrawerTile(
              icon: Icons.folder_open_rounded,
              label: 'По категориям',
              selected: section == _AdminSection.categories,
              onTap: () => onSelect(_AdminSection.categories),
            ),
            _DrawerTile(
              icon: Icons.inventory_2_outlined,
              label: 'Все товары',
              selected: section == _AdminSection.allProducts,
              onTap: () => onSelect(_AdminSection.allProducts),
            ),
            _DrawerTile(
              icon: Icons.tune_rounded,
              label: 'Система',
              selected: section == _AdminSection.system,
              onTap: () => onSelect(_AdminSection.system),
            ),
            const Spacer(),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: Divider(color: Color(0xFF334155), height: 1),
            ),
            ListTile(
              leading: Icon(Icons.storefront_outlined, color: Colors.white.withValues(alpha: 0.85)),
              title: Text(
                'В магазин',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.92),
                  fontWeight: FontWeight.w600,
                ),
              ),
              onTap: () {
                Scaffold.of(context).closeDrawer();
                context.go('/home');
              },
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

class _DrawerTile extends StatelessWidget {
  const _DrawerTile({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final bg = selected ? const Color(0xFF334155) : Colors.transparent;
    final fg = selected ? Colors.white : AdminTheme.sidebarMuted;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 2),
      child: Material(
        color: bg,
        borderRadius: BorderRadius.circular(12),
        child: ListTile(
          leading: Icon(icon, color: selected ? AdminTheme.primary : fg, size: 22),
          title: Text(
            label,
            style: TextStyle(
              color: selected ? Colors.white : fg,
              fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
            ),
          ),
          selected: selected,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          onTap: onTap,
        ),
      ),
    );
  }
}
