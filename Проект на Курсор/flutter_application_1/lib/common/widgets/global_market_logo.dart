import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../core/constants/app_colors.dart';

/// Логотип Global Market: полный блок или одна строка для AppBar.
class GlobalMarketLogo extends StatelessWidget {
  const GlobalMarketLogo({
    super.key,
    this.compact = false,
    this.crossAxisAlignment = CrossAxisAlignment.start,
  });

  final bool compact;
  final CrossAxisAlignment crossAxisAlignment;

  @override
  Widget build(BuildContext context) {
    if (compact) {
      final style = GoogleFonts.inter(
        fontSize: 16,
        fontWeight: FontWeight.w900,
        letterSpacing: 0.3,
        height: 1,
      );
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('GLOBAL ', style: style.copyWith(color: AppColors.textPrimary)),
          Text('MARKET', style: style.copyWith(color: AppColors.accent)),
        ],
      );
    }
    final titleSize = 20.0;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: crossAxisAlignment,
      children: [
        Text(
          'GLOBAL',
          style: GoogleFonts.inter(
            fontSize: titleSize,
            fontWeight: FontWeight.w900,
            letterSpacing: 1,
            height: 1,
            color: AppColors.textPrimary,
          ),
        ),
        Text(
          'MARKET',
          style: GoogleFonts.inter(
            fontSize: titleSize,
            fontWeight: FontWeight.w900,
            letterSpacing: 1,
            height: 1,
            color: AppColors.accent,
          ),
        ),
        const SizedBox(height: 4),
        Container(
          height: 3,
          width: 64,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(2),
            gradient: const LinearGradient(
              colors: [AppColors.accent, AppColors.accentDark],
            ),
          ),
        ),
      ],
    );
  }
}
