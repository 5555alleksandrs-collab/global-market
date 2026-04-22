import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';

import '../../application/providers.dart';
import '../../core/router/safe_navigation.dart';
import '../../core/domain/models/user.dart';
import '../../common/widgets/app_states.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/domain/models/order.dart';

class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({super.key});

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _email = TextEditingController();
  final _comment = TextEditingController();
  final _address = TextEditingController();

  String _delivery = 'Курьер';
  String _payment = 'Картой онлайн (скоро)';

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _email.dispose();
    _comment.dispose();
    _address.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final items = ref.read(cartProvider);
    if (items.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Корзина пуста')),
      );
      return;
    }
    if (_name.text.trim().isEmpty || _phone.text.trim().isEmpty || _address.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Заполните имя, телефон и адрес')),
      );
      return;
    }

    final total = items.fold<double>(0, (s, e) => s + e.lineTotal);
    final order = Order(
      id: const Uuid().v4(),
      number: DateTime.now().millisecondsSinceEpoch.toString().substring(5),
      createdAt: DateTime.now(),
      items: List.of(items),
      total: total,
      currency: items.first.currency,
      status: OrderStatus.newOrder,
      deliveryMethod: _delivery,
      paymentMethod: _payment,
      addressLine: _address.text.trim(),
    );

    await ref.read(ordersProvider.notifier).addOrder(order);
    await ref.read(cartProvider.notifier).clear();

    final user = ref.read(userProfileProvider);
    if (user != null) {
      final updated = User(
        id: user.id,
        name: _name.text.trim(),
        phone: _phone.text.trim(),
        email: _email.text.trim().isEmpty ? null : _email.text.trim(),
        addresses: user.addresses,
      );
      await ref.read(localPrefsProvider).saveUserJson(jsonEncode(updated.toJson()));
      ref.invalidate(userProfileProvider);
    }

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Заказ оформлен (mock)')),
    );
    context.go('/orders');
  }

  @override
  Widget build(BuildContext context) {
    final items = ref.watch(cartProvider);
    final fmt = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);
    final total = items.fold<double>(0, (s, e) => s + e.lineTotal);

    if (items.isEmpty) {
      return Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_rounded),
            onPressed: () => popOrGo(context),
          ),
          title: const Text('Оформление'),
        ),
        body: AppEmptyState(
          title: 'Корзина пуста',
          subtitle: 'Добавьте товары, чтобы оформить заказ.',
          actionLabel: 'В каталог',
          onAction: () => context.go('/catalog'),
          icon: Icons.shopping_bag_outlined,
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => popOrGo(context),
        ),
        title: const Text('Оформление'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          Text('Контакты', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          TextField(
            controller: _name,
            decoration: const InputDecoration(labelText: 'Имя *'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _phone,
            keyboardType: TextInputType.phone,
            decoration: const InputDecoration(labelText: 'Телефон *'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(labelText: 'Email (необязательно)'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _comment,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'Комментарий к заказу'),
          ),
          const SizedBox(height: AppSpacing.lg),
          Text('Доставка', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            value: _delivery,
            decoration: const InputDecoration(labelText: 'Способ доставки'),
            items: const [
              DropdownMenuItem(value: 'Курьер', child: Text('Курьер')),
              DropdownMenuItem(value: 'Самовывоз', child: Text('Самовывоз')),
              DropdownMenuItem(value: 'Пункт выдачи', child: Text('Пункт выдачи')),
            ],
            onChanged: (v) => setState(() => _delivery = v ?? 'Курьер'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _address,
            maxLines: 2,
            decoration: const InputDecoration(labelText: 'Адрес доставки *'),
          ),
          const SizedBox(height: AppSpacing.lg),
          Text('Оплата', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            value: _payment,
            decoration: const InputDecoration(labelText: 'Способ оплаты'),
            items: const [
              DropdownMenuItem(
                value: 'Картой онлайн (скоро)',
                child: Text('Картой онлайн (скоро)'),
              ),
              DropdownMenuItem(value: 'При получении', child: Text('При получении')),
            ],
            onChanged: (v) => setState(() => _payment = v ?? 'Картой онлайн (скоро)'),
          ),
          const SizedBox(height: AppSpacing.lg),
          Text('Итог', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              children: [
                for (final it in items)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      children: [
                        Expanded(child: Text('${it.title} × ${it.quantity}')),
                        Text(fmt.format(it.lineTotal)),
                      ],
                    ),
                  ),
                const Divider(height: 22),
                Row(
                  children: [
                    Text('Сумма', style: Theme.of(context).textTheme.titleMedium),
                    const Spacer(),
                    Text(fmt.format(total), style: Theme.of(context).textTheme.titleLarge),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          FilledButton(
            onPressed: _submit,
            child: const Text('Оформить заказ'),
          ),
          const SizedBox(height: AppSpacing.md),
        ],
      ),
    );
  }
}
