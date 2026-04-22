import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../application/providers.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/router/safe_navigation.dart';

class CodeAuthScreen extends ConsumerStatefulWidget {
  const CodeAuthScreen({super.key, required this.phone});

  final String phone;

  @override
  ConsumerState<CodeAuthScreen> createState() => _CodeAuthScreenState();
}

class _CodeAuthScreenState extends ConsumerState<CodeAuthScreen> {
  final _code = TextEditingController();

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _verify() async {
    final entered = _code.text.trim();
    if (entered != '1234') {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Неверный код. Попробуйте 1234')),
      );
      return;
    }
    await ref.read(authProvider.notifier).signInWithPhone(widget.phone);
    if (!mounted) return;
    context.go('/profile');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => popOrGo(context, fallback: '/auth/phone'),
        ),
        title: const Text('Код'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Код для ${widget.phone}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 10),
            Text(
              'Введите 1234 для mock-входа.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: AppSpacing.lg),
            TextField(
              controller: _code,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Код',
              ),
            ),
            const Spacer(),
            FilledButton(
              onPressed: _verify,
              child: const Text('Подтвердить'),
            ),
            const SizedBox(height: AppSpacing.md),
          ],
        ),
      ),
    );
  }
}
