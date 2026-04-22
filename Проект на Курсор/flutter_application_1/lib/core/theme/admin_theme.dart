import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';

/// Визуальный слой админки: светлый «рабочий» фон, акцент indigo (как у Stripe/Notion),
/// без сплошного серого — карточки и боковая панель дают структуру.
abstract final class AdminTheme {
  static const Color canvas = Color(0xFFEEF2FF);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color appBarFill = Color(0xFFF8FAFF);
  static const Color border = Color(0xFFE2E8F0);
  static const Color primary = Color(0xFF4F46E5);
  static const Color primarySoft = Color(0xFFEEF2FF);
  static const Color sidebarBg = Color(0xFF0F172A);
  static const Color sidebarMuted = Color(0xFF94A3B8);
  static const Color success = Color(0xFF059669);
  static const Color warning = Color(0xFFD97706);
  static const Color danger = Color(0xFFDC2626);

  static ThemeData merge(ThemeData base) {
    final scheme = base.colorScheme.copyWith(
      primary: primary,
      onPrimary: Colors.white,
      surface: surface,
      onSurface: const Color(0xFF0F172A),
    );

    return base.copyWith(
      scaffoldBackgroundColor: canvas,
      colorScheme: scheme,
      appBarTheme: base.appBarTheme.copyWith(
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
        backgroundColor: appBarFill,
        foregroundColor: const Color(0xFF0F172A),
        systemOverlayStyle: SystemUiOverlayStyle.dark,
        titleTextStyle: GoogleFonts.inter(
          fontSize: 19,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.3,
          color: const Color(0xFF0F172A),
        ),
      ),
      cardTheme: base.cardTheme.copyWith(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: border),
        ),
      ),
      dividerTheme: const DividerThemeData(color: border, thickness: 1),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: primary,
        foregroundColor: Colors.white,
        elevation: 3,
        highlightElevation: 6,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      inputDecorationTheme: base.inputDecorationTheme.copyWith(
        fillColor: surface,
        filled: true,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 15),
        ),
      ),
    );
  }
}
