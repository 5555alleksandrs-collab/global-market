import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/router/safe_navigation.dart';
import '../../core/constants/app_spacing.dart';
import 'widgets/order_history_body.dart';

class OrdersScreen extends ConsumerWidget {
  const OrdersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => popOrGo(context),
        ),
        title: const Text('Мои заказы'),
      ),
      body: const OrderHistoryBody(
        padding: EdgeInsets.all(AppSpacing.md),
        showDocumentsHeader: false,
      ),
    );
  }
}
