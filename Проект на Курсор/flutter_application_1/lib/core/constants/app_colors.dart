import 'package:flutter/material.dart';

/// Global Market — тёмная премиум-палитра: чёрный фон, оранжевый акцент (как в референсе).
abstract final class AppColors {
  static const background = Color(0xFF000000);
  static const surface = Color(0xFF1C1C1E);
  static const surfaceElevated = Color(0xFF2C2C2E);
  static const surfaceMuted = Color(0xFF3A3A3C);
  static const border = Color(0xFF48484A);
  static const textPrimary = Color(0xFFFFFFFF);
  static const textSecondary = Color(0xFFAEAEB2);
  static const textTertiary = Color(0xFF8E8E93);

  /// Оранжевый акцент бренда (кнопки, активные состояния, FAB).
  static const accent = Color(0xFFFF6600);
  static const accentDark = Color(0xFFE85D00);
  static const accentGlow = Color(0x33FF6600);
  static const accentSoft = Color(0xFF332200);

  static const success = Color(0xFF32D74B);
  static const danger = Color(0xFFFF453A);
  static const chip = Color(0xFF2C2C2E);
}
