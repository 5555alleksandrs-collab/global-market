import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../application/providers.dart';
import '../../core/constants/admin_constants.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/router/safe_navigation.dart';

/// Системные действия: PIN, сброс каталога, выход из админки.
class AdminSystemScreen extends ConsumerStatefulWidget {
  const AdminSystemScreen({super.key});

  @override
  ConsumerState<AdminSystemScreen> createState() => _AdminSystemScreenState();
}

class _AdminSystemScreenState extends ConsumerState<AdminSystemScreen> {
  final _newPin = TextEditingController();
  final _repeatPin = TextEditingController();
  String? _pinError;

  @override
  void dispose() {
    _newPin.dispose();
    _repeatPin.dispose();
    super.dispose();
  }

  Future<void> _savePin() async {
    final a = _newPin.text.trim();
    final b = _repeatPin.text.trim();
    if (a.length < AdminConstants.minPinLength) {
      setState(() => _pinError = 'Минимум ${AdminConstants.minPinLength} символов');
      return;
    }
    if (a != b) {
      setState(() => _pinError = 'Коды не совпадают');
      return;
    }
    await ref.read(localPrefsProvider).saveAdminPin(a);
    setState(() {
      _pinError = null;
      _newPin.clear();
      _repeatPin.clear();
    });
    if (mounted) {
      HapticFeedback.mediumImpact();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Новый PIN сохранён')));
    }
  }

  Future<void> _resetSeed() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Сбросить каталог?'),
        content: const Text('Все правки будут заменены начальным набором товаров.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Отмена')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Сбросить')),
        ],
      ),
    );
    if (ok == true && mounted) {
      await ref.read(adminCatalogServiceProvider).resetCatalogToSeed();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Каталог восстановлен')));
      }
    }
  }

  Future<void> _logout() async {
    await ref.read(adminAuthProvider.notifier).signOut();
    if (mounted) popOrGo(context, fallback: '/profile');
  }

  @override
  Widget build(BuildContext context) {
    final hasCustom = ref.watch(localPrefsProvider).loadAdminPin() != null;

    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        Text(
          'Доступ',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 8),
        Text(
          hasCustom
              ? 'Используется ваш PIN. Сброс PIN невозможен из приложения — очистите данные приложения в настройках ОС.'
              : 'Сейчас действует PIN по умолчанию. Задайте свой ниже.',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textSecondary),
        ),
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: _newPin,
          obscureText: true,
          decoration: InputDecoration(
            labelText: 'Новый PIN (мин. ${AdminConstants.minPinLength})',
            errorText: _pinError,
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        TextField(
          controller: _repeatPin,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Повтор PIN'),
          onSubmitted: (_) => _savePin(),
        ),
        const SizedBox(height: AppSpacing.md),
        FilledButton(
          onPressed: _savePin,
          child: const Text('Сохранить PIN'),
        ),
        const SizedBox(height: AppSpacing.xl),
        Text(
          'Каталог',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: _resetSeed,
          icon: const Icon(Icons.restore_rounded),
          label: const Text('Восстановить начальный набор товаров'),
        ),
        const SizedBox(height: AppSpacing.xl),
        Text(
          'Сессия',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 12),
        FilledButton.tonal(
          onPressed: _logout,
          child: const Text('Выйти из админ-панели'),
        ),
        const SizedBox(height: AppSpacing.lg),
        Text(
          'Вход в админку скрыт: удерживайте карточку профиля на экране «Профиль» около 2 секунд.',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textTertiary),
        ),
      ],
    );
  }
}
