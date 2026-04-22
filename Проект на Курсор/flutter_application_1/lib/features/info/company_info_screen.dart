import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';

/// Правила покупки, гарантия и контакты Global Market.
class CompanyInfoScreen extends StatelessWidget {
  const CompanyInfoScreen({super.key});

  static const telegramUrl = 'https://t.me/globalmarket_opt';

  Future<void> _openTelegram() async {
    final uri = Uri.parse(telegramUrl);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('О компании'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          Text(
            'Global Market',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.5,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Оптовая продажа техники и аксессуаров. Работаем по всему миру, гарантируем отгрузку и широкий ассортимент.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppColors.textSecondary,
                  height: 1.45,
                ),
          ),
          const SizedBox(height: AppSpacing.lg),
          _SectionCard(
            icon: Icons.verified_user_outlined,
            title: 'Гарантия',
            child: Text(
              'Гарантия действует 7 дней с даты покупки на производственные дефекты. '
              'Для косметики — только на неактивированный товар.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.45),
            ),
          ),
          _SectionCard(
            icon: Icons.schedule_rounded,
            title: 'Режим работы',
            child: Text(
              'Понедельник — воскресенье, с 12:00 до 20:00.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.45),
            ),
          ),
          _SectionCard(
            icon: Icons.local_shipping_outlined,
            title: 'Выдача заказов',
            child: Text(
              'Товар выдаётся в любое время в часы работы.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.45),
            ),
          ),
          _SectionCard(
            icon: Icons.telegram,
            title: 'Связь и заказы',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Telegram: @globalmarketopt',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: AppSpacing.sm),
                FilledButton.icon(
                  onPressed: _openTelegram,
                  icon: const Icon(Icons.open_in_new_rounded, size: 18),
                  label: const Text('Открыть канал в Telegram'),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            'Спасибо, что выбираете Global Market.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textTertiary),
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({
    required this.icon,
    required this.title,
    required this.child,
  });

  final IconData icon;
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: AppColors.accent, size: 22),
                const SizedBox(width: 10),
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
                ),
              ],
            ),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }
}
