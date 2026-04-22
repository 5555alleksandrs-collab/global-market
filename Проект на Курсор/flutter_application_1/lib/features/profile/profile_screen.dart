import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../application/providers.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  DateTime? _profileCardPressStart;

  @override
  Widget build(BuildContext context) {
    final phone = ref.watch(authProvider);
    final user = ref.watch(userProfileProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Профиль')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          Listener(
            behavior: HitTestBehavior.opaque,
            onPointerDown: (_) => _profileCardPressStart = DateTime.now(),
            onPointerUp: (_) {
              final start = _profileCardPressStart;
              _profileCardPressStart = null;
              if (start == null) return;
              final held = DateTime.now().difference(start);
              if (held >= const Duration(seconds: 2)) {
                HapticFeedback.mediumImpact();
                context.push('/admin');
              }
            },
            onPointerCancel: (_) => _profileCardPressStart = null,
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: AppColors.border),
              ),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 28,
                    backgroundColor: AppColors.chip,
                    child: Text(
                      _initial(user?.name),
                      style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          user?.name ?? 'Пользователь',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Global Market',
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.accent),
                        ),
                        if (phone != null && phone.isNotEmpty)
                          Text(phone, style: Theme.of(context).textTheme.bodyMedium),
                        if ((user?.email ?? '').isNotEmpty)
                          Text(user?.email ?? '', style: Theme.of(context).textTheme.bodyMedium),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          if (phone == null || phone.isEmpty)
            OutlinedButton.icon(
              onPressed: () => context.push('/auth/phone'),
              icon: const Icon(Icons.phone_android_rounded),
              label: const Text('Добавить телефон для заказов'),
            )
          else
            OutlinedButton(
              onPressed: () async {
                await ref.read(authProvider.notifier).signOut();
              },
              child: const Text('Убрать телефон из профиля'),
            ),
          const SizedBox(height: AppSpacing.md),
          FilledButton.tonal(
            onPressed: () async {
              await ref.read(appSessionProvider.notifier).signOut();
              if (!context.mounted) return;
              context.go('/auth/login');
            },
            child: const Text('Выйти из аккаунта'),
          ),
          const SizedBox(height: AppSpacing.lg),
          _tile(
            context,
            icon: Icons.info_outline_rounded,
            title: 'О компании и правила',
            subtitle: 'Гарантия и режим работы',
            onTap: () => context.push('/company'),
          ),
          _tile(
            context,
            icon: Icons.receipt_long_rounded,
            title: 'Мои заказы',
            subtitle: 'История и статусы',
            onTap: () => context.push('/orders'),
          ),
          _tile(
            context,
            icon: Icons.favorite_rounded,
            title: 'Избранное',
            subtitle: 'Сохранённые товары',
            onTap: () => context.go('/favorites'),
          ),
          _tile(
            context,
            icon: Icons.location_on_outlined,
            title: 'Адреса доставки',
            subtitle: 'Скоро: синхронизация с аккаунтом',
            onTap: () {},
          ),
          _tile(
            context,
            icon: Icons.settings_rounded,
            title: 'Настройки',
            subtitle: 'Уведомления и предпочтения',
            onTap: () => context.push('/settings'),
          ),
        ],
      ),
    );
  }

  Widget _tile(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Ink(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              children: [
                Icon(icon, color: AppColors.accent),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 2),
                      Text(subtitle, style: Theme.of(context).textTheme.bodyMedium),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right_rounded, color: AppColors.textSecondary),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String _initial(String? name) {
  final n = name?.trim();
  if (n == null || n.isEmpty) return 'G';
  return n.substring(0, 1).toUpperCase();
}
