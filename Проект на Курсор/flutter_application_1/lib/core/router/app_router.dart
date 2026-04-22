import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../application/providers.dart';
import '../../features/auth/code_auth_screen.dart';
import '../../features/auth/phone_auth_screen.dart';
import '../../features/auth/login_screen.dart';
import '../../features/cart/cart_screen.dart';
import '../../features/catalog/catalog_screen.dart';
import '../../features/category/category_screen.dart';
import '../../features/checkout/checkout_screen.dart';
import '../../features/favorites/favorites_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/main_shell.dart';
import '../../features/orders/orders_screen.dart';
import '../../features/product/product_screen.dart';
import '../../features/admin/admin_gate_screen.dart';
import '../../features/admin/admin_product_edit_screen.dart';
import '../theme/admin_theme.dart';
import '../../features/info/company_info_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/profile/settings_screen.dart';

final rootNavigatorKey = GlobalKey<NavigatorState>();

/// Обновляет go_router при смене сессии входа.
class GoRouterRefreshNotifier extends ChangeNotifier {
  void notify() => notifyListeners();
}

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = GoRouterRefreshNotifier();
  ref.listen(appSessionProvider, (_, __) => refresh.notify());

  return GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: '/home',
    refreshListenable: refresh,
    redirect: (context, state) {
      final loggedIn = ref.read(appSessionProvider);
      final path = state.matchedLocation;
      final isLogin = path == '/auth/login';

      if (!loggedIn && !isLogin) {
        final from = Uri.encodeComponent(state.uri.toString());
        return '/auth/login?from=$from';
      }
      if (loggedIn && isLogin) {
        final from = state.uri.queryParameters['from'];
        if (from != null && from.isNotEmpty) {
          try {
            return Uri.decodeComponent(from);
          } catch (_) {
            return '/home';
          }
        }
        return '/home';
      }
      return null;
    },
    routes: [
      GoRoute(
        path: '/auth/login',
        builder: (context, state) => const LoginScreen(),
      ),
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return MainShell(navigationShell: navigationShell);
        },
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/home',
                builder: (context, state) => const HomeScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/catalog',
                builder: (context, state) => const CatalogScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/profile',
                builder: (context, state) => const ProfileScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/cart',
                builder: (context, state) => const CartScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/favorites',
                builder: (context, state) => const FavoritesScreen(),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        parentNavigatorKey: rootNavigatorKey,
        path: '/product/:id',
        builder: (context, state) {
          final id = state.pathParameters['id']!;
          return ProductScreen(productId: id);
        },
      ),
      GoRoute(
        parentNavigatorKey: rootNavigatorKey,
        path: '/category/:categoryId',
        builder: (context, state) {
          final id = state.pathParameters['categoryId']!;
          return CategoryScreen(categoryId: id);
        },
      ),
      GoRoute(
        parentNavigatorKey: rootNavigatorKey,
        path: '/checkout',
        builder: (context, state) => const CheckoutScreen(),
      ),
      GoRoute(
        parentNavigatorKey: rootNavigatorKey,
        path: '/auth/phone',
        builder: (context, state) => const PhoneAuthScreen(),
      ),
      GoRoute(
        parentNavigatorKey: rootNavigatorKey,
        path: '/auth/code',
        builder: (context, state) {
          final phone = state.uri.queryParameters['phone'] ?? '';
          return CodeAuthScreen(phone: phone);
        },
      ),
      GoRoute(
        parentNavigatorKey: rootNavigatorKey,
        path: '/orders',
        builder: (context, state) => const OrdersScreen(),
      ),
      GoRoute(
        parentNavigatorKey: rootNavigatorKey,
        path: '/settings',
        builder: (context, state) => const SettingsScreen(),
      ),
      GoRoute(
        parentNavigatorKey: rootNavigatorKey,
        path: '/company',
        builder: (context, state) => const CompanyInfoScreen(),
      ),
      GoRoute(
        parentNavigatorKey: rootNavigatorKey,
        path: '/admin',
        builder: (context, state) => const AdminGateScreen(),
      ),
      GoRoute(
        parentNavigatorKey: rootNavigatorKey,
        path: '/admin/product',
        builder: (context, state) {
          final id = state.uri.queryParameters['id'];
          return Theme(
            data: AdminTheme.merge(Theme.of(context)),
            child: AdminProductEditScreen(productId: id),
          );
        },
      ),
    ],
  );
});
