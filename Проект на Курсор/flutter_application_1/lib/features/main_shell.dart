import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/constants/app_colors.dart';
import '../core/constants/app_shadows.dart';

/// Нижняя навигация в стиле референса: чёрная панель и круглая оранжевая кнопка «Профиль» по центру.
class MainShell extends StatelessWidget {
  const MainShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  void _goBranch(int index) {
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }

  @override
  Widget build(BuildContext context) {
    final idx = navigationShell.currentIndex;

    return Scaffold(
      body: SafeArea(
        top: false,
        child: navigationShell,
      ),
      extendBody: true,
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: AppColors.background,
          boxShadow: AppShadows.navBar,
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 72,
            child: Stack(
              clipBehavior: Clip.none,
              alignment: Alignment.center,
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _NavSlot(
                        selected: idx == 0,
                        icon: Icons.home_outlined,
                        activeIcon: Icons.home_rounded,
                        label: 'Главная',
                        onTap: () => _goBranch(0),
                      ),
                      _NavSlot(
                        selected: idx == 1,
                        icon: Icons.grid_view_outlined,
                        activeIcon: Icons.grid_view_rounded,
                        label: 'Каталог',
                        onTap: () => _goBranch(1),
                      ),
                      const SizedBox(width: 56),
                      _NavSlot(
                        selected: idx == 3,
                        icon: Icons.shopping_bag_outlined,
                        activeIcon: Icons.shopping_bag_rounded,
                        label: 'Корзина',
                        onTap: () => _goBranch(3),
                      ),
                      _NavSlot(
                        selected: idx == 4,
                        icon: Icons.favorite_outline,
                        activeIcon: Icons.favorite_rounded,
                        label: 'Избранное',
                        onTap: () => _goBranch(4),
                      ),
                    ],
                  ),
                ),
                Positioned(
                  top: -18,
                  child: Material(
                    elevation: 6,
                    shadowColor: AppColors.accent.withValues(alpha: 0.45),
                    shape: const CircleBorder(),
                    color: AppColors.accent,
                    child: InkWell(
                      customBorder: const CircleBorder(),
                      onTap: () => _goBranch(2),
                      child: SizedBox(
                        width: 58,
                        height: 58,
                        child: Icon(
                          Icons.person_rounded,
                          color: idx == 2 ? Colors.white : Colors.white.withValues(alpha: 0.85),
                          size: 28,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NavSlot extends StatelessWidget {
  const _NavSlot({
    required this.selected,
    required this.icon,
    required this.activeIcon,
    required this.label,
    required this.onTap,
  });

  final bool selected;
  final IconData icon;
  final IconData activeIcon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = selected ? AppColors.accent : AppColors.textTertiary;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(selected ? activeIcon : icon, color: c, size: 24),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                color: c,
                letterSpacing: 0.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
