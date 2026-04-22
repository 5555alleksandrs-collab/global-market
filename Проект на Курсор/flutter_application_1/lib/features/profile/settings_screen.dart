import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/router/safe_navigation.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => popOrGo(context, fallback: '/profile'),
        ),
        title: const Text('Настройки'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: const [
          ListTile(
            title: Text('Уведомления'),
            subtitle: Text('Push — подключение в будущем'),
          ),
          ListTile(
            title: Text('Валюта'),
            subtitle: Text('Сейчас: RUB (mock)'),
          ),
          ListTile(
            title: Text('Поддержка'),
            subtitle: Text('Чат поддержки — позже'),
          ),
        ],
      ),
    );
  }
}
