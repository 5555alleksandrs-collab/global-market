import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/data/local_catalog_storage.dart';
import '../core/data/repositories/local_catalog_repository.dart';
import '../core/domain/models/cart_item.dart';
import '../core/domain/models/brand.dart';
import '../core/domain/models/category.dart';
import '../core/domain/models/order.dart';
import '../core/domain/models/product.dart';
import '../core/domain/models/user.dart';
import '../core/domain/repositories/catalog_repository.dart';
import '../core/constants/app_credentials.dart';
import '../core/storage/local_prefs.dart';
import '../features/catalog/application/catalog_query.dart';

final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('sharedPreferencesProvider must be overridden in main');
});

final localPrefsProvider = Provider<LocalPrefs>(
  (ref) => LocalPrefs(ref.watch(sharedPreferencesProvider)),
);

final catalogStorageProvider = Provider<LocalCatalogStorage>(
  (ref) => LocalCatalogStorage(ref.watch(sharedPreferencesProvider)),
);

final catalogRepositoryProvider = Provider<CatalogRepository>(
  (ref) => LocalCatalogRepository(ref.watch(catalogStorageProvider)),
);

final categoriesProvider = FutureProvider<List<Category>>((ref) async {
  return ref.watch(catalogRepositoryProvider).getCategories();
});

final brandsProvider = FutureProvider<List<Brand>>((ref) async {
  return ref.watch(catalogRepositoryProvider).getBrands();
});

final allProductsProvider = FutureProvider<List<Product>>((ref) async {
  return ref.watch(catalogRepositoryProvider).getAllProducts();
});

final productProvider = FutureProvider.family<Product?, String>((ref, id) async {
  return ref.watch(catalogRepositoryProvider).getProductById(id);
});

final catalogQueryProvider = StateProvider<CatalogQuery>((ref) => const CatalogQuery());

class CartNotifier extends Notifier<List<CartItem>> {
  @override
  List<CartItem> build() {
    return ref.watch(localPrefsProvider).loadCart();
  }

  Future<void> _save() => ref.read(localPrefsProvider).saveCart(state);

  Future<void> addOrUpdate(CartItem item) async {
    final idx = state.indexWhere(
      (e) => e.productId == item.productId && e.variantId == item.variantId,
    );
    if (idx >= 0) {
      final old = state[idx];
      final merged = old.copyWith(quantity: old.quantity + item.quantity);
      final copy = [...state];
      copy[idx] = merged;
      state = copy;
    } else {
      state = [...state, item];
    }
    await _save();
  }

  Future<void> remove(String cartItemId) async {
    state = state.where((e) => e.id != cartItemId).toList();
    await _save();
  }

  Future<void> setQuantity(String cartItemId, int qty) async {
    if (qty <= 0) {
      await remove(cartItemId);
      return;
    }
    final idx = state.indexWhere((e) => e.id == cartItemId);
    if (idx < 0) return;
    final copy = [...state];
    copy[idx] = copy[idx].copyWith(quantity: qty);
    state = copy;
    await _save();
  }

  Future<void> clear() async {
    state = [];
    await _save();
  }
}

final cartProvider = NotifierProvider<CartNotifier, List<CartItem>>(CartNotifier.new);

class FavoritesNotifier extends Notifier<Set<String>> {
  @override
  Set<String> build() {
    return ref.watch(localPrefsProvider).loadFavoriteIds();
  }

  Future<void> toggle(String productId) async {
    final next = {...state};
    if (next.contains(productId)) {
      next.remove(productId);
    } else {
      next.add(productId);
    }
    state = next;
    await ref.read(localPrefsProvider).saveFavoriteIds(state);
  }

  Future<void> remove(String productId) async {
    final next = {...state}..remove(productId);
    state = next;
    await ref.read(localPrefsProvider).saveFavoriteIds(state);
  }

  bool contains(String productId) => state.contains(productId);
}

final favoritesProvider = NotifierProvider<FavoritesNotifier, Set<String>>(FavoritesNotifier.new);

class AuthNotifier extends Notifier<String?> {
  @override
  String? build() {
    return ref.watch(localPrefsProvider).loadAuthSession();
  }

  Future<void> signInWithPhone(String phone) async {
    state = phone;
    final prefs = ref.read(localPrefsProvider);
    await prefs.saveAuthSession(phone);
    final appLogin = prefs.loadAppSession();
    var name = 'Гость';
    if (appLogin != null && appLogin.isNotEmpty) {
      name = appLogin.length == 1
          ? appLogin.toUpperCase()
          : '${appLogin[0].toUpperCase()}${appLogin.substring(1).toLowerCase()}';
    }
    final user = User(
      id: appLogin != null ? 'app-$appLogin' : 'u-local',
      name: name,
      phone: phone,
      email: null,
    );
    await prefs.saveUserJson(jsonEncode(user.toJson()));
    ref.invalidate(userProfileProvider);
  }

  Future<void> signOut() async {
    state = null;
    final prefs = ref.read(localPrefsProvider);
    await prefs.saveAuthSession(null);
    final appLogin = prefs.loadAppSession();
    if (appLogin != null && appLogin.isNotEmpty) {
      final name = appLogin.length == 1
          ? appLogin.toUpperCase()
          : '${appLogin[0].toUpperCase()}${appLogin.substring(1).toLowerCase()}';
      await prefs.saveUserJson(
        jsonEncode(
          User(
            id: 'app-$appLogin',
            name: name,
            phone: '',
            email: null,
          ).toJson(),
        ),
      );
    } else {
      await prefs.saveUserJson(null);
    }
    ref.invalidate(userProfileProvider);
  }
}

final authProvider = NotifierProvider<AuthNotifier, String?>(AuthNotifier.new);

final userProfileProvider = Provider<User?>((ref) {
  ref.watch(authProvider);
  ref.watch(appSessionProvider);
  final raw = ref.read(localPrefsProvider).loadUserJson();
  if (raw == null || raw.isEmpty) return null;
  try {
    return User.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  } catch (_) {
    return null;
  }
});

class OrdersNotifier extends Notifier<List<Order>> {
  @override
  List<Order> build() {
    final raw = ref.watch(localPrefsProvider).loadOrdersJson();
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list
          .map((e) => Order.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> _persist() async {
    final jsonStr = jsonEncode(state.map((e) => e.toJson()).toList());
    await ref.read(localPrefsProvider).saveOrdersJson(jsonStr);
  }

  Future<void> addOrder(Order order) async {
    state = [order, ...state];
    await _persist();
  }

  Future<void> updateOrder(Order updated) async {
    final idx = state.indexWhere((e) => e.id == updated.id);
    if (idx < 0) return;
    final copy = [...state];
    copy[idx] = updated;
    state = copy;
    await _persist();
  }

  /// Перечитать заказы из SharedPreferences (после синка или pull-to-refresh).
  void reloadFromPrefs() {
    final raw = ref.read(localPrefsProvider).loadOrdersJson();
    if (raw == null || raw.isEmpty) {
      state = [];
      return;
    }
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      state = list
          .map((e) => Order.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      state = [];
    }
  }
}

final ordersProvider = NotifierProvider<OrdersNotifier, List<Order>>(OrdersNotifier.new);

class AdminAuthNotifier extends Notifier<bool> {
  @override
  bool build() => ref.watch(localPrefsProvider).loadAdminSession();

  Future<void> setAuthenticated(bool value) async {
    state = value;
    await ref.read(localPrefsProvider).saveAdminSession(value);
  }

  Future<void> signOut() => setAuthenticated(false);
}

final adminAuthProvider = NotifierProvider<AdminAuthNotifier, bool>(AdminAuthNotifier.new);

/// Вход по логину и паролю (демо — см. [AppCredentials]).
class AppSessionNotifier extends Notifier<bool> {
  @override
  bool build() {
    return ref.read(localPrefsProvider).loadAppSession() != null;
  }

  Future<void> signIn(String login, String password) async {
    final l = login.trim();
    final p = password;
    if (l != AppCredentials.demoLogin || p != AppCredentials.demoPassword) {
      throw Exception('Неверный логин или пароль');
    }
    final prefs = ref.read(localPrefsProvider);
    var phone = prefs.loadAuthSession() ?? '';
    final existingRaw = prefs.loadUserJson();
    if (existingRaw != null && existingRaw.isNotEmpty) {
      try {
        final u = User.fromJson(jsonDecode(existingRaw) as Map<String, dynamic>);
        if (u.phone.isNotEmpty) phone = u.phone;
      } catch (_) {}
    }
    final display = l.substring(0, 1).toUpperCase() + l.substring(1);
    await prefs.saveAppSession(l);
    await prefs.saveUserJson(
      jsonEncode(
        User(
          id: 'app-$l',
          name: display,
          phone: phone,
          email: null,
        ).toJson(),
      ),
    );
    state = true;
    ref.invalidate(userProfileProvider);
  }

  Future<void> signOut() async {
    await ref.read(localPrefsProvider).saveAppSession(null);
    await ref.read(localPrefsProvider).saveUserJson(null);
    state = false;
    await ref.read(authProvider.notifier).signOut();
    await ref.read(adminAuthProvider.notifier).signOut();
    ref.invalidate(userProfileProvider);
  }
}

final appSessionProvider = NotifierProvider<AppSessionNotifier, bool>(AppSessionNotifier.new);

/// Операции админки: сохранение каталога на диск + обновление провайдеров.
class AdminCatalogService {
  AdminCatalogService(this._ref);

  final Ref _ref;

  Future<void> upsertProduct(Product product) async {
    final storage = _ref.read(catalogStorageProvider);
    final list = await storage.load();
    final idx = list.indexWhere((e) => e.id == product.id);
    if (idx >= 0) {
      list[idx] = product;
    } else {
      list.add(product);
    }
    await storage.save(list);
    _invalidateCatalog(product.id);
  }

  Future<void> deleteProduct(String id) async {
    final storage = _ref.read(catalogStorageProvider);
    final list = (await storage.load()).where((e) => e.id != id).toList();
    await storage.save(list);
    _invalidateCatalog(id);
  }

  Future<void> resetCatalogToSeed() async {
    await _ref.read(catalogStorageProvider).resetToSeed();
    _ref.invalidate(allProductsProvider);
  }

  void _invalidateCatalog(String productId) {
    _ref.invalidate(allProductsProvider);
    _ref.invalidate(productProvider(productId));
  }
}

final adminCatalogServiceProvider = Provider<AdminCatalogService>(
  (ref) => AdminCatalogService(ref),
);
