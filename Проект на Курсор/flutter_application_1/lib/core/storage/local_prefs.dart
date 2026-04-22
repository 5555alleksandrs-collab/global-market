import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../domain/models/cart_item.dart';

/// Локальное хранилище для корзины, избранного, сессии, заказов (mock).
class LocalPrefs {
  LocalPrefs(this._prefs);

  final SharedPreferences _prefs;

  static const _cartKey = 'cart_items_v1';
  static const _favoritesKey = 'favorites_v1';
  static const _authKey = 'auth_session_v1';
  static const _ordersKey = 'orders_v1';
  static const _userKey = 'user_profile_v1';
  static const _adminKey = 'admin_session_v1';
  static const _adminPinKey = 'admin_custom_pin_v1';
  static const _appSessionKey = 'app_session_v1';

  Future<void> saveCart(List<CartItem> items) async {
    final list = items.map((e) => e.toJson()).toList();
    await _prefs.setString(_cartKey, jsonEncode(list));
  }

  List<CartItem> loadCart() {
    final raw = _prefs.getString(_cartKey);
    if (raw == null || raw.isEmpty) return [];
    final decoded = jsonDecode(raw) as List<dynamic>;
    return decoded
        .map((e) => CartItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<void> saveFavoriteIds(Set<String> ids) async {
    await _prefs.setStringList(_favoritesKey, ids.toList());
  }

  Set<String> loadFavoriteIds() {
    return _prefs.getStringList(_favoritesKey)?.toSet() ?? {};
  }

  Future<void> saveAuthSession(String? phone) async {
    if (phone == null) {
      await _prefs.remove(_authKey);
    } else {
      await _prefs.setString(_authKey, phone);
    }
  }

  String? loadAuthSession() => _prefs.getString(_authKey);

  Future<void> saveOrdersJson(String json) async {
    await _prefs.setString(_ordersKey, json);
  }

  String? loadOrdersJson() => _prefs.getString(_ordersKey);

  Future<void> saveUserJson(String? json) async {
    if (json == null) {
      await _prefs.remove(_userKey);
    } else {
      await _prefs.setString(_userKey, json);
    }
  }

  String? loadUserJson() => _prefs.getString(_userKey);

  Future<void> saveAdminSession(bool active) async {
    await _prefs.setBool(_adminKey, active);
  }

  bool loadAdminSession() => _prefs.getBool(_adminKey) ?? false;

  /// Пользовательский PIN админки; если null — используйте [AdminConstants.defaultPin].
  String? loadAdminPin() {
    final v = _prefs.getString(_adminPinKey);
    if (v == null || v.isEmpty) return null;
    return v;
  }

  Future<void> saveAdminPin(String? pin) async {
    if (pin == null || pin.isEmpty) {
      await _prefs.remove(_adminPinKey);
    } else {
      await _prefs.setString(_adminPinKey, pin);
    }
  }

  /// Логин приложения (после успешного входа по паролю).
  Future<void> saveAppSession(String? login) async {
    if (login == null || login.isEmpty) {
      await _prefs.remove(_appSessionKey);
    } else {
      await _prefs.setString(_appSessionKey, login);
    }
  }

  String? loadAppSession() {
    final v = _prefs.getString(_appSessionKey);
    if (v == null || v.isEmpty) return null;
    return v;
  }
}
