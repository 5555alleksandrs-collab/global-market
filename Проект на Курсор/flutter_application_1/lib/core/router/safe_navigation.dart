import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

/// Если в стеке есть куда вернуться — [Navigator.pop] через GoRouter, иначе [go] на [fallback].
void popOrGo(BuildContext context, {String fallback = '/home'}) {
  if (context.canPop()) {
    context.pop();
  } else {
    context.go(fallback);
  }
}
