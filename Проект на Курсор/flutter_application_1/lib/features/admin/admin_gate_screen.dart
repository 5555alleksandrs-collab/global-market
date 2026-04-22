import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../application/providers.dart';
import '../../core/theme/admin_theme.dart';
import 'admin_login_screen.dart';
import 'admin_shell.dart';

/// Если не авторизованы в админке — экран ввода PIN, иначе оболочка с разделами.
class AdminGateScreen extends ConsumerWidget {
  const AdminGateScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(adminAuthProvider);
    return Theme(
      data: AdminTheme.merge(Theme.of(context)),
      child: auth ? const AdminShell() : const AdminLoginScreen(),
    );
  }
}
