import 'package:flutter/material.dart';

/// Тени для тёмной темы — мягкое свечение, без «плоского» Material.
abstract final class AppShadows {
  static List<BoxShadow> card = [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.45),
      blurRadius: 20,
      offset: const Offset(0, 10),
      spreadRadius: -4,
    ),
  ];

  static List<BoxShadow> cardHover = [
    BoxShadow(
      color: const Color(0xFFFF6600).withValues(alpha: 0.12),
      blurRadius: 24,
      offset: const Offset(0, 10),
      spreadRadius: -4,
    ),
  ];

  static List<BoxShadow> navBar = [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.45),
      blurRadius: 20,
      offset: const Offset(0, -6),
      spreadRadius: -8,
    ),
  ];

  static List<BoxShadow> banner = [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.55),
      blurRadius: 32,
      offset: const Offset(0, 16),
      spreadRadius: -12,
    ),
  ];

  static List<BoxShadow> fab = [
    BoxShadow(
      color: const Color(0xFFFF6600).withValues(alpha: 0.45),
      blurRadius: 20,
      offset: const Offset(0, 8),
      spreadRadius: -4,
    ),
  ];
}
