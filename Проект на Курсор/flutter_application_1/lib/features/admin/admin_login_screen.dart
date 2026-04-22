import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/router/safe_navigation.dart';

import '../../application/providers.dart';
import '../../core/constants/admin_constants.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/admin_theme.dart';

class AdminLoginScreen extends ConsumerStatefulWidget {
  const AdminLoginScreen({super.key});

  @override
  ConsumerState<AdminLoginScreen> createState() => _AdminLoginScreenState();
}

class _AdminLoginScreenState extends ConsumerState<AdminLoginScreen> {
  final _pin = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _pin.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final prefs = ref.read(localPrefsProvider);
    final stored = prefs.loadAdminPin();
    final expected = stored ?? AdminConstants.defaultPin;
    if (_pin.text.trim() == expected) {
      await ref.read(adminAuthProvider.notifier).setAuthenticated(true);
      setState(() => _error = null);
    } else {
      setState(() => _error = 'Неверный PIN');
    }
  }

  @override
  Widget build(BuildContext context) {
    final hasCustom = ref.read(localPrefsProvider).loadAdminPin() != null;

    return Scaffold(
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFFEEF2FF),
              Color(0xFFF8FAFC),
              Color(0xFFE0E7FF),
            ],
          ),
        ),
        child: SafeArea(
          child: Stack(
            children: [
              Align(
                alignment: Alignment.topLeft,
                child: IconButton(
                  icon: const Icon(Icons.arrow_back_rounded),
                  onPressed: () => popOrGo(context, fallback: '/profile'),
                  style: IconButton.styleFrom(foregroundColor: const Color(0xFF475569)),
                ),
              ),
              Center(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 420),
                    child: Material(
                      elevation: 8,
                      shadowColor: AdminTheme.primary.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(24),
                      child: Container(
                        padding: const EdgeInsets.all(28),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(24),
                          border: Border.all(color: AdminTheme.border),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(12),
                                  decoration: BoxDecoration(
                                    color: AdminTheme.primarySoft,
                                    borderRadius: BorderRadius.circular(16),
                                  ),
                                  child: const Icon(Icons.lock_outline_rounded, color: AdminTheme.primary, size: 28),
                                ),
                                const SizedBox(width: 16),
                                Expanded(
                                  child: Text(
                                    'Админ-панель',
                                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                                          fontWeight: FontWeight.w800,
                                          letterSpacing: -0.4,
                                          color: const Color(0xFF0F172A),
                                        ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Введите PIN',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(height: 10),
                            Text(
                              hasCustom
                                  ? 'Используется PIN из раздела «Система».'
                                  : 'Первый вход: PIN по умолчанию — смените в «Система» после входа.',
                              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                    color: const Color(0xFF64748B),
                                    height: 1.4,
                                  ),
                            ),
                            const SizedBox(height: AppSpacing.lg),
                            TextField(
                              controller: _pin,
                              obscureText: true,
                              keyboardType: TextInputType.visiblePassword,
                              autocorrect: false,
                              decoration: InputDecoration(
                                labelText: 'PIN',
                                errorText: _error,
                                prefixIcon: const Icon(Icons.pin_outlined),
                              ),
                              onSubmitted: (_) => _submit(),
                            ),
                            const SizedBox(height: AppSpacing.lg),
                            FilledButton.icon(
                              onPressed: _submit,
                              icon: const Icon(Icons.login_rounded, size: 20),
                              label: const Text('Войти'),
                            ),
                            const SizedBox(height: AppSpacing.md),
                            Text(
                              'Вход скрыт: удерживайте карточку профиля ~2 сек.',
                              textAlign: TextAlign.center,
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFF94A3B8)),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
