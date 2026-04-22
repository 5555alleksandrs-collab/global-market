import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../core/constants/app_colors.dart';

class PriceDisplay extends StatelessWidget {
  const PriceDisplay({
    super.key,
    required this.price,
    this.oldPrice,
    this.currency = 'RUB',
    this.style,
    this.oldStyle,
    this.compact = false,
  });

  final double price;
  final double? oldPrice;
  final String currency;
  final TextStyle? style;
  final TextStyle? oldStyle;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat.currency(locale: 'ru_RU', symbol: '₽', decimalDigits: 0);
    final hasDisc = oldPrice != null && oldPrice! > price;
    final base = style ??
        Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w800,
              letterSpacing: -0.35,
              color: AppColors.textPrimary,
              fontSize: compact ? 14 : null,
            );

    return FittedBox(
      fit: BoxFit.scaleDown,
      alignment: Alignment.centerLeft,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(
            fmt.format(price),
            style: base,
          ),
          if (hasDisc) ...[
            const SizedBox(width: 8),
            Text(
              fmt.format(oldPrice),
              style: oldStyle ??
                  Theme.of(context).textTheme.bodyMedium?.copyWith(
                        decoration: TextDecoration.lineThrough,
                        color: AppColors.textSecondary,
                        fontSize: compact ? 12 : null,
                      ),
            ),
          ],
        ],
      ),
    );
  }
}
